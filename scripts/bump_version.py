#!/usr/bin/env python3
"""
Bump FileProcessor release version in file_processor/version.py (single source of truth).

Usage:
  python scripts/bump_version.py              # show current version
  python scripts/bump_version.py patch        # 0.1.0 -> 0.1.1
  python scripts/bump_version.py minor        # 0.1.0 -> 0.2.0
  python scripts/bump_version.py major        # 0.1.0 -> 1.0.0
  python scripts/bump_version.py set 1.2.3
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "file_processor" / "version.py"
_VERSION_RE = re.compile(r'^(__version__\s*=\s*["\'])([^"\']+)(["\']\s*)$', re.M)


def read_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        raise SystemExit(f"Could not parse __version__ in {VERSION_FILE}")
    return match.group(2)


def write_version(version: str) -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    new_text, n = _VERSION_RE.subn(rf'\g<1>{version}\g<3>', text, count=1)
    if n != 1:
        raise SystemExit(f"Could not update __version__ in {VERSION_FILE}")
    VERSION_FILE.write_text(new_text, encoding="utf-8")


def parse_semver(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise SystemExit(f"Version must be semver MAJOR.MINOR.PATCH, got {version!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump(part: str, current: str) -> str:
    major, minor, patch = parse_semver(current)
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise SystemExit(f"Unknown bump part: {part!r}")
    return f"{major}.{minor}.{patch}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump FileProcessor release version.")
    parser.add_argument(
        "action",
        nargs="?",
        choices=("patch", "minor", "major", "set"),
        help="Bump part or 'set' with explicit version",
    )
    parser.add_argument("value", nargs="?", help="Explicit version when action is 'set'")
    args = parser.parse_args()

    current = read_version()
    if args.action is None:
        print(current)
        return 0

    if args.action == "set":
        if not args.value:
            print("Usage: bump_version.py set MAJOR.MINOR.PATCH", file=sys.stderr)
            return 2
        new_version = args.value
        parse_semver(new_version)
    else:
        new_version = bump(args.action, current)

    write_version(new_version)
    print(f"{current} -> {new_version}")
    print(f"Updated {VERSION_FILE.relative_to(ROOT)}")
    print("Next: commit, tag (git tag v{new_version}), rebuild bundles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
