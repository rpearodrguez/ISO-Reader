"""Adapter for ISO 9660 disc images, read via pycdlib without mounting.

Facility preference is Joliet > Rock Ridge > plain ISO9660: Joliet gives the original
Unicode filenames, Rock Ridge gives POSIX-style names, and plain ISO9660 falls back to
truncated 8.3 uppercase names with a trailing ";1" version suffix.
"""
import posixpath
from pathlib import Path
from typing import BinaryIO, Iterator, Tuple

import pycdlib

from .base import ContainerAdapter


class IsoAdapter(ContainerAdapter):
    """Reads .iso disc images via pycdlib, picking the richest available naming facility."""

    def __init__(self, container_path: Path):
        super().__init__(container_path)
        self._iso: "pycdlib.PyCdlib | None" = None
        self._facility_kwarg = "iso_path"  # one of iso_path / rr_path / joliet_path

    def open(self) -> None:
        self._iso = pycdlib.PyCdlib()
        self._iso.open(str(self.container_path))
        if self._iso.has_joliet():
            self._facility_kwarg = "joliet_path"
        elif self._iso.has_rock_ridge():
            self._facility_kwarg = "rr_path"
        else:
            self._facility_kwarg = "iso_path"

    def walk(self) -> Iterator[Tuple[str, str, int]]:
        assert self._iso is not None
        for dirname, _dirlist, filelist in self._iso.walk(**{self._facility_kwarg: "/"}):
            for entry in filelist:
                internal_path = posixpath.join(dirname, entry)
                # Every facility (Joliet and Rock Ridge included) carries a ";1" version
                # suffix on the raw file identifier -- it's not part of the real filename
                # and ';' isn't legal in an ISO9660 name, so it's always safe to strip.
                filename = entry.split(";")[0]
                record = self._iso.get_record(**{self._facility_kwarg: internal_path})
                yield internal_path, filename, record.get_data_length()

    def extract_file(self, internal_path: str, dest_file_obj: BinaryIO) -> None:
        assert self._iso is not None
        self._iso.get_file_from_iso_fp(dest_file_obj, **{self._facility_kwarg: internal_path})

    def close(self) -> None:
        if self._iso is not None:
            self._iso.close()
            self._iso = None
