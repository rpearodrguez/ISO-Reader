"""Resolves the correct ContainerAdapter subclass from a container file's extension.

.mds and .cue are intentionally excluded: they are sidecar metadata/index files (Alcohol
120% descriptor, CUE sheet) that point at the real payload in the paired .mdf/.bin file,
not containers libarchive can open on their own. See claude.md for the full rationale.
"""
from pathlib import Path
from typing import Dict, Type

from .adapters.archive_adapter import ArchiveAdapter
from .adapters.base import ContainerAdapter
from .adapters.iso_adapter import IsoAdapter
from .adapters.zip_adapter import ZipAdapter

_EXTENSION_MAP: Dict[str, Type[ContainerAdapter]] = {
    ".iso": IsoAdapter,
    ".mdf": ArchiveAdapter,
    ".bin": ArchiveAdapter,
    ".rar": ArchiveAdapter,
    ".7z": ArchiveAdapter,
    ".zip": ZipAdapter,
}


class UnsupportedContainerError(Exception):
    """Raised when a file extension has no registered adapter."""


class ContainerFactory:
    """Builds the appropriate ContainerAdapter instance for a given container file path."""

    @staticmethod
    def create(container_path: Path) -> ContainerAdapter:
        ext = container_path.suffix.lower()
        adapter_cls = _EXTENSION_MAP.get(ext)
        if adapter_cls is None:
            raise UnsupportedContainerError(f"No adapter registered for extension {ext!r}")
        return adapter_cls(container_path)

    @staticmethod
    def supported_extensions() -> Dict[str, Type[ContainerAdapter]]:
        return dict(_EXTENSION_MAP)
