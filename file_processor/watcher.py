from __future__ import annotations

import logging
from pathlib import Path
from threading import Event, Thread

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .config import FlowConfig, FlowRegistry
from .runner import FlowRunner

logger = logging.getLogger(__name__)


class _FlowEventHandler(FileSystemEventHandler):
    def __init__(self, flow: FlowConfig, runner: FlowRunner):
        super().__init__()
        self.flow = flow
        self.runner = runner

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Let flow.file_glob drive matching; simple suffix check for now
        if not path.match(self.flow.file_glob):
            return
        logger.info("Detected new file %s for flow %s", path, self.flow.name)
        try:
            self.runner.run_file(self.flow, path)
        except Exception:
            logger.exception("Error processing %s for flow %s", path, self.flow.name)


def start_watchers(registry: FlowRegistry, stop_event: Event) -> None:
    observers: list[Observer] = []

    runner = FlowRunner(registry)

    for flow in registry.flows:
        handler = _FlowEventHandler(flow, runner)
        observer = Observer()
        observer.schedule(handler, str(flow.input_dir), recursive=False)
        observer.start()
        observers.append(observer)
        logger.info("Started watcher for flow %s on %s", flow.name, flow.input_dir)

    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    finally:
        for observer in observers:
            observer.stop()
        for observer in observers:
            observer.join()


def run_daemon(registry: FlowRegistry) -> None:
    """
    Start background observers for all flows and block until interrupted.
    """
    stop_event = Event()

    # In a full app we would hook OS signals; for now, expose stop_event to caller via thread.
    thread = Thread(target=start_watchers, args=(registry, stop_event), daemon=False)
    thread.start()
    thread.join()

