"""Abstract base class defining the common interface all container adapters implement."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Iterator, Tuple


class ContainerAdapter(ABC):
    """Common interface for reading disc images and archives without mounting them.

    Every subclass exposes the same four operations, so callers never need to branch
    on container type — ContainerFactory is the only place that picks the subclass.
    """

    def __init__(self, container_path: Path):
        self.container_path = container_path

    @abstractmethod
    def open(self) -> None:
        """Open the container file and prepare it for reading."""
        raise NotImplementedError

    @abstractmethod
    def walk(self) -> Iterator[Tuple[str, str, int]]:
        """Yield (internal_path, filename, size_bytes) for every file in the container."""
        raise NotImplementedError

    @abstractmethod
    def extract_file(self, internal_path: str, dest_file_obj: BinaryIO) -> None:
        """Stream the bytes of internal_path into dest_file_obj."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release any resources held by the adapter."""
        raise NotImplementedError

    def __enter__(self) -> "ContainerAdapter":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
