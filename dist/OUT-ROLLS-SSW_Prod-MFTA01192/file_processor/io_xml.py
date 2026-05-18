from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from lxml import etree

from .mapping import Mapping
from .transformations import resolve_transform

logger = logging.getLogger(__name__)


def parse_xml_tree(path: Path) -> etree._ElementTree:
    """Parse an XML file into an lxml ElementTree."""
    return etree.parse(str(path))


def _find_node_case_insensitive(root: etree._Element, xpath: str):
    """
    Resolve a simple absolute/root-relative XPath by tag name, with case-insensitive
    matching for element names.

    Returns the matched element or attribute/string value, or None when not found.
    Supports basic attribute tail syntax, e.g. /A/B/@attr.
    """
    if not xpath:
        return None

    if not xpath.startswith("/"):
        xpath = "/" + xpath

    attr_name = None
    if "/@" in xpath:
        xpath, attr_name = xpath.rsplit("/@", 1)

    parts = [p for p in xpath.split("/") if p]
    if not parts:
        return None

    # Root match (case-insensitive)
    if root.tag != parts[0] and root.tag.lower() != parts[0].lower():
        return None

    current = root
    for tag in parts[1:]:
        child = current.find(tag)
        if child is None:
            tag_l = tag.lower()
            child = next(
                (
                    c
                    for c in current
                    if hasattr(c, "tag") and isinstance(c.tag, str) and c.tag.lower() == tag_l
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
    parts = [p for p in rel_path.split("/") if p]
    if not parts:
        return None

    first = parts[0].lower()
    for start in root.iter():
        if not hasattr(start, "tag") or not isinstance(start.tag, str):
            continue
        if start.tag.lower() != first:
            continue

        current = start
        ok = True
        for tag in parts[1:]:
            child = current.find(tag)
            if child is None:
                tag_l = tag.lower()
                child = next(
                    (
                        c
                        for c in current
                        if hasattr(c, "tag") and isinstance(c.tag, str) and c.tag.lower() == tag_l
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


def xml_to_row_dicts(mapping: Mapping, xml_tree: etree._ElementTree) -> List[Dict[int, str]]:
    """
    Extract CSV-style row dictionaries from an XML tree using the same XLS mapping.

    For now we implement a simple 1:1 mapping:
    - For each MappingEntry, evaluate its XPath relative to the root and take the first match's text.
    - Combine all values into a single row dict {column_index -> value}.
    - This yields exactly one CSV row per XML file.
    """
    root = xml_tree.getroot()
    row: dict[int, str] = {}
    matched_count = 0

    def _element_value_for_concat(el: etree._Element) -> str:
        """
        Convert one matched element into a compact text value suitable for CSV.

        For VariableCheck blocks this becomes: "<errorType>: <description>".
        Otherwise we fall back to joining all descendant text with spaces.
        """
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

    def _coerce_nodes_to_value(nodes) -> str:
        # XPath can return element nodes or strings.
        if len(nodes) == 1:
            node = nodes[0]
            if isinstance(node, str):
                return node.strip()
            return (node.text or "").strip() if hasattr(node, "text") else ""

        # Multiple results: concatenate into one CSV cell.
        # For VariableCheck nodes, we join using a single space and wrap each
        # description in double quotes, per Ops request.
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

        # If elements came from VariableCheck, wrap each value in quotes.
        first_is_variablecheck = False
        for n in nodes:
            if isinstance(n, str):
                continue
            if hasattr(n, "tag") and isinstance(n.tag, str) and n.tag.lower() == "variablecheck":
                first_is_variablecheck = True
            break

        if first_is_variablecheck:
            # Ops wants: space between VariableCheck descriptions, and only the
            # outer CSV quoting (if needed) handled by the CSV writer.
            return " ".join(values)

        # Generic fallback: space-delimit.
        return " ".join(values)

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
            matched_count += 1
            logger.debug(
                "xml_to_csv: fixed transform xpath=%s (column=%s) -> %r",
                entry.target_xpath,
                entry.source_column_index,
                value,
            )
            continue

        raw_xpath = entry.target_xpath.strip()
        is_absolute = raw_xpath.startswith("/")
        abs_xpath = raw_xpath if is_absolute else "/" + raw_xpath
        rel_xpath = raw_xpath.lstrip("/")
        desc_xpath = f".//{rel_xpath}" if rel_xpath else ""

        # 1) absolute/root-relative style
        nodes = root.xpath(abs_xpath)
        if not nodes and desc_xpath:
            # 2) relative mapping style: search descendants anywhere in the document
            nodes = root.xpath(desc_xpath)

        if not nodes:
            # 3) case-insensitive fallbacks
            fallback_node = _find_node_case_insensitive(root, abs_xpath)
            if fallback_node is None and rel_xpath:
                fallback_node = _find_descendant_case_insensitive(root, rel_xpath)
            if fallback_node is None:
                value = ""
                logger.debug(
                    "xml_to_csv: no match for xpath=%s (column=%s)",
                    raw_xpath,
                    entry.source_column_index,
                )
            else:
                matched_count += 1
                if isinstance(fallback_node, str):
                    value = fallback_node
                else:
                    value = (fallback_node.text or "").strip()
                logger.debug(
                    "xml_to_csv: case-insensitive match xpath=%s (column=%s) -> %r",
                    raw_xpath,
                    entry.source_column_index,
                    value,
                )
        else:
            matched_count += 1
            value = _coerce_nodes_to_value(nodes)
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

    logger.info(
        "xml_to_csv: extracted %d/%d mapped fields from XML",
        matched_count,
        len(mapping.entries),
    )
    return [row]

