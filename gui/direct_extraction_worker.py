"""Runs extractor.direct_extract.extract_selected on a background thread so extracting a
hand-picked selection from the "Explorar disco" tab doesn't freeze the GUI."""
from pathlib import Path
from typing import List, Tuple

from PySide6.QtCore import QThread, Signal

from extractor.direct_extract import extract_selected


class DirectExtractionWorker(QThread):
    """Wraps extract_selected() and re-emits its plain callback as a Qt signal."""

    file_progress = Signal(str)
    finished_ok = Signal(int, list)
    failed = Signal(str)

    def __init__(self, container_path: Path, files: List[Tuple[str, str]], output_dir: Path, parent=None):
        super().__init__(parent)
        self._container_path = container_path
        self._files = files
        self._output_dir = output_dir

    def run(self) -> None:
        try:
            extracted, errors = extract_selected(
                self._container_path,
                self._files,
                self._output_dir,
                on_file_progress=lambda path: self.file_progress.emit(path),
            )
            self.finished_ok.emit(extracted, errors)
        except Exception as exc:
            self.failed.emit(str(exc))
