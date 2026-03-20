from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from lxml import etree

from .config import FlowConfig, FlowRegistry, RowFilter
from .io_csv import read_csv_rows, read_fixed_width_rows
from .io_xml import parse_xml_tree, xml_to_row_dicts
from .mapping import load_mapping_from_xls
from .xml_builder import build_xml_for_group, validate_xml_with_xsd

logger = logging.getLogger(__name__)


def _matches_filters(row: dict[int, str], filters: Iterable[RowFilter]) -> bool:
    for flt in filters:
        value = row.get(flt.column_index, "")
        if flt.operator == "eq":
            if value != flt.value:
                return False
        elif flt.operator == "in":
            allowed = {v.strip() for v in flt.value.split(",")}
            if value not in allowed:
                return False
        else:
            raise ValueError(f"Unsupported operator: {flt.operator}")
    return True


def process_file_for_flow(flow: FlowConfig, file_path: Path) -> None:
    logger.info("Processing file %s for flow %s", file_path, flow.name)

    mapping = load_mapping_from_xls(flow.mapping_file)

    # Branch on mode: csv_to_xml vs xml_to_csv
    if flow.mode == "csv_to_xml":
        if flow.input_format == "csv":
            rows = read_csv_rows(file_path, delimiter=flow.delimiter)
        elif flow.input_format == "fixed_width":
            rows = read_fixed_width_rows(file_path, flow)
        else:
            raise NotImplementedError(f"Unsupported input_format for csv_to_xml: {flow.input_format}")
        _process_rows_csv_to_xml(flow, mapping, file_path, rows)
    elif flow.mode == "xml_to_csv":
        xml_tree = parse_xml_tree(file_path)
        rows = xml_to_row_dicts(mapping, xml_tree)
        _write_csv_output(flow, file_path, rows)
    else:
        raise NotImplementedError(f"Unsupported flow mode: {flow.mode}")


def _process_rows_csv_to_xml(flow: FlowConfig, mapping, file_path: Path, rows: list[dict[int, str]]) -> None:
    logger.debug("Read %d rows from %s", len(rows), file_path)

    # Apply row filters
    if flow.filters:
        rows = [r for r in rows if _matches_filters(r, flow.filters)]
        logger.debug("After filtering, %d rows remain", len(rows))

    if not rows:
        logger.info("No rows to process after filtering; skipping file.")
        return

    # Group rows if requested
    if flow.grouping:
        groups: dict[str, list[dict[int, str]]] = defaultdict(list)
        key_col = flow.grouping.group_by_column_index
        for row in rows:
            key = row.get(key_col, "")
            groups[key].append(row)

        for key, group_rows in groups.items():
            xml_tree = build_xml_for_group(flow, mapping, group_rows, group_key=key)
            try:
                validate_xml_with_xsd(xml_tree, flow.xsd_file)
            except Exception:
                # On validation or other errors, still persist XML alongside the CSV in the error folder.
                _write_xml_error_output(flow, file_path, xml_tree, suffix=f"_{key}")
                raise
            _write_xml_output(flow, file_path, xml_tree, suffix=f"_{key}")
    else:
        # No grouping: each CSV row should produce its own XML document.
        for idx, row in enumerate(rows, start=1):
            xml_tree = build_xml_for_group(flow, mapping, [row], group_key=None)
            try:
                validate_xml_with_xsd(xml_tree, flow.xsd_file)
            except Exception:
                # On validation or other errors, still persist XML alongside the CSV in the error folder.
                _write_xml_error_output(flow, file_path, xml_tree, suffix=f"_{idx:04d}")
                raise
            _write_xml_output(flow, file_path, xml_tree, suffix=f"_{idx:04d}")


def _write_xml_output(flow: FlowConfig, source_file: Path, xml_tree: etree._ElementTree, suffix: str = ""):
    """Write successful XML results to the flow's success_dir."""
    _write_xml_output_to_dir(flow.success_dir, source_file, xml_tree, suffix)


def _write_xml_error_output(flow: FlowConfig, source_file: Path, xml_tree: etree._ElementTree, suffix: str = ""):
    """
    Write XML that failed validation/processing next to the CSV in the error_dir.
    The TransactionManager will move the CSV there; this writes the XML directly.
    """
    _write_xml_output_to_dir(flow.error_dir, source_file, xml_tree, suffix)


def _strip_whitespace_only_text_tail(root: etree._Element) -> None:
    """Remove whitespace-only .text and .tail so pretty_print can apply uniform indentation."""
    for elem in root.iter():
        if elem.text is not None and not elem.text.strip():
            elem.text = None
        if elem.tail is not None and not elem.tail.strip():
            elem.tail = None


def _write_xml_output_to_dir(
    target_dir: Path, source_file: Path, xml_tree: etree._ElementTree, suffix: str = ""
) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    base_name = source_file.stem + suffix + ".xml"
    target_path = target_dir / base_name
    _strip_whitespace_only_text_tail(xml_tree.getroot())
    xml_tree.write(str(target_path), encoding="utf-8", xml_declaration=True, pretty_print=True)
    logger.info("Wrote XML output to %s", target_path)


def _write_csv_output(flow: FlowConfig, source_file: Path, rows: list[dict[int, str]]) -> None:
    """
    Write XML->CSV transformation results to the flow's success_dir.

    For now, we emit one CSV file per XML file, with as many rows as produced
    by xml_to_row_dicts, without a header line.
    """
    import csv

    flow.success_dir.mkdir(parents=True, exist_ok=True)
    base_name = source_file.stem + ".csv"
    target_path = flow.success_dir / base_name

    if not rows:
        logger.info("No rows produced for XML->CSV; writing empty file to %s", target_path)
        target_path.write_text("", encoding="utf-8")
        return

    # Determine max column index to keep stable ordering
    max_col = max(max(row.keys(), default=0) for row in rows)

    with target_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=flow.delimiter)
        for row in rows:
            writer.writerow([row.get(i, "") for i in range(1, max_col + 1)])

    logger.info("Wrote CSV output to %s", target_path)


def process_all_pending_files(registry: FlowRegistry) -> None:
    """
    Batch-style processing: for each flow, process all files currently in the input directory.
    After successful processing, move files to archive; on error, move to error directory.
    """
    for flow in registry.flows:
        for path in sorted(flow.input_dir.glob(flow.file_glob)):
            try:
                process_file_for_flow(flow, path)
            except Exception as exc:
                logger.exception("Error processing %s for flow %s", path, flow.name)
                _move_safely(path, flow.error_dir)
            else:
                # Move original input file to archive on success
                _move_safely(path, flow.archive_dir)


def _move_safely(source: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / source.name
    source.rename(target_path)

