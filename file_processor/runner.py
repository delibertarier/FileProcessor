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

    def run_all_pending(self) -> None:
        for flow in self.registry.flows:
            for path in sorted(flow.input_dir.glob(flow.file_glob)):
                logger.info("Queued file %s for flow %s", path, flow.name)
                self.run_file(flow, path)

