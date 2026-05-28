"""Copy example inputs into flow input_dir using each flow's file_glob."""

from __future__ import annotations

import shutil
from pathlib import Path

EXAMPLES_SUBDIR_OUT = "out"
EXAMPLES_SUBDIR_IN = "in"


def _example_search_dirs(flow, examples_root: Path) -> list[Path]:
    if flow.mode == "csv_to_xml":
        out_dir = examples_root / EXAMPLES_SUBDIR_OUT
        return [out_dir] if out_dir.is_dir() else []

    in_dir = examples_root / EXAMPLES_SUBDIR_IN
    if not in_dir.is_dir():
        return []
    dirs: list[Path] = [in_dir]
    dirs.extend(sorted(p for p in in_dir.iterdir() if p.is_dir()))
    return dirs


def find_example_files(flow, examples_root: Path) -> list[Path]:
    """Example files under examples/ matching this flow's file_glob."""
    pattern = (flow.file_glob or "*.*").strip()
    by_name: dict[str, Path] = {}
    for base in _example_search_dirs(flow, examples_root):
        for path in sorted(base.glob(pattern)):
            if path.is_file():
                by_name[path.name.lower()] = path
    return sorted(by_name.values(), key=lambda p: p.name.lower())


def seed_flows(registry, examples_root: Path) -> list[tuple[str, Path, Path]]:
    """
    Copy examples for each configured flow into its input_dir.

    Returns (flow_name, source, destination) for each copied file.
    """
    copied: list[tuple[str, Path, Path]] = []
    seen_dest: set[tuple[str, str]] = set()

    for flow in registry.flows:
        dest_dir = Path(flow.input_dir)
        for src in find_example_files(flow, examples_root):
            key = (str(dest_dir.resolve()), src.name.lower())
            if key in seen_dest:
                continue
            seen_dest.add(key)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            shutil.copy2(src, dest)
            copied.append((flow.name, src, dest))

    return copied
