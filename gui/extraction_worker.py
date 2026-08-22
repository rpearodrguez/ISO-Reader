"""Runs extractor.batch_runner.run_batch on a background thread so the GUI stays responsive."""
from PySide6.QtCore import QThread, Signal

from extractor.batch_runner import run_batch


class ExtractionWorker(QThread):
    """Wraps run_batch() and re-emits its plain callbacks as Qt signals."""

    container_started = Signal(str, int)
    file_progress = Signal()
    container_error = Signal(str)
    source_missing = Signal(str)
    file_error = Signal(str, str)
    container_finished = Signal(str, dict)
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config

    def run(self) -> None:
        try:
            stats = run_batch(
                self._config,
                on_container_start=lambda name, total: self.container_started.emit(name, total),
                on_file_progress=lambda: self.file_progress.emit(),
                on_container_error=lambda msg: self.container_error.emit(msg),
                on_source_missing=lambda path: self.source_missing.emit(str(path)),
                on_file_error=lambda internal_path, msg: self.file_error.emit(internal_path, msg),
                on_container_finished=lambda name, counts: self.container_finished.emit(name, counts),
            )
            self.finished_ok.emit(stats)
        except Exception as exc:
            self.failed.emit(str(exc))
