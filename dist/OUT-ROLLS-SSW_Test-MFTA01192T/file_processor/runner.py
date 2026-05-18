from __future__ import annotations

import logging
from pathlib import Path

from .config import FlowConfig, FlowRegistry
from .processor import process_file_for_flow
from .transaction import TransactionManager

logger = logging.getLogger(__name__)


class FlowRunner:
    """Coordinates transactional processing of files for all configured flows."""

    def __init__(self, registry: FlowRegistry) -> None:
        self.registry = registry

    def run_file(self, flow: FlowConfig, path: Path) -> None:
        tm = TransactionManager(flow)
        tm.process_with_transaction(path, lambda p: process_file_for_flow(flow, p))

    def _recover_in_progress_for_flow(self, flow: FlowConfig) -> int:
        if not flow.in_progress_dir:
            return 0
        if not flow.in_progress_dir.exists():
            return 0

        recovered = 0
        tm = TransactionManager(flow)
        paths = sorted(p for p in flow.in_progress_dir.glob("*") if p.is_file())
        for path in paths:
            recovered += 1
            logger.info("Recovering in-progress file %s for flow %s", path, flow.name)
            try:
                tm.process_existing_in_progress(path, lambda p: process_file_for_flow(flow, p))
            except Exception:
                logger.exception(
                    "Error recovering in-progress file %s for flow %s; continuing with next file",
                    path,
                    flow.name,
                )
        return recovered

    def run_all_pending(self) -> None:
        any_files = False

        for flow in self.registry.flows:
            recovered_count = self._recover_in_progress_for_flow(flow)
            if recovered_count:
                any_files = True

            paths = sorted(flow.input_dir.glob(flow.file_glob))
            if not paths:
                logger.info(
                    "No files found for flow '%s' in %s matching pattern %s",
                    flow.name,
                    flow.input_dir,
                    flow.file_glob,
                )
                continue

            for path in paths:
                any_files = True
                logger.info("Queued file %s for flow %s", path, flow.name)
                try:
                    self.run_file(flow, path)
                except Exception:
                    # Keep run-once resilient: one bad file should not block others.
                    logger.exception("Error processing %s for flow %s; continuing with next file", path, flow.name)

        if not any_files:
            logger.info("No input files found for any configured flows. Nothing to do.")

