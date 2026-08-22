"""Writes the extraction run log as a CSV: container, internal_path, dest, size, status, search."""
import csv
from pathlib import Path
from typing import Optional


class LogWriter:
    """Appends one row per file processed during the batch run. Header written once."""

    _FIELDS = ["container", "internal_path", "dest", "size", "status", "search"]

    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.log_path.exists()
        self._file = open(self.log_path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=self._FIELDS)
        if is_new:
            self._writer.writeheader()
            self._file.flush()

    def log(
        self,
        container: str,
        internal_path: str,
        dest: Optional[str],
        size: int,
        status: str,
        search: str,
    ) -> None:
        self._writer.writerow(
            {
                "container": container,
                "internal_path": internal_path,
                "dest": dest or "",
                "size": size,
                "status": status,
                "search": search,
            }
        )
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "LogWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
