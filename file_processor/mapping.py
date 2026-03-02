from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from openpyxl import load_workbook


TransformFunc = Callable[[str], str]


@dataclass
class MappingEntry:
    """Single mapping from a source CSV column or constant to an XML XPath."""

    source_column_index: int | None  # 1-based; None means use constant_value
    target_xpath: str
    transform_name: str | None = None
    constant_value: str | None = None


@dataclass
class Mapping:
    """In-memory representation of all mappings from XLS."""

    entries: list[MappingEntry]


def load_mapping_from_xls(path: Path) -> Mapping:
    """
    Load mapping definition from an XLS file.

    Convention (first sheet, from row 2 onward):
    - Column 1: source column index (1-based). Empty or 0 -> constant or derived.
    - Column 2: target XPath.
    - Column 3: optional transform rule name.
    - Column 4: optional constant value.
    """
    wb = load_workbook(path, data_only=True)
    ws = wb.worksheets[0]

    entries: list[MappingEntry] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        source_idx_raw, xpath_raw, transform_raw, constant_raw = (row + (None, None, None, None))[:4]
        if xpath_raw is None:
            # Skip empty rows
            continue

        source_index: Optional[int] = None
        if source_idx_raw not in (None, "", 0):
            try:
                source_index = int(source_idx_raw)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid source column index in mapping XLS: {source_idx_raw!r}")

        entry = MappingEntry(
            source_column_index=source_index,
            target_xpath=str(xpath_raw).strip(),
            transform_name=(str(transform_raw).strip() if transform_raw not in (None, "") else None),
            constant_value=(str(constant_raw) if constant_raw not in (None, "") else None),
        )
        entries.append(entry)

    return Mapping(entries=entries)

