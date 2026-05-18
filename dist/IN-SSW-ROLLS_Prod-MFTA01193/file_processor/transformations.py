from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional

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


def extract_date(value: str) -> str:
    """Extract date part from datetime-like input (e.g. 2022-01-17T10:55:11)."""
    dt = date_parser.parse(value)
    return dt.date().isoformat()


def extract_time(value: str) -> str:
    """Extract time part from datetime-like input (e.g. 2022-01-17T10:55:11)."""
    dt = date_parser.parse(value)
    return dt.strftime("%H:%M:%S")


def make_replace_transform(spec: str) -> Callable[[str], str]:
    """
    Build a substring-replace transform from the part after ``replace:``.

    Syntax (column F): ``replace:old1=new1,old2=new2``
    Pairs are comma-separated; each pair uses the first ``=`` as delimiter.
    Rules are applied in order; every occurrence of each ``old`` is replaced.
    """
    rules: list[tuple[str, str]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        old, new = part.split("=", 1)
        rules.append((old, new))

    def replacer(value: str, _rules: list[tuple[str, str]] = rules) -> str:
        result = value
        for old, new in _rules:
            result = result.replace(old, new)
        return result

    return replacer


def resolve_transform(name: Optional[str]) -> Callable[[str], str]:
    """
    Resolve a transform by name for csv_to_xml and xml_to_csv.

    - Static names in TRANSFORMATIONS (e.g. strip, extract_date)
    - ``first_<N>`` — first N characters
    - ``replace:old=new,...`` — one or more substring replacements
    """
    if not name:
        return identity

    func = TRANSFORMATIONS.get(name)
    if func:
        return func

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

    if name.startswith("replace:"):
        return make_replace_transform(name.removeprefix("replace:"))

    return identity


TRANSFORMATIONS: Dict[str, Callable[[str], str]] = {
    "identity": identity,
    "strip": strip,
    "to_iso_date": to_iso_date,
    "to_iso_time": to_iso_time,
    "to_iso_datetime": to_iso_datetime,
    "date_dd_mm_yyyy": date_dd_mm_yyyy,
    "date_yyyy_mm_dd": date_yyyy_mm_dd,
    "extract_date": extract_date,
    "extract_time": extract_time,
}

