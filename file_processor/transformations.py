from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict

from dateutil import parser as date_parser


def identity(value: str) -> str:
    return value


def strip(value: str) -> str:
    return value.strip()


def to_iso_date(value: str) -> str:
    """Parse a date in a flexible way and output ISO-8601 date."""
    dt = date_parser.parse(value)
    return dt.date().isoformat()


def from_pattern_to_iso(value: str, pattern: str) -> str:
    """Generic: parse with strptime pattern and emit ISO date."""
    dt = datetime.strptime(value, pattern)
    return dt.date().isoformat()


TRANSFORMATIONS: Dict[str, Callable[[str], str]] = {
    "identity": identity,
    "strip": strip,
    "to_iso_date": to_iso_date,
    # additional patterns can be registered here or dynamically in user code
}

