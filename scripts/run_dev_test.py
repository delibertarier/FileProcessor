#!/usr/bin/env python3
"""
Reset local data/, copy example inputs, and run all flows once (dev smoke test).

Copies only files from examples/ that match each flow's file_glob in config/flows.yaml.

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
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for p in (ROOT, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DEFAULT_CONFIG = ROOT / "config" / "flows.yaml"
DATA_ROOT = ROOT / "data"
EXAMPLES_ROOT = ROOT / "examples"


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


def _load_registry(config_path: Path, *, outbound_only: bool, inbound_only: bool):
    import os

    os.chdir(ROOT)
    from file_processor.config import FlowRegistry

    registry = FlowRegistry.from_yaml(config_path)
    if outbound_only:
        registry.flows = [f for f in registry.flows if f.mode == "csv_to_xml"]
    elif inbound_only:
        registry.flows = [f for f in registry.flows if f.mode == "xml_to_csv"]
    return registry


def _print_seed_report(copied: list[tuple[str, Path, Path]]) -> None:
    by_flow: dict[str, list[Path]] = {}
    for flow_name, _src, dest in copied:
        by_flow.setdefault(flow_name, []).append(dest)
    for flow_name, dests in by_flow.items():
        print(f"  [{flow_name}] {len(dests)} file(s)")
        for dest in dests:
            print(f"    {dest.name}")


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
    if errors:
        print(f"\n{errors} file(s) in error/ — see paths above.")
    else:
        from file_processor.version import __version__

        print(f"\nAll good — every example processed with nothing in error/ (v{__version__}).")
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

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 2

    registry = _load_registry(
        config_path,
        outbound_only=args.outbound_only,
        inbound_only=args.inbound_only,
    )

    if not args.skip_purge:
        n = _purge_data(DATA_ROOT)
        print(f"Purged {n} file(s) under {DATA_ROOT.relative_to(ROOT)}/")

    if not args.skip_copy:
        from test_seed_examples import seed_flows

        copied = seed_flows(registry, EXAMPLES_ROOT)
        print(f"Copied {len(copied)} example file(s) (per flow file_glob in {config_path.name}):")
        _print_seed_report(copied)

    if args.skip_run:
        return 0

    from file_processor.runner import FlowRunner

    print(f"\nRunning {len(registry.flows)} flow(s) from {config_path.relative_to(ROOT)}...")
    FlowRunner(registry).run_all_pending()

    return _print_results()


if __name__ == "__main__":
    sys.exit(main())
