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

    @staticmethod
    def _next_available_target_path(target_dir: Path, source_name: str) -> Path:
        """
        Return a non-existing target path in target_dir.
        If source_name already exists, append _0001, _0002, ... before extension.
        """
        base = Path(source_name).stem
        suffix = Path(source_name).suffix

        candidate = target_dir / source_name
        if not candidate.exists():
            return candidate

        idx = 1
        while True:
            candidate = target_dir / f"{base}_{idx:04d}{suffix}"
            if not candidate.exists():
                return candidate
            idx += 1

    def _move(self, source: Path, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._next_available_target_path(target_dir, source.name)
        if target_path.name != source.name:
            logger.warning(
                "Target file already exists in %s; moving %s as %s",
                target_dir,
                source.name,
                target_path.name,
            )
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

    def process_existing_in_progress(self, processing_path: Path, handler: Callable[[Path], None]) -> None:
        """
        Resume processing for a file that is already in in-progress state.
        Used on startup recovery after an unclean stop.
        """
        try:
            handler(processing_path)
        except Exception:
            logger.exception("Error while recovering %s for flow %s", processing_path, self.flow.name)
            self._move_to_error(processing_path)
            raise
        else:
            self._move_to_archive(processing_path)

