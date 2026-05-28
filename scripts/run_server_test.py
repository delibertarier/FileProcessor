#!/usr/bin/env python3
"""
Smoke-test FileProcessor on a Windows **test** server using paths from config/flows.yaml.

Copies bundled examples into the flow input_dir folders, runs all flows once, and
reports success/error/archive counts. Refuses to run when paths look like production.

Run from the deployment bundle root (where config/flows.yaml lives), e.g.:

  py scripts\\run_server_test.py
  py scripts\\run_server_test.py -v
  py scripts\\run_server_test.py --dry-run
  py scripts\\run_server_test.py --skip-purge --skip-copy

Does not purge archive_dir unless --purge-archive is passed.
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for p in (ROOT, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

DEFAULT_CONFIG = ROOT / "config" / "flows.yaml"
EXAMPLES_ROOT = ROOT / "examples"

FLOW_WORK_DIRS = ("input_dir", "success_dir", "error_dir", "in_progress_dir")


def _path_looks_like_production(path: str) -> bool:
    """
    True when path is under production FTP (E:\\FTP\\AMFT\\...) not test (AMFT_Test).
    """
    upper = path.replace("/", "\\").upper()
    if "AMFT_TEST" in upper:
        return False
    if re.search(r"\\FTP\\AMFT\\", upper):
        return True
    return False


def _assert_test_environment(flow_paths: list[tuple[str, str]]) -> None:
    prod = [(name, key, p) for name, key, p in flow_paths if _path_looks_like_production(p)]
    if prod:
        print("Refusing to run: config paths look like PRODUCTION, not test.", file=sys.stderr)
        print("This script is only for test FTP folders (AMFT_Test).", file=sys.stderr)
        for name, key, p in prod:
            print(f"  flow {name!r} {key}: {p}", file=sys.stderr)
        sys.exit(2)


def _collect_flow_dirs(registry, *, include_archive: bool) -> list[tuple[str, Path]]:
    """Unique (label, path) dirs across all flows."""
    seen: set[Path] = set()
    items: list[tuple[str, Path]] = []
    keys = list(FLOW_WORK_DIRS) + (["archive_dir"] if include_archive else [])
    for flow in registry.flows:
        for key in keys:
            path = getattr(flow, key, None)
            if path is None:
                continue
            resolved = Path(path)
            if resolved in seen:
                continue
            seen.add(resolved)
            label = f"{flow.name} / {key}"
            items.append((label, resolved))
    return items


def _purge_dir(dir_path: Path) -> int:
    if not dir_path.exists():
        return 0
    removed = 0
    for item in dir_path.iterdir():
        if item.is_file():
            item.unlink()
            removed += 1
        elif item.is_dir():
            shutil.rmtree(item)
            removed += 1
    return removed


def _copy_glob(src_dir: Path, pattern: str, dest_dir: Path) -> list[Path]:
    if not src_dir.is_dir():
        return []
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for src in sorted(src_dir.glob(pattern)):
        if not src.is_file():
            continue
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


def _seed_flow(flow) -> list[Path]:
    from test_seed_examples import find_example_files

    dest_dir = Path(flow.input_dir)
    copied: list[Path] = []
    for src in find_example_files(flow, EXAMPLES_ROOT):
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        copied.append(dest)
    return copied


def _list_files(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return sorted(p for p in dir_path.iterdir() if p.is_file())


def _confirm(message: str, *, force: bool) -> bool:
    if force:
        return True
    if not sys.stdin.isatty():
        print(f"{message} Use --force to proceed without prompting.", file=sys.stderr)
        return False
    reply = input(f"{message} [y/N]: ").strip().lower()
    return reply in ("y", "yes")


def _print_results(registry, *, include_archive: bool) -> int:
    errors = 0
    print("\n--- Results ---")
    for flow in registry.flows:
        print(f"\nFlow: {flow.name} ({flow.mode})")
        sections = [
            ("input (remaining)", flow.input_dir),
            ("success", flow.success_dir),
            ("error", flow.error_dir),
        ]
        if include_archive:
            sections.append(("archive", flow.archive_dir))
        for label, path in sections:
            files = _list_files(Path(path))
            print(f"  {label}: {len(files)} file(s)")
            for f in files:
                print(f"    {f.name}")
            if label == "error" and files:
                errors += len(files)
    if errors:
        print(f"\n{errors} file(s) in error/ — see paths above.")
    else:
        from file_processor.version import __version__

        print(f"\nAll good — test run finished with nothing in error/ (v{__version__}).")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test FileProcessor on test FTP paths from config/flows.yaml."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="flows.yaml (default: config/flows.yaml in bundle root)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show paths and actions only; do not purge, copy, or process.",
    )
    parser.add_argument("--skip-purge", action="store_true")
    parser.add_argument("--skip-copy", action="store_true")
    parser.add_argument("--skip-run", action="store_true")
    parser.add_argument(
        "--purge-archive",
        action="store_true",
        help="Also empty archive_dir (default: leave archive untouched).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation before purging FTP folders.",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 2

    import os

    os.chdir(ROOT)

    from file_processor.config import FlowRegistry
    from file_processor.runner import FlowRunner

    registry = FlowRegistry.from_yaml(config_path)
    if not registry.flows:
        print("No flows in config.", file=sys.stderr)
        return 2

    flow_paths = [
        (flow.name, key, str(getattr(flow, key)))
        for flow in registry.flows
        for key in (*FLOW_WORK_DIRS, "archive_dir")
        if getattr(flow, key, None)
    ]
    _assert_test_environment(flow_paths)

    purge_dirs = _collect_flow_dirs(registry, include_archive=args.purge_archive)

    print(f"Bundle root: {ROOT}")
    print(f"Config: {config_path.relative_to(ROOT)}")
    print(f"Flows: {len(registry.flows)}")
    for flow in registry.flows:
        print(f"  - {flow.name} ({flow.mode}) input={flow.input_dir}")

    if args.dry_run:
        print("\n[dry-run] Would purge:")
        for label, path in purge_dirs:
            n = len(_list_files(path))
            print(f"  {path} ({n} file(s) now) — {label}")
        print("\n[dry-run] Would copy examples → input_dir per flow:")
        from test_seed_examples import find_example_files

        for flow in registry.flows:
            matches = find_example_files(flow, EXAMPLES_ROOT)
            print(f"  {flow.name}: {flow.file_glob!r} → {flow.input_dir} ({len(matches)} file(s))")
            for path in matches:
                print(f"    {path.name}")
        if not args.skip_run:
            print("\n[dry-run] Would run FlowRunner.run_all_pending()")
        return 0

    if not args.skip_purge:
        if not _confirm(
            f"Clear {len(purge_dirs)} test folder(s) (input/success/error/in_progress"
            + (", archive" if args.purge_archive else "")
            + ")?",
            force=args.force,
        ):
            print("Aborted.")
            return 1
        total = 0
        for label, path in purge_dirs:
            n = _purge_dir(path)
            total += n
            print(f"Purged {n} item(s) from {path}  ({label})")
        print(f"Purged {total} item(s) total.")

    if not args.skip_copy:
        for flow in registry.flows:
            copied = _seed_flow(flow)
            print(f"Copied {len(copied)} file(s) for {flow.name} → {flow.input_dir}")
            for p in copied:
                print(f"  {p.name}")

    if args.skip_run:
        return 0

    print(f"\nRunning {len(registry.flows)} flow(s)...")
    FlowRunner(registry).run_all_pending()
    return _print_results(registry, include_archive=args.purge_archive)


if __name__ == "__main__":
    sys.exit(main())
