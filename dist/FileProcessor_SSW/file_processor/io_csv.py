from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Dict

from .config import FlowConfig


def read_csv_rows(path: Path, delimiter: str) -> List[Dict[int, str]]:
    """Read a delimited CSV file into a list of 1-based index -> value dictionaries."""
    rows: list[dict[int, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            index_map = {i + 1: (cell or "") for i, cell in enumerate(row)}
            rows.append(index_map)
    return rows


def read_fixed_width_rows(path: Path, flow: FlowConfig) -> List[Dict[int, str]]:
    """
    Read a fixed-width file according to the flow's fixed_width_columns specification.

    Each line is sliced into columns based on 1-based start and length, then mapped to
    1-based column indices for compatibility with the mapping XLS.
    """
    if not flow.fixed_width_columns:
        raise ValueError("fixed_width_columns must be configured for fixed_width input_format.")

    rows: list[dict[int, str]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            row: dict[int, str] = {}
            for idx, col in enumerate(flow.fixed_width_columns, start=1):
                start = col.start - 1
                end = start + col.length
                value = line[start:end].rstrip("\n")
                row[idx] = value.rstrip()
            rows.append(row)
    return rows

