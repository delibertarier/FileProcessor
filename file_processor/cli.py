from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from .config import FlowRegistry
from .runner import FlowRunner
from .version import __version__
from .watcher import run_daemon

app = typer.Typer(help="FileProcessor CLI")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Configurable CSV/XML file processor."""


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )


def _load_registry(config_path: Path) -> FlowRegistry:
    try:
        return FlowRegistry.from_yaml(config_path)
    except ValidationError as exc:
        raise typer.BadParameter(f"Invalid config: {exc}") from exc


@app.command()
def version() -> None:
    """Print the installed FileProcessor version."""
    typer.echo(__version__)


@app.command()
def run_once(
    config: Path = typer.Argument(..., help="Path to flows.yaml configuration file."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Process all current files in all flows once (batch mode)."""
    _setup_logging(verbose)
    registry = _load_registry(config)
    runner = FlowRunner(registry)
    runner.run_all_pending()


@app.command()
def run_daemon_mode(
    config: Path = typer.Argument(..., help="Path to flows.yaml configuration file."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging."),
) -> None:
    """Watch flow input directories and process new files as they appear."""
    _setup_logging(verbose)
    registry = _load_registry(config)
    run_daemon(registry)


if __name__ == "__main__":
    app()

