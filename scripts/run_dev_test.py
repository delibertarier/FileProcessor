#!/usr/bin/env python3
"""
Reset local data/, copy example inputs, and run all flows once (dev smoke test).

Usage (from repo root, with venv activated or .venv/bin/python):
  python scripts/run_dev_test.py
  python scripts/run_dev_test.py -v
  python scripts/run_dev_test.py --skip-run          # purge + copy only
  python scripts/run_dev_test.py --outbound-only

Exits 0 when no files remain in error dirs; 1 if any landed in error/.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CONFIG = ROOT / "config" / "flows.yaml"
DATA_ROOT = ROOT / "data"

OUTBOUND_EXAMPLES = ROOT / "examples" / "out"
INBOUND_SSW_EXAMPLES = ROOT / "examples" / "in" / "SSW"
INBOUND_EMCS_EXAMPLES = ROOT / "examples" / "in" / "EMCS"


def _purge_data(data_root: Path) -> int:
    """Remove all files under data/ except .gitkeep."""
    removed = 0
    if not data_root.exists():
        return 0
    for path in sorted(data_root.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()
            removed += 1
    return removed


def _copy_glob(src_dir: Path, pattern: str, dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for src in sorted(src_dir.glob(pattern)):
        if not src.is_file():
            continue
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


def _seed_examples(*, outbound: bool, inbound: bool) -> dict[str, list[Path]]:
    seeded: dict[str, list[Path]] = {"outbound": [], "inbound": []}

    if outbound:
        seeded["outbound"] = _copy_glob(
            OUTBOUND_EXAMPLES,
            "TRA*.TXT",
            DATA_ROOT / "outbound" / "in",
        )

    if inbound:
        inbound_in = DATA_ROOT / "inbound" / "in"
        seeded["inbound"].extend(
            _copy_glob(INBOUND_SSW_EXAMPLES, "TE_FELUY_*.xml", inbound_in)
        )
        seeded["inbound"].extend(
            _copy_glob(INBOUND_EMCS_EXAMPLES, "ARC_ALL*.xml", inbound_in)
        )

    return seeded


def _list_files(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return sorted(p for p in dir_path.iterdir() if p.is_file() and p.name != ".gitkeep")


def _print_results() -> int:
    """Print summary; return non-zero if anything landed in error dirs."""
    errors = 0
    sections = (
        ("Outbound input (remaining)", DATA_ROOT / "outbound" / "in"),
        ("Outbound success", DATA_ROOT / "outbound" / "success"),
        ("Outbound error", DATA_ROOT / "outbound" / "error"),
        ("Outbound archive", DATA_ROOT / "outbound" / "archive"),
        ("Inbound input (remaining)", DATA_ROOT / "inbound" / "in"),
        ("Inbound success", DATA_ROOT / "inbound" / "success"),
        ("Inbound error", DATA_ROOT / "inbound" / "error"),
        ("Inbound archive", DATA_ROOT / "inbound" / "archive"),
    )
    print("\n--- Results ---")
    for label, path in sections:
        files = _list_files(path)
        print(f"{label}: {len(files)} file(s)")
        for f in files:
            print(f"  {f.name}")
        if "error" in label.lower() and files:
            errors += len(files)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Purge data/, copy example files, and run FileProcessor once."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"flows.yaml path (default: {DEFAULT_CONFIG.relative_to(ROOT)})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--skip-purge", action="store_true", help="Do not clear data/")
    parser.add_argument("--skip-copy", action="store_true", help="Do not copy from examples/")
    parser.add_argument("--skip-run", action="store_true", help="Purge and copy only")
    parser.add_argument("--outbound-only", action="store_true", help="Only outbound examples + flows")
    parser.add_argument("--inbound-only", action="store_true", help="Only inbound examples + flows")
    args = parser.parse_args()

    if args.outbound_only and args.inbound_only:
        print("Cannot use --outbound-only and --inbound-only together.", file=sys.stderr)
        return 2

    do_outbound = not args.inbound_only
    do_inbound = not args.outbound_only

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 2

    if not args.skip_purge:
        n = _purge_data(DATA_ROOT)
        print(f"Purged {n} file(s) under {DATA_ROOT.relative_to(ROOT)}/")

    if not args.skip_copy:
        seeded = _seed_examples(outbound=do_outbound, inbound=do_inbound)
        print(f"Copied {len(seeded['outbound'])} outbound file(s) → data/outbound/in/")
        for p in seeded["outbound"]:
            print(f"  {p.name}")
        print(f"Copied {len(seeded['inbound'])} inbound file(s) → data/inbound/in/")
        for p in seeded["inbound"]:
            print(f"  {p.name}")

    if args.skip_run:
        return 0

    # Flow paths in config are relative to cwd — run from repo root.
    import os

    os.chdir(ROOT)

    from file_processor.config import FlowRegistry  # noqa: E402
    from file_processor.runner import FlowRunner

    registry = FlowRegistry.from_yaml(config_path)
    if args.outbound_only:
        registry.flows = [f for f in registry.flows if f.mode == "csv_to_xml"]
    elif args.inbound_only:
        registry.flows = [f for f in registry.flows if f.mode == "xml_to_csv"]

    print(f"\nRunning {len(registry.flows)} flow(s) from {config_path.relative_to(ROOT)}...")
    FlowRunner(registry).run_all_pending()

    return _print_results()


if __name__ == "__main__":
    sys.exit(main())
