"""Resolves output paths per output_mode, detects duplicates, and writes extracted files."""
from pathlib import Path
from typing import Dict, Optional, Tuple


class FileHandler:
    """Writes extracted files to disk under the configured output_mode, skipping duplicates."""

    def __init__(self, output_dir: Path, output_mode: str):
        self.output_dir = Path(output_dir)
        self.output_mode = output_mode
        # (output_subdir, filename, size) -> destination path already written this run.
        self._seen: Dict[Tuple[str, str, int], Path] = {}

    def resolve_dest_path(
        self,
        search_output_subdir: str,
        container_stem: str,
        filename: str,
        extension_dir: str,
    ) -> Path:
        """Build the destination path for a file based on output_mode.

        flat/by_search -> output_dir/output_subdir/filename
        by_iso         -> output_dir/output_subdir/container_stem/filename
        by_type        -> output_dir/output_subdir/extension_dir/filename
        """
        base = self.output_dir / search_output_subdir
        if self.output_mode == "by_iso":
            base = base / container_stem
        elif self.output_mode == "by_type":
            base = base / extension_dir.lstrip(".")
        return base / filename

    def is_duplicate(self, search_output_subdir: str, filename: str, size: int) -> Optional[Path]:
        """Return the existing destination path if filename+size was already written for this search."""
        return self._seen.get((search_output_subdir, filename, size))

    def mark_written(self, search_output_subdir: str, filename: str, size: int, dest_path: Path) -> None:
        self._seen[(search_output_subdir, filename, size)] = dest_path

    def ensure_parent(self, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
