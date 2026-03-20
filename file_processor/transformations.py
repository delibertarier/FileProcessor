from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict

from dateutil import parser as date_parser


def identity(value: str) -> str:
    return value


def strip(value: str) -> str:
    return value.strip()


def to_iso_date(value: str) -> str:
    """Parse a date in a flexible way and output ISO-8601 date (YYYY-MM-DD)."""
    dt = date_parser.parse(value)
    return dt.date().isoformat()


def to_iso_time(value: str) -> str:
    """Parse a time in a flexible way and output ISO-style time (HH:MM:SS)."""
    dt = date_parser.parse(value)
    return dt.strftime("%H:%M:%S")


def to_iso_datetime(value: str) -> str:
    """Parse date/time flexibly and output ISO-8601 datetime (YYYY-MM-DDTHH:MM:SS)."""
    dt = date_parser.parse(value)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def from_pattern_to_iso(value: str, pattern: str) -> str:
    """Generic: parse with strptime pattern and emit ISO date."""
    dt = datetime.strptime(value.strip(), pattern)
    return dt.date().isoformat()


def date_dd_mm_yyyy(value: str) -> str:
    """Parse DD-MM-YYYY or DD/MM/YYYY and output ISO date."""
    v = value.strip()
    for sep in ("-", "/", "."):
        if sep in v:
            parts = v.split(sep, 2)
            if len(parts) == 3 and len(parts[0]) <= 2 and len(parts[1]) <= 2 and len(parts[2]) == 4:
                try:
                    dt = datetime.strptime(v, f"%d{sep}%m{sep}%Y")
                    return dt.date().isoformat()
                except ValueError:
                    pass
    # Fallback: let dateutil try
    return to_iso_date(value)


def date_yyyy_mm_dd(value: str) -> str:
    """Parse YYYY-MM-DD (or with time) and output ISO date only."""
    dt = date_parser.parse(value)
    return dt.date().isoformat()


TRANSFORMATIONS: Dict[str, Callable[[str], str]] = {
    "identity": identity,
    "strip": strip,
    "to_iso_date": to_iso_date,
    "to_iso_time": to_iso_time,
    "to_iso_datetime": to_iso_datetime,
    "date_dd_mm_yyyy": date_dd_mm_yyyy,
    "date_yyyy_mm_dd": date_yyyy_mm_dd,
}

