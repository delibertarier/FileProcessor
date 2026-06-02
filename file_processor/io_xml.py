from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from lxml import etree

from .config import FlowConfig
from .mapping import Mapping
from .transformations import resolve_transform

logger = logging.getLogger(__name__)

_DEFAULT_LINE_FILENAME_ELEMENTS = (
    "ExciseProductCode",
    "BodyRecordUniqueReference",
    "CnCode",
)


@dataclass
class XmlToCsvResult:
    """Rows to write and optional per-line filename suffixes (without leading _)."""

    rows: list[dict[int, str]]
    file_suffixes: list[str]


def parse_xml_tree(path: Path) -> etree._ElementTree:
    """Parse an XML file into an lxml ElementTree."""
    return etree.parse(str(path))


def _local_name(tag: str) -> str:
    """Element tag local name, ignoring XML namespace URI or prefix (e.g. ie:IE801)."""
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.split(":", 1)[-1]
    return tag


def _xpath_parts(xpath: str) -> tuple[list[str], str | None]:
    """Split a mapping XPath into element parts and optional trailing attribute name."""
    if not xpath:
        return [], None

    if not xpath.startswith("/"):
        xpath = "/" + xpath

    attr_name = None
    if "/@" in xpath:
        xpath, attr_name = xpath.rsplit("/@", 1)

    parts = [_local_name(p) for p in xpath.split("/") if p]
    return parts, attr_name


def _normalize_mapping_xpath(raw_xpath: str) -> tuple[str, str]:
    """Strip namespace prefixes from mapping XPath segments (ie:Tag -> Tag)."""
    parts, attr_name = _xpath_parts(raw_xpath)
    if not parts:
        return raw_xpath, ""

    path = "/" + "/".join(parts)
    if attr_name:
        path += f"/@{_local_name(attr_name)}"
    rel = "/".join(parts)
    return path, rel


def _safe_xpath(root: etree._Element, expr: str) -> list:
    if not expr:
        return []
    try:
        return root.xpath(expr)
    except etree.XPathEvalError:
        return []


def _xpath_by_local_names(root: etree._Element, parts: list[str], attr_name: str | None) -> list:
    """Build //local-name() chain so namespaced EMCS elements match mapping paths."""
    if not parts:
        return []

    expr = f"//*[local-name()='{parts[0]}']"
    for part in parts[1:]:
        expr += f"/*[local-name()='{part}']"
    if attr_name:
        expr += f"/@{attr_name}"

    nodes = _safe_xpath(root, expr)
    if attr_name and nodes:
        return nodes
    if nodes and not attr_name:
        return nodes
    return []


def _find_node_case_insensitive(root: etree._Element, xpath: str):
    """
    Resolve a simple absolute/root-relative XPath by tag name, with case-insensitive
    matching for element names.

    Returns the matched element or attribute/string value, or None when not found.
    Supports basic attribute tail syntax, e.g. /A/B/@attr.
    """
    parts, attr_name = _xpath_parts(xpath)
    if not parts:
        return None

    if _local_name(root.tag).lower() != parts[0].lower():
        return None

    current = root
    for tag in parts[1:]:
        tag_l = tag.lower()
        child = current.find(tag)
        if child is None:
            child = next(
                (
                    c
                    for c in current
                    if hasattr(c, "tag")
                    and isinstance(c.tag, str)
                    and _local_name(c.tag).lower() == tag_l
                ),
                None,
            )
        if child is None:
            return None
        current = child

    if attr_name:
        return current.get(attr_name)
    return current


def _find_descendant_case_insensitive(root: etree._Element, rel_path: str):
    """
    Resolve a relative path by finding the first matching descendant path
    case-insensitively, e.g. "GoodsDeclaration/linkId" or "MessageDetails/type".
    """
    parts = [_local_name(p) for p in rel_path.split("/") if p]
    if not parts:
        return None

    first = parts[0].lower()
    for start in root.iter():
        if not hasattr(start, "tag") or not isinstance(start.tag, str):
            continue
        if _local_name(start.tag).lower() != first:
            continue

        current = start
        ok = True
        for tag in parts[1:]:
            tag_l = tag.lower()
            child = current.find(tag)
            if child is None:
                child = next(
                    (
                        c
                        for c in current
                        if hasattr(c, "tag")
                        and isinstance(c.tag, str)
                        and _local_name(c.tag).lower() == tag_l
                    ),
                    None,
                )
            if child is None:
                ok = False
                break
            current = child
        if ok:
            return current
    return None


def _resolve_xpath_nodes(root: etree._Element, raw_xpath: str) -> list:
    """
    Resolve mapping XPath to nodes/values.

    Order: standard XPath, descendant XPath, local-name XPath, tree walk fallbacks.
    """
    abs_xpath, rel_xpath = _normalize_mapping_xpath(raw_xpath)
    parts, attr_name = _xpath_parts(abs_xpath)
    root_local = _local_name(root.tag)
    rel_without_root = ""
    if parts and parts[0].lower() == root_local.lower():
        rel_without_root = "/".join(parts[1:])

    nodes = _safe_xpath(root, abs_xpath)
    if not nodes and rel_xpath:
        nodes = _safe_xpath(root, f".//{rel_xpath}")
    if not nodes and rel_without_root:
        nodes = _safe_xpath(root, f".//{rel_without_root}")

    if not nodes and parts:
        nodes = _xpath_by_local_names(root, parts, attr_name)
    if not nodes and rel_without_root:
        parts_wo_root, _ = _xpath_parts("/" + rel_without_root)
        if parts_wo_root:
            nodes = _xpath_by_local_names(root, parts_wo_root, attr_name)

    if nodes:
        return nodes

    fallback_node = _find_node_case_insensitive(root, abs_xpath)
    if fallback_node is None and rel_xpath:
        fallback_node = _find_descendant_case_insensitive(root, rel_xpath)
    if fallback_node is None and rel_without_root:
        fallback_node = _find_descendant_case_insensitive(root, rel_without_root)

    if fallback_node is None:
        return []

    if isinstance(fallback_node, str):
        return [fallback_node]
    return [fallback_node]


def _line_item_local_name(xml_line_xpath: str) -> str:
    parts, _ = _xpath_parts(
        xml_line_xpath if xml_line_xpath.startswith("/") else "/" + xml_line_xpath
    )
    return parts[-1] if parts else _local_name(xml_line_xpath)


def _find_line_item_elements(root: etree._Element, xml_line_xpath: str) -> list[etree._Element]:
    local = _line_item_local_name(xml_line_xpath)
    return [
        el
        for el in root.iter()
        if isinstance(el.tag, str) and _local_name(el.tag) == local
    ]


def _xpath_is_line_scoped(raw_xpath: str, line_local_name: str) -> bool:
    parts = [_local_name(p) for p in raw_xpath.split("/") if p]
    return line_local_name in parts


def _xpath_relative_to_line_item(raw_xpath: str, line_local_name: str) -> str:
    parts = [_local_name(p) for p in raw_xpath.split("/") if p]
    if line_local_name not in parts:
        return raw_xpath
    return "/".join(parts[parts.index(line_local_name) + 1 :])


def _sanitize_filename_part(value: str) -> str:
    """Safe fragment for Windows / FTP filenames."""
    cleaned = re.sub(r'[<>:"/\\|?*\s]+', "_", value.strip())
    cleaned = cleaned.strip("._")
    return cleaned[:80] if cleaned else ""


def _line_item_file_suffix(
    line_item: etree._Element,
    *,
    preferred_element: Optional[str],
    fallback_index: int,
) -> str:
    """
    Build a filename suffix from a child element of the line item (e.g. ExciseProductCode -> E440).
    """
    candidates: list[str] = []
    if preferred_element:
        candidates.append(_local_name(preferred_element))
    for name in _DEFAULT_LINE_FILENAME_ELEMENTS:
        if name not in candidates:
            candidates.append(name)

    for name in candidates:
        nodes = _resolve_path_under_context(line_item, name)
        if not nodes:
            continue
        node = nodes[0]
        if isinstance(node, str):
            text = node.strip()
        else:
            text = (node.text or "").strip()
        safe = _sanitize_filename_part(text)
        if safe:
            return safe

    return f"line{fallback_index:02d}"


def _resolve_path_under_context(context: etree._Element, rel_path: str) -> list:
    """
    Walk direct children under context by local name (handles namespaces).

    Unlike _resolve_xpath_nodes, never treats the path as document-absolute.
    """
    if not rel_path:
        return [context]

    attr_name = None
    if "/@" in rel_path:
        rel_path, attr_name = rel_path.rsplit("/@", 1)

    parts = [_local_name(p) for p in rel_path.split("/") if p]
    if not parts:
        return [context]

    current: etree._Element | None = context
    for part in parts:
        if current is None:
            return []
        tag_l = part.lower()
        child = next(
            (
                c
                for c in current
                if isinstance(c.tag, str) and _local_name(c.tag).lower() == tag_l
            ),
            None,
        )
        if child is None:
            return []
        current = child

    if attr_name:
        val = current.get(attr_name)
        return [val] if val is not None else []
    return [current]


def _element_value_for_concat(el: etree._Element) -> str:
    """Compact text for one element (e.g. VariableCheck blocks)."""
    error_type = el.findtext("errorType")
    description = el.findtext("description")

    if (error_type is not None or description is not None) and (error_type or description):
        et = (error_type or "").strip()
        de = (description or "").strip()
        if et and de:
            return f"{et}: {de}"
        return et or de

    parts = [t.strip() for t in el.itertext() if t is not None and t.strip()]
    return " ".join(parts)


def _coerce_nodes_to_value(nodes, *, first_only: bool = False) -> str:
    if first_only and nodes:
        nodes = nodes[:1]

    if len(nodes) == 1:
        node = nodes[0]
        if isinstance(node, str):
            return node.strip()
        return (node.text or "").strip() if hasattr(node, "text") else ""

    values: list[str] = []
    for node in nodes:
        if isinstance(node, str):
            v = node.strip()
        else:
            v = _element_value_for_concat(node)
        if v:
            values.append(v)

    if not values:
        return ""

    first_is_variablecheck = False
    for n in nodes:
        if isinstance(n, str):
            continue
        if hasattr(n, "tag") and isinstance(n.tag, str) and n.tag.lower() == "variablecheck":
            first_is_variablecheck = True
        break

    if first_is_variablecheck:
        return " ".join(values)

    return " ".join(values)


def _build_row(
    mapping: Mapping,
    *,
    doc_root: etree._Element,
    line_item: Optional[etree._Element],
    line_local_name: Optional[str],
    document_first_only: bool,
) -> dict[int, str]:
    row: dict[int, str] = {}

    for entry in mapping.entries:
        transform_name_raw = entry.transform_name.strip() if entry.transform_name else ""
        transform_name = transform_name_raw.lower()
        if transform_name == "skip":
            # Ignore this mapping row entirely for XML->CSV.
            continue

        if entry.source_column_index is None:
            # Constants don't participate in XML->CSV for now.
            continue

        if transform_name.startswith("fixed:"):
            value = transform_name_raw.split(":", 1)[1]
            row[entry.source_column_index] = value
            logger.debug(
                "xml_to_csv: fixed transform xpath=%s (column=%s) -> %r",
                entry.target_xpath,
                entry.source_column_index,
                value,
            )
            continue

        raw_xpath = entry.target_xpath.strip()
        if (
            line_item is not None
            and line_local_name
            and _xpath_is_line_scoped(raw_xpath, line_local_name)
        ):
            rel = _xpath_relative_to_line_item(raw_xpath, line_local_name)
            nodes = _resolve_path_under_context(line_item, rel) if rel else [line_item]
            use_first_only = False
        else:
            nodes = _resolve_xpath_nodes(doc_root, raw_xpath)
            use_first_only = document_first_only

        if not nodes:
            value = ""
            logger.debug(
                "xml_to_csv: no match for xpath=%s (column=%s)",
                raw_xpath,
                entry.source_column_index,
            )
        else:
            value = _coerce_nodes_to_value(nodes, first_only=use_first_only)
            logger.debug(
                "xml_to_csv: matched xpath=%s (column=%s) -> %r",
                raw_xpath,
                entry.source_column_index,
                value,
            )

        if transform_name and transform_name not in ("skip", "empty") and not transform_name.startswith("fixed:"):
            transform = resolve_transform(transform_name_raw)
            try:
                value = transform(str(value))
            except Exception:
                logger.exception(
                    "xml_to_csv: transform %r failed for xpath=%s (column=%s) with value=%r",
                    transform_name,
                    raw_xpath,
                    entry.source_column_index,
                    value,
                )
                value = ""

        row[entry.source_column_index] = value

    return row


def xml_to_csv_result(
    mapping: Mapping,
    xml_tree: etree._ElementTree,
    flow: Optional[FlowConfig] = None,
) -> XmlToCsvResult:
    """
    Extract CSV row dicts from XML using the mapping XLS.

    With xml_line_xpath: one row per repeating line item. file_suffixes are set when
    xml_line_output is file_per_line (from ExciseProductCode etc. on each line).
    """
    root = xml_tree.getroot()
    xml_line_xpath = flow.xml_line_xpath if flow else None
    per_line_files = bool(flow and flow.xml_line_xpath and flow.xml_line_output == "file_per_line")
    filename_element = flow.xml_line_filename_element if flow else None

    if not xml_line_xpath:
        row = _build_row(
            mapping,
            doc_root=root,
            line_item=None,
            line_local_name=None,
            document_first_only=False,
        )
        logger.info("xml_to_csv: 1 CSV row (no xml_line_xpath)")
        return XmlToCsvResult(rows=[row], file_suffixes=[])

    line_local = _line_item_local_name(xml_line_xpath)
    line_items = _find_line_item_elements(root, xml_line_xpath)
    multi_line = len(line_items) > 1

    rows: list[dict[int, str]] = []
    suffixes: list[str] = []

    for index, item in enumerate(line_items, start=1):
        rows.append(
            _build_row(
                mapping,
                doc_root=root,
                line_item=item,
                line_local_name=line_local,
                document_first_only=multi_line,
            )
        )
        if per_line_files:
            suffixes.append(
                _line_item_file_suffix(
                    item,
                    preferred_element=filename_element,
                    fallback_index=index,
                )
            )

    if not line_items:
        rows.append(
            _build_row(
                mapping,
                doc_root=root,
                line_item=None,
                line_local_name=None,
                document_first_only=False,
            )
        )

    if per_line_files and suffixes:
        logger.info(
            "xml_to_csv: %d row(s), separate CSV per <%s> (suffixes: %s)",
            len(rows),
            line_local,
            ", ".join(suffixes),
        )
    else:
        logger.info(
            "xml_to_csv: %d CSV row(s) from %d <%s> line item(s)",
            len(rows),
            len(line_items),
            line_local,
        )

    return XmlToCsvResult(rows=rows, file_suffixes=suffixes if per_line_files else [])


def xml_to_row_dicts(
    mapping: Mapping,
    xml_tree: etree._ElementTree,
    flow: Optional[FlowConfig] = None,
) -> List[Dict[int, str]]:
    """Backward-compatible wrapper returning rows only."""
    return xml_to_csv_result(mapping, xml_tree, flow).rows

