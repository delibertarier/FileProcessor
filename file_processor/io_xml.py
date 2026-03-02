from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from lxml import etree

from .mapping import Mapping


def parse_xml_tree(path: Path) -> etree._ElementTree:
    """Parse an XML file into an lxml ElementTree."""
    return etree.parse(str(path))


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

    for entry in mapping.entries:
        if entry.source_column_index is None:
            # Constants don't participate in XML->CSV for now.
            continue

        nodes = root.xpath(entry.target_xpath)
        if not nodes:
            value = ""
        else:
            node = nodes[0]
            # node can be element or attribute value
            if isinstance(node, str):
                value = node
            else:
                value = (node.text or "").strip()

        row[entry.source_column_index] = value

    return [row]

