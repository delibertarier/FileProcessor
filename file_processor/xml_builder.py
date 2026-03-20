from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Set

from lxml import etree

from .config import FlowConfig
from .mapping import Mapping, MappingEntry
from .transformations import TRANSFORMATIONS, identity


def _get_transform(name: Optional[str]):
    """
    Resolve a transform function by name.

    - Empty / None name -> identity.
    - Known name in TRANSFORMATIONS -> that function.
    - Dynamic pattern: "first_<N>" -> take first N characters from the value.
    - Anything else -> identity (no change).
    """
    if not name:
        return identity

    # Static transforms registered in TRANSFORMATIONS
    func = TRANSFORMATIONS.get(name)
    if func:
        return func

    # Dynamic transform: first_<N>  (e.g. first_3, first_10)
    if name.startswith("first_"):
        length_str = name.removeprefix("first_")
        try:
            n = int(length_str)
        except ValueError:
            return identity
        if n <= 0:
            return identity

        def first_n(value: str, _n: int = n) -> str:
            return value[:_n]

        return first_n

    # Unknown names fall back to identity instead of failing hard
    return identity


def _ensure_element(root: etree._Element, xpath: str) -> etree._Element:
    """
    Ensure that an element exists for the given XPath relative to the root,
    creating intermediate nodes as needed.

    The mapping file may use either:
    - Absolute-style paths: `/PldaSswDeclaration/...`
    - Root-relative paths without leading slash: `PldaSswDeclaration/...`
    We normalize by prepending `/` when missing.

    When locating a child, we first try exact tag match, then case-insensitive
    match so that mapping paths like .../outbound/... match the skeleton's .../Outbound/...
    """
    if not xpath.startswith("/"):
        xpath = "/" + xpath

    parts = [p for p in xpath.split("/") if p]
    if not parts:
        raise ValueError(f"Invalid XPath: {xpath!r}")

    if root.tag != parts[0]:
        # Case-insensitive root match when using skeleton
        if root.tag.lower() != parts[0].lower():
            raise ValueError(f"Root element name mismatch: expected {root.tag!r}, got {parts[0]!r}")
    current = root
    for tag in parts[1:]:
        child = current.find(tag)
        if child is None:
            # Case-insensitive match so e.g. "outbound" finds skeleton's "Outbound".
            # Only consider element children (skip comments, PIs, etc.).
            tag_lower = tag.lower() if isinstance(tag, str) else tag
            child = next(
                (
                    c
                    for c in current
                    if hasattr(c, "tag") and isinstance(c.tag, str) and c.tag.lower() == tag_lower
                ),
                None,
            )
        if child is None:
            # Mapping is allowed to extend beyond the skeleton: create missing elements.
            child = etree.SubElement(current, tag)
        current = child
    return current


def _find_element(root: etree._Element, xpath: str) -> Optional[etree._Element]:
    """
    Find an element at the given XPath if it exists; return None if any segment is missing.
    Same path normalization and case-insensitive matching as _ensure_element, but never creates.
    """
    if not xpath.startswith("/"):
        xpath = "/" + xpath

    parts = [p for p in xpath.split("/") if p]
    if not parts:
        return None

    if root.tag != parts[0]:
        if root.tag.lower() != parts[0].lower():
            return None
    current = root
    for tag in parts[1:]:
        child = current.find(tag)
        if child is None:
            tag_lower = tag.lower() if isinstance(tag, str) else tag
            child = next(
                (
                    c
                    for c in current
                    if hasattr(c, "tag") and isinstance(c.tag, str) and c.tag.lower() == tag_lower
                ),
                None,
            )
        if child is None:
            return None
        current = child
    return current


def _collect_allowed_paths(mapping: Mapping) -> Set[str]:
    """
    Collect all XPaths that are explicitly mapped (and should appear in output), plus their ancestors.

    Entries with transform_name "skip" are excluded so that those elements are pruned
    when using a skeleton (e.g. language tags you do not want in the output).
    Paths are normalized to lowercase for matching against the actual XML tree.
    """
    allowed: set[str] = set()
    for entry in mapping.entries:
        if entry.transform_name and entry.transform_name.strip().lower() == "skip":
            continue
        xpath = entry.target_xpath
        if not xpath:
            continue
        if not xpath.startswith("/"):
            xpath = "/" + xpath
        parts = [p for p in xpath.split("/") if p]
        if not parts:
            continue
        current = ""
        for p in parts:
            current += "/" + p
            allowed.add(current.lower())
    return allowed


def _prune_unused_elements(root: etree._Element, allowed_paths_lc: Set[str]) -> None:
    """
    Remove elements from the skeleton that are not in the mapping file (stream/XPath column).
    Any such element is removed so we do not emit tags that are not mapped (e.g. tags that cannot be empty).
    """

    def _walk(elem: etree._Element, current_path: str) -> None:
        # Work on a copy of children list since we may modify it.
        for child in list(elem):
            if not hasattr(child, "tag") or not isinstance(child.tag, str):
                # Skip comments, processing instructions, etc.
                continue
            child_path = f"{current_path}/{child.tag}"
            _walk(child, child_path)

            # Remove element if it is not in the mapping and has no element children.
            has_element_children = any(
                hasattr(c, "tag") and isinstance(c.tag, str) for c in child
            )
            if child_path.lower() not in allowed_paths_lc and not has_element_children:
                elem.remove(child)

    root_path = "/" + root.tag
    _walk(root, root_path)


def build_xml_for_group(
    flow: FlowConfig,
    mapping: Mapping,
    rows: Iterable[dict[int, str]],
    group_key: Optional[str] = None,
) -> etree._ElementTree:
    """
    Build an XML document for a group of CSV rows.

    - `rows` is an iterable of {column_index (1-based) -> value}.
    - If `flow.skeleton_xml` is set, use that XML as the starting template.
    - If `flow.grouping` is set, we treat the mapping entries as applying:
      - Once at group level (XPaths under group_root_xpath but not under item_xpath)
      - Once per row (XPaths under item_xpath), yielding repeating items.
    """
    using_skeleton = flow.skeleton_xml is not None

    if using_skeleton:
        # Parse skeleton fresh for each document so we don't mutate a shared tree
        root = etree.parse(str(flow.skeleton_xml)).getroot()
    else:
        root = etree.Element(flow.root_element_name)

    if not flow.grouping:
        # No grouping: each row is treated separately but we still emit a single document
        for row in rows:
            _apply_mapping_entries(root, mapping, row)
        if using_skeleton:
            allowed_paths = _collect_allowed_paths(mapping)
            _prune_unused_elements(root, allowed_paths)
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
        _apply_mapping_entries(
            item_elem,
            mapping,
            row,
            base_xpath=grouping.item_xpath,
        )

    if using_skeleton:
        allowed_paths = _collect_allowed_paths(mapping)
        _prune_unused_elements(root, allowed_paths)

    return etree.ElementTree(root)


def _resolve_entry_value(entry: MappingEntry, row: Optional[dict[int, str]]) -> Optional[str]:
    # Special transform name to skip this mapping line entirely (case-insensitive).
    if entry.transform_name and entry.transform_name.strip().lower() == "skip":
        return None

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

        # When value is empty, do not emit the tag: skip creating it, and remove it if present (e.g. from skeleton).
        if not str(value).strip():
            root_elem = base_root.getroottree().getroot()
            elem = _find_element(root_elem, target_xpath)
            if elem is not None and elem.getparent() is not None:
                elem.getparent().remove(elem)
            continue

        elem = _ensure_element(
            base_root.getroottree().getroot(),
            target_xpath,
        )
        elem.text = value


def validate_xml_with_xsd(xml_tree: etree._ElementTree, xsd_file: Optional[Path]) -> None:
    if not xsd_file:
        return
    schema_doc = etree.parse(str(xsd_file))
    schema = etree.XMLSchema(schema_doc)
    if not schema.validate(xml_tree):
        errors = [str(e) for e in schema.error_log]
        raise ValueError(f"XML failed XSD validation: {'; '.join(errors)}")

