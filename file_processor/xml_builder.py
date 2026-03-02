from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from lxml import etree

from .config import FlowConfig
from .mapping import Mapping, MappingEntry
from .transformations import TRANSFORMATIONS, identity


def _get_transform(name: Optional[str]):
    if not name:
        return identity
    func = TRANSFORMATIONS.get(name)
    if not func:
        raise KeyError(f"Unknown transformation rule: {name}")
    return func


def _ensure_element(root: etree._Element, xpath: str) -> etree._Element:
    """
    Ensure that an element exists for the given XPath relative to the root,
    creating intermediate nodes as needed.
    """
    # For simplicity, handle only absolute-like paths without predicates (e.g. /Root/Order/Line/Amount)
    if not xpath.startswith("/"):
        raise ValueError(f"Only absolute XPaths are supported for now: {xpath!r}")

    parts = [p for p in xpath.split("/") if p]
    if not parts:
        raise ValueError(f"Invalid XPath: {xpath!r}")

    if root.tag != parts[0]:
        raise ValueError(f"Root element name mismatch: expected {root.tag!r}, got {parts[0]!r}")

    current = root
    for tag in parts[1:]:
        child = current.find(tag)
        if child is None:
            child = etree.SubElement(current, tag)
        current = child
    return current


def build_xml_for_group(
    flow: FlowConfig,
    mapping: Mapping,
    rows: Iterable[dict[int, str]],
    group_key: Optional[str] = None,
) -> etree._ElementTree:
    """
    Build an XML document for a group of CSV rows.

    - `rows` is an iterable of {column_index (1-based) -> value}.
    - If `flow.grouping` is set, we treat the mapping entries as applying:
      - Once at group level (XPaths under group_root_xpath but not under item_xpath)
      - Once per row (XPaths under item_xpath), yielding repeating items.
    """
    root = etree.Element(flow.root_element_name)

    if not flow.grouping:
        # No grouping: each row is treated separately but we still emit a single document
        for row in rows:
            _apply_mapping_entries(root, mapping, row)
        return etree.ElementTree(root)

    grouping = flow.grouping
    group_root = _ensure_element(root, grouping.group_root_xpath)

    # Apply any group-level constants or synthetic values (if mapping uses group_root_xpath)
    for entry in mapping.entries:
        if entry.target_xpath.startswith(grouping.group_root_xpath) and not entry.target_xpath.startswith(
            grouping.item_xpath
        ):
            # Group-level mapping
            value = _resolve_entry_value(entry, None)
            if value is None:
                continue
            elem = _ensure_element(root, entry.target_xpath)
            elem.text = value

    # Now create items per row
    for row in rows:
        item_elem = _ensure_element(group_root, grouping.item_xpath)
        _apply_mapping_entries(item_elem, mapping, row, base_xpath=grouping.item_xpath)

    return etree.ElementTree(root)


def _resolve_entry_value(entry: MappingEntry, row: Optional[dict[int, str]]) -> Optional[str]:
    if entry.source_column_index is None:
        value = entry.constant_value
    else:
        if row is None:
            return None
        value = row.get(entry.source_column_index)

    if value is None:
        return None

    transform = _get_transform(entry.transform_name)
    return transform(str(value))


def _apply_mapping_entries(
    base_root: etree._Element,
    mapping: Mapping,
    row: dict[int, str],
    base_xpath: Optional[str] = None,
) -> None:
    for entry in mapping.entries:
        target_xpath = entry.target_xpath
        if base_xpath and not target_xpath.startswith(base_xpath):
            # Skip entries that do not belong under this item subtree
            continue

        value = _resolve_entry_value(entry, row)
        if value is None:
            continue

        elem = _ensure_element(base_root.getroottree().getroot(), target_xpath)
        elem.text = value


def validate_xml_with_xsd(xml_tree: etree._ElementTree, xsd_file: Optional[Path]) -> None:
    if not xsd_file:
        return
    schema_doc = etree.parse(str(xsd_file))
    schema = etree.XMLSchema(schema_doc)
    if not schema.validate(xml_tree):
        errors = [str(e) for e in schema.error_log]
        raise ValueError(f"XML failed XSD validation: {'; '.join(errors)}")

