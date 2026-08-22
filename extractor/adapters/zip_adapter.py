"""Adapter for .zip archives, read via the stdlib zipfile module (no extra dependency)."""
import zipfile
from pathlib import Path
from typing import BinaryIO, Iterator, Tuple

from .base import ContainerAdapter


class ZipAdapter(ContainerAdapter):
    """Reads .zip archives without extracting the whole archive to disk first."""

    def __init__(self, container_path: Path):
        super().__init__(container_path)
        self._zip: "zipfile.ZipFile | None" = None

    def open(self) -> None:
        self._zip = zipfile.ZipFile(self.container_path, "r")

    def walk(self) -> Iterator[Tuple[str, str, int]]:
        assert self._zip is not None
        for info in self._zip.infolist():
            if info.is_dir():
                continue
            filename = info.filename.rsplit("/", 1)[-1]
            yield info.filename, filename, info.file_size

    def extract_file(self, internal_path: str, dest_file_obj: BinaryIO) -> None:
        assert self._zip is not None
        with self._zip.open(internal_path) as src:
            dest_file_obj.write(src.read())

    def close(self) -> None:
        if self._zip is not None:
            self._zip.close()
            self._zip = None
