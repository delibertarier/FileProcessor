from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from .config import FlowConfig

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Handles transactional file moves for a single flow.

    Lifecycle:
    - Move from input_dir to in_progress_dir (or rename with .processing suffix).
    - Invoke processing function on the in-progress path.
    - On success, move in-progress file to archive_dir.
    - On failure, move in-progress file to error_dir.
    """

    def __init__(self, flow: FlowConfig) -> None:
        self.flow = flow

    def _move(self, source: Path, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / source.name
        source.rename(target_path)
        return target_path

    def _move_to_in_progress(self, src: Path) -> Path:
        if self.flow.in_progress_dir:
            in_progress_dir = self.flow.in_progress_dir
            logger.debug("Moving %s to in-progress dir %s", src, in_progress_dir)
            return self._move(src, in_progress_dir)
        # Fallback: rename in place with .processing suffix
        processing_path = src.with_suffix(src.suffix + ".processing")
        logger.debug("Renaming %s to %s for in-progress", src, processing_path)
        src.rename(processing_path)
        return processing_path

    def _move_to_archive(self, src: Path) -> None:
        logger.debug("Archiving %s to %s", src, self.flow.archive_dir)
        self._move(src, self.flow.archive_dir)

    def _move_to_error(self, src: Path) -> None:
        logger.debug("Moving errored %s to %s", src, self.flow.error_dir)
        self._move(src, self.flow.error_dir)

    def process_with_transaction(self, src: Path, handler: Callable[[Path], None]) -> None:
        processing_path = self._move_to_in_progress(src)
        try:
            handler(processing_path)
        except Exception:
            logger.exception("Error while processing %s for flow %s", processing_path, self.flow.name)
            self._move_to_error(processing_path)
            raise
        else:
            self._move_to_archive(processing_path)

