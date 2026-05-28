from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


def _fix_windows_dot_before_drive_letter(path: Path) -> Path:
    """
    YAML typo: '.E:\\dir' instead of 'E:\\dir'. Without this, pathlib treats the
    path as relative (component '.E:') and resolve() prepends the cwd, yielding
    WinError 123 on mkdir.
    """
    s = str(path)
    if os.name == "nt" and re.match(r"^\.[A-Za-z]:", s):
        return Path(s[1:])
    return path


SourceFormat = Literal["csv", "fixed_width"]
FlowMode = Literal["csv_to_xml", "xml_to_csv"]
XmlLineOutput = Literal["multi_row_file", "file_per_line"]


class RowFilter(BaseModel):
    """Simple row filter on a single column value."""

    column_index: int = Field(..., description="1-based index of the CSV column to inspect (1-based).")
    operator: Literal["eq", "in"] = Field(
        "eq", description="Comparison operator: 'eq' (equals) or 'in' (value in comma-separated list)."
    )
    value: str = Field(..., description="Comparison value or comma-separated values for 'in'.")


class GroupingRule(BaseModel):
    """Defines how to group CSV rows into one XML document (csv_to_xml)."""

    group_by_column_index: int = Field(
        ..., description="1-based CSV column index used as grouping key."
    )
    group_root_xpath: str = Field(
        ...,
        description="XPath to the repeating group node that represents one group (e.g. /Root/Order).",
    )
    item_xpath: str = Field(
        ...,
        description="XPath to the repeating item node for each source row inside the group.",
    )


class FixedWidthColumn(BaseModel):
    """Column specification for fixed-width files."""

    start: int = Field(..., description="1-based start position of the field in the line.")
    length: int = Field(..., description="Length of the field.")


class FlowConfig(BaseModel):
    """
    Configuration for a single flow.

    This is the core building block used by the FlowRegistry. It encapsulates:
    - Directories (input, success, error, archive, optional in_progress)
    - File format and direction (CSV/XML, fixed-width vs delimited)
    - Mapping XLS file and optional XSD schema
    - Optional row filters and grouping rules
    """

    name: str

    # Mode & formats
    mode: FlowMode = "csv_to_xml"
    input_format: SourceFormat = "csv"
    delimiter: str = ";"  # relevant for CSV

    # Directories
    input_dir: Path
    success_dir: Path
    error_dir: Path
    archive_dir: Path
    in_progress_dir: Optional[Path] = None

    file_glob: str = "*.csv"

    # Mapping, skeleton & schema
    mapping_file: Path = Field(
        ..., description="Path to mapping definition; for now this is expected to be an XLS file."
    )
    mapping_sheet_name: Optional[str] = Field(
        None,
        description="Optional sheet name in the mapping XLS. If omitted, the first sheet is used.",
    )
    skeleton_xml: Optional[Path] = Field(
        None,
        description="Optional path to an XML skeleton template used as the base document for csv_to_xml.",
    )
    xsd_file: Optional[Path] = Field(
        None, description="Optional XSD file to validate generated XML when in csv_to_xml mode."
    )

    # XML root
    root_element_name: str = "Root"

    # Fixed-width layout (when input_format == 'fixed_width')
    fixed_width_columns: list[FixedWidthColumn] = Field(default_factory=list)

    # Filtering and grouping
    filters: list[RowFilter] = Field(default_factory=list)
    grouping: Optional[GroupingRule] = None

    # xml_to_csv: repeating line items (e.g. BodyEadEsad)
    xml_line_xpath: Optional[str] = Field(
        None,
        description=(
            "For xml_to_csv: local name or path of repeating line items. "
            "Header-level mapping columns are repeated; line-level columns come from each item."
        ),
    )
    xml_line_output: XmlLineOutput = Field(
        "file_per_line",
        description=(
            "When xml_line_xpath is set: file_per_line = one CSV per line item "
            "(filename suffix from xml_line_filename_element); "
            "multi_row_file = one CSV with multiple rows."
        ),
    )
    xml_line_filename_element: Optional[str] = Field(
        "ExciseProductCode",
        description=(
            "Local element name under each line item used in the output CSV filename. "
            "Falls back to BodyRecordUniqueReference, then line index."
        ),
    )

    @field_validator(
        "input_dir",
        "success_dir",
        "error_dir",
        "archive_dir",
        "in_progress_dir",
        "mapping_file",
        "skeleton_xml",
        "xsd_file",
    )
    @classmethod
    def _expand_paths(cls, v: Optional[Path]) -> Optional[Path]:
        if v is None:
            return None
        v = _fix_windows_dot_before_drive_letter(v)
        return v.expanduser().resolve()


class FlowRegistry(BaseModel):
    """
    Top-level configuration containing multiple flows.

    This corresponds to the main YAML file (e.g. config/flows.yaml).
    """

    flows: list[FlowConfig]

    @classmethod
    def from_yaml(cls, path: Path) -> "FlowRegistry":
        """Load a YAML file and validate into a FlowRegistry."""
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)


