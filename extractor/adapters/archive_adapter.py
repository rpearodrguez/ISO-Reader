"""Adapter for .mdf/.bin disc images and .rar/.7z archives, read via libarchive-c.

libarchive-c has no random-access index — it only supports sequential entry iteration
over a fresh stream. `open()` therefore does one pass up front to cache (pathname, size)
for every entry, and `extract_file()` re-opens the stream and scans forward to the
requested entry each time it's called.

Caveat: .mdf and .bin are raw optical disc sector dumps, not true archives. libarchive
has no dedicated MDS/MDF or CUE/BIN reader — it only succeeds here when the payload
happens to be a plain 2048-byte-sector ISO9660 image, which covers many single-track
Alcohol 120% rips but not multi-track or 2352-byte raw-sector BIN files. Containers that
don't parse raise here, which the caller logs as an error and skips.

`libarchive` is imported lazily (inside open()/extract_file(), not at module load) because
it loads the native libarchive shared library via ctypes at import time. If that library
isn't installed on the host, importing it raises immediately -- doing that eagerly at
module level would take down the whole CLI even for users only processing .iso/.zip files.
"""
from pathlib import Path
from typing import BinaryIO, Iterator, List, Tuple

from .base import ContainerAdapter


class ArchiveAdapter(ContainerAdapter):
    """Reads .mdf, .bin, .rar, and .7z containers entry-by-entry via libarchive."""

    def __init__(self, container_path: Path):
        super().__init__(container_path)
        self._entries: List[Tuple[str, int]] = []

    def open(self) -> None:
        import libarchive

        with libarchive.file_reader(str(self.container_path)) as archive:
            self._entries = [
                (entry.pathname, entry.size or 0) for entry in archive if not entry.isdir
            ]

    def walk(self) -> Iterator[Tuple[str, str, int]]:
        for pathname, size in self._entries:
            filename = pathname.rsplit("/", 1)[-1]
            yield pathname, filename, size

    def extract_file(self, internal_path: str, dest_file_obj: BinaryIO) -> None:
        import libarchive

        with libarchive.file_reader(str(self.container_path)) as archive:
            for entry in archive:
                if entry.pathname == internal_path:
                    for block in entry.get_blocks():
                        dest_file_obj.write(block)
                    return
        raise FileNotFoundError(f"{internal_path!r} not found in {self.container_path}")

    def close(self) -> None:
        self._entries = []
