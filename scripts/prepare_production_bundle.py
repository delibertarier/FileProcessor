#!/usr/bin/env python3
"""
Build clean production deploy folder(s) with flows.yaml preset from production_paths.yaml.

Each deployment is a separate Windows app instance (test/prod × inbound/outbound).

Usage:
  cp config/production_paths.example.yaml config/production_paths.yaml
  python scripts/prepare_production_bundle.py --purge-local-data
  python scripts/prepare_production_bundle.py --deployment OUT-ROLLS-SSW_Prod-MFTA01192

Production FTP folders are never purged. --purge-local-data only affects ./data inside the bundle.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PATHS = ROOT / "config" / "production_paths.yaml"
EXAMPLE_PATHS = ROOT / "config" / "production_paths.example.yaml"

COPY_DIRS = ("file_processor", "examples", "offline", "config", "scripts")
COPY_FILES = (
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "INSTALL.md",
    "OPS_GUIDE.md",
    "WINDOWS_SERVICE_GUIDE.md",
)

SKIP_DIR_NAMES = {".git", ".venv", "__pycache__", ".egg-info", "dist", ".cursor"}
SKIP_FILE_PATTERNS = (
    re.compile(r"^~\$"),
    re.compile(r"\.pyc$"),
    re.compile(r"^\.DS_Store$"),
)

def _load_production_config() -> dict:
    path = PRODUCTION_PATHS if PRODUCTION_PATHS.exists() else EXAMPLE_PATHS
    if not path.exists():
        print(
            f"Missing {PRODUCTION_PATHS}. Copy {EXAMPLE_PATHS} and edit your paths.",
            file=sys.stderr,
        )
        sys.exit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _yaml_path(p: str) -> str:
    if "\\" in p or ":" in p:
        return "'" + p.replace("'", "''") + "'"
    return p


DIR_PATH_KEYS = (
    "input_dir",
    "success_dir",
    "error_dir",
    "archive_dir",
    "in_progress_dir",
)

DEPLOYMENT_EXAMPLES_DIR = ROOT / "scripts" / "deployment-examples"


def _load_source_flows(root_cfg: dict) -> dict[str, dict]:
    """Load flow definitions from config/flows.yaml (dev source of truth)."""
    rel = root_cfg.get("source_flows", "config/flows.yaml")
    path = ROOT / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    flows: dict[str, dict] = {}
    for entry in data.get("flows", []):
        name = entry.get("name")
        if not name:
            continue
        flows[name] = entry
    return flows


INBOUND_MODE = "xml_to_csv"
OUTBOUND_MODE = "csv_to_xml"


def _example_flows_path(example_name: str, examples_dir: Path | None = None) -> Path:
    base = examples_dir or DEPLOYMENT_EXAMPLES_DIR
    example_path = base / example_name / "flows.yaml"
    if not example_path.exists():
        raise FileNotFoundError(f"Deployment example not found: {example_path}")
    return example_path


def _read_example_first_flow(example_name: str, examples_dir: Path | None = None) -> dict:
    example_path = _example_flows_path(example_name, examples_dir)
    data = yaml.safe_load(example_path.read_text(encoding="utf-8"))
    entries = data.get("flows") or []
    if not entries:
        raise ValueError(f"No flows in deployment example {example_path}")
    return entries[0]


def _deployment_mode_from_example(example_name: str, examples_dir: Path | None = None) -> str:
    """
    Determine inbound vs outbound from the deployment example (test/prod server config).

    Prefer the mode on the first flow in the example flows.yaml; fall back to IN-/OUT- prefix.
    """
    first = _read_example_first_flow(example_name, examples_dir)
    mode = first.get("mode")
    if mode in (INBOUND_MODE, OUTBOUND_MODE):
        return mode

    upper = example_name.upper()
    if upper.startswith("IN-"):
        return INBOUND_MODE
    if upper.startswith("OUT-"):
        return OUTBOUND_MODE

    raise ValueError(
        f"Cannot determine direction for deployment example {example_name!r}. "
        f"Name should start with IN- or OUT-, or flows.yaml should set mode."
    )


def _read_dir_paths_from_example(example_name: str, examples_dir: Path | None = None) -> dict[str, str]:
    """
    Read IN/OUT/archive paths from scripts/deployment-examples/<name>/flows.yaml.
    Uses the first flow in that file (all flows on one instance share the same folders).
    """
    first = _read_example_first_flow(example_name, examples_dir)
    paths = {key: str(first[key]) for key in DIR_PATH_KEYS if first.get(key) not in (None, "")}
    if len(paths) != len(DIR_PATH_KEYS):
        example_path = _example_flows_path(example_name, examples_dir)
        missing = [k for k in DIR_PATH_KEYS if k not in paths]
        raise ValueError(f"Deployment example {example_path} missing path keys: {missing}")
    return paths


def _select_flow_names(
    source_flows: dict[str, dict],
    required_mode: str,
    explicit_names: list[str] | None,
    deployment_name: str,
) -> list[str]:
    """Pick flows from config/flows.yaml that match inbound (xml_to_csv) or outbound (csv_to_xml)."""
    matching = sorted(
        name for name, flow in source_flows.items() if flow.get("mode") == required_mode
    )

    if explicit_names:
        selected: list[str] = []
        for name in explicit_names:
            if name not in source_flows:
                available = ", ".join(sorted(source_flows))
                raise ValueError(
                    f"Deployment {deployment_name!r}: flow {name!r} not in source flows. "
                    f"Available: {available}"
                )
            actual_mode = source_flows[name].get("mode")
            if actual_mode != required_mode:
                raise ValueError(
                    f"Deployment {deployment_name!r}: flow {name!r} has mode {actual_mode!r}, "
                    f"but this target requires {required_mode!r} "
                    f"({'incoming' if required_mode == INBOUND_MODE else 'outgoing'})."
                )
            selected.append(name)
        return selected

    if not matching:
        raise ValueError(
            f"Deployment {deployment_name!r}: no flows with mode {required_mode!r} in source flows.yaml."
        )
    return matching


def _resolve_deployment(root_cfg: dict, name: str, deployment_cfg: dict) -> dict:
    """
    Build deployment config: flow settings from config/flows.yaml,
    directory paths from scripts/deployment-examples/<name>/flows.yaml.

    Incoming deployments (IN-* / xml_to_csv): only xml_to_csv flows from config.
    Outgoing deployments (OUT-* / csv_to_xml): only csv_to_xml flows from config.
    """
    merged = dict(deployment_cfg)
    example_name = merged.get("example", name)

    source_flows = _load_source_flows(root_cfg)
    required_mode = _deployment_mode_from_example(example_name)
    dir_paths = _read_dir_paths_from_example(example_name)

    explicit = merged.get("flow_names")
    if explicit is not None and not explicit:
        raise ValueError(f"Deployment {name!r}: flow_names is empty.")

    flow_names = _select_flow_names(source_flows, required_mode, explicit, name)

    built_flows: dict[str, dict] = {}
    for flow_name in flow_names:
        flow = dict(source_flows[flow_name])
        if flow.get("mode") != required_mode:
            raise ValueError(
                f"Deployment {name!r}: internal error, flow {flow_name!r} mode mismatch."
            )
        for key, value in dir_paths.items():
            flow[key] = value
        built_flows[flow_name] = flow

    merged["flows"] = built_flows
    merged["required_mode"] = required_mode
    merged["example"] = example_name
    merged["source_flows"] = root_cfg.get("source_flows", "config/flows.yaml")
    return merged


def _build_flows_yaml(cfg: dict, *, deployment_name: str, description: str = "") -> str:
    lines = [
        "# Generated by scripts/prepare_production_bundle.py — do not edit by hand.",
        f"# Deployment: {deployment_name}",
        f"# Paths from scripts/deployment-examples/{cfg.get('example', deployment_name)}/flows.yaml",
        f"# Flow settings from {cfg.get('source_flows', 'config/flows.yaml')}",
    ]
    if description:
        lines.append(f"# {description}")
    mode_label = cfg.get("required_mode", "")
    if mode_label:
        direction = "incoming (xml_to_csv)" if mode_label == INBOUND_MODE else "outgoing (csv_to_xml)"
        lines.append(f"# Flows included: {direction} only")
    lines.extend(["", "flows:"])

    for name, flow in cfg.get("flows", {}).items():
        mode = flow.get("mode", "csv_to_xml")
        mapping_file = flow.get("mapping_file", "./examples/mapping ROLLS SSW outgoing.xlsx")
        skeleton_xml = flow.get("skeleton_xml")
        xsd_file = flow.get("xsd_file")

        lines.extend(
            [
                f"  - name: {name}",
                f"    mode: {mode}",
                "",
                f"    input_dir: {_yaml_path(flow['input_dir'])}",
                f"    success_dir: {_yaml_path(flow['success_dir'])}",
                f"    error_dir: {_yaml_path(flow['error_dir'])}",
                f"    archive_dir: {_yaml_path(flow['archive_dir'])}",
                f"    in_progress_dir: {_yaml_path(flow['in_progress_dir'])}",
                "",
                f"    file_glob: \"{flow.get('file_glob', '*.*')}\"",
                "",
                "    input_format: csv",
                f"    delimiter: \"{flow.get('delimiter', '|')}\"",
                "",
                f"    mapping_file: {mapping_file}",
                f"    mapping_sheet_name: \"{flow.get('mapping_sheet_name', '')}\"",
            ]
        )
        if mode == "csv_to_xml":
            lines.append(f"    skeleton_xml: {skeleton_xml}")
            lines.append(f"    xsd_file: {xsd_file}")
        else:
            lines.extend(["    skeleton_xml: null", "    xsd_file: null"])
        lines.append(f"    root_element_name: {flow.get('root_element_name', 'PldaSswDeclaration')}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _iter_deployments(root_cfg: dict) -> list[tuple[str, dict]]:
    """
    Return (deployment_name, merged_config) for each deployment.

    Supports:
    - deployments: { NAME: { flows, paths, ... }, ... }  (preferred)
    - legacy single bundle: top-level flows + bundle_output_dir
    """
    deployments = root_cfg.get("deployments")
    if deployments:
        base = Path(root_cfg.get("bundle_output_base", "dist"))
        items: list[tuple[str, dict]] = []
        for name, dep in deployments.items():
            merged = _resolve_deployment(root_cfg, name, dep)
            if "bundle_output_dir" not in merged:
                merged["bundle_output_dir"] = str(base / name)
            items.append((name, merged))
        return items

    # Legacy: one combined bundle
    print("No deployments found in production paths config.", file=sys.stderr)
    sys.exit(1)


def _should_skip_path(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIR_NAMES or part.endswith(".egg-info"):
            return True
    if path.is_file():
        for pat in SKIP_FILE_PATTERNS:
            if pat.search(path.name):
                return True
    return False


def _copy_tree(src: Path, dst: Path) -> None:
    if _should_skip_path(src):
        return
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for child in src.iterdir():
            _copy_tree(child, dst / child.name)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _prepare_local_data(bundle: Path) -> None:
    data = bundle / "data"
    if not data.exists():
        return
    for sub in data.rglob("*"):
        if sub.is_file() and sub.name != ".gitkeep":
            sub.unlink()


def _copy_data_skeleton(bundle: Path) -> None:
    data_src = ROOT / "data"
    if not data_src.exists():
        return
    for gitkeep in data_src.rglob(".gitkeep"):
        rel = gitkeep.relative_to(data_src)
        target = bundle / "data" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gitkeep, target)
    readme = data_src / "README.md"
    if readme.exists():
        shutil.copy2(readme, bundle / "data" / "README.md")


def _write_deployment_readme(bundle: Path, deployment_name: str, cfg: dict) -> None:
    flow_names = ", ".join(cfg.get("flows", {}).keys())
    first_flow = next(iter(cfg.get("flows", {}).values()), {})
    text = (
        f"FileProcessor deployment bundle: {deployment_name}\n"
        f"{cfg.get('description', '')}\n\n"
        f"Flows in config/flows.yaml: {flow_names}\n"
        f"Shared input_dir: {first_flow.get('input_dir', '')}\n\n"
        "Reference flows.yaml: scripts/deployment-examples/"
        f"{deployment_name}/flows.yaml\n\n"
        "Install: see INSTALL.md and WINDOWS_SERVICE_GUIDE.md\n"
        "Run: python -m file_processor.cli run-daemon-mode config/flows.yaml -v\n"
    )
    (bundle / "DEPLOYMENT.txt").write_text(text, encoding="utf-8")


def _confirm_overwrite(output_dir: Path, *, force: bool) -> bool:
    if not output_dir.exists():
        return True
    if force:
        return True
    if not sys.stdin.isatty():
        print(
            f"  Refusing to overwrite existing {output_dir}. Use --force.",
            file=sys.stderr,
        )
        return False
    reply = input(f"  Overwrite existing bundle at {output_dir}? [y/N]: ").strip().lower()
    if reply not in ("y", "yes"):
        print("  Skipped.")
        return False
    return True


def prepare_bundle(
    deployment_name: str,
    output_dir: Path,
    *,
    purge_local_data: bool,
    force: bool,
    cfg: dict[str, Any],
) -> None:
    if not _confirm_overwrite(output_dir, force=force):
        return

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for name in COPY_DIRS:
        src = ROOT / name
        if src.exists():
            _copy_tree(src, output_dir / name)

    _copy_data_skeleton(output_dir)

    for name in COPY_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, output_dir / name)

    flows_yaml = _build_flows_yaml(
        cfg,
        deployment_name=deployment_name,
        description=str(cfg.get("description", "")),
    )
    (output_dir / "config" / "flows.yaml").write_text(flows_yaml, encoding="utf-8")

    if PRODUCTION_PATHS.exists():
        shutil.copy2(PRODUCTION_PATHS, output_dir / "config" / "production_paths.yaml")

    _write_deployment_readme(output_dir, deployment_name, cfg)

    if purge_local_data:
        _prepare_local_data(output_dir)
        print("  Purged local ./data files in bundle (kept .gitkeep).")

    print(f"  Bundle ready: {output_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare FileProcessor production deploy folder(s)."
    )
    parser.add_argument(
        "--deployment",
        action="append",
        dest="deployments",
        metavar="NAME",
        help="Build only this deployment (repeatable). Default: all deployments.",
    )
    parser.add_argument(
        "--list-deployments",
        action="store_true",
        help="List deployment names from config and exit.",
    )
    parser.add_argument(
        "--purge-local-data",
        action="store_true",
        help="Remove test files from data/ inside each bundle (not production FTP folders).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing bundle folder(s) under dist/ without prompting.",
    )
    args = parser.parse_args()

    root_cfg = _load_production_config()
    all_deployments = _iter_deployments(root_cfg)

    if args.list_deployments:
        for name, cfg in all_deployments:
            desc = cfg.get("description", "")
            out = cfg.get("bundle_output_dir", "")
            print(f"{name}\t{out}\t{desc}")
        return

    selected = {n: c for n, c in all_deployments}
    if args.deployments:
        unknown = set(args.deployments) - set(selected)
        if unknown:
            print(f"Unknown deployment(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            print(f"Available: {', '.join(sorted(selected))}", file=sys.stderr)
            sys.exit(1)
        selected = {n: selected[n] for n in args.deployments}

    print(f"Building {len(selected)} deployment bundle(s)...")
    for name, cfg in selected.items():
        print(f"\n=== {name} ===")
        if cfg.get("description"):
            print(f"  {cfg['description']}")
        out = Path(cfg["bundle_output_dir"])
        if not out.is_absolute():
            out = ROOT / out
        prepare_bundle(
            name,
            out,
            purge_local_data=args.purge_local_data,
            force=args.force,
            cfg=cfg,
        )
    print(f"\nDone. {len(selected)} bundle(s) under {ROOT / 'dist'}")


if __name__ == "__main__":
    main()
