"""Direct extraction of a hand-picked set of files from a single already-opened container.

Used by the GUI's "Explorar disco" tab so the user can extract files straight from the
tree they're browsing, without first turning the selection into a search and running it
through the searches/config.yaml batch flow (extractor/batch_runner.py). Framework-agnostic
like batch_runner, so the GUI can wrap it in a QThread and drive it with plain callbacks.
"""
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .factory import ContainerFactory

# (internal_path) -> None, called once per file after it's written or failed
OnFileProgress = Callable[[str], None]


def _unique_dest(output_dir: Path, filename: str, used_names: set) -> Path:
    """Return output_dir/filename, or a "name (2).ext"-style variant if that name was
    already claimed earlier in this same extraction run."""
    if filename not in used_names:
        return output_dir / filename
    stem, suffix = Path(filename).stem, Path(filename).suffix
    n = 2
    while f"{stem} ({n}){suffix}" in used_names:
        n += 1
    return output_dir / f"{stem} ({n}){suffix}"


def extract_selected(
    container_path: Path,
    files: List[Tuple[str, str]],
    output_dir: Path,
    on_file_progress: Optional[OnFileProgress] = None,
) -> Tuple[int, List[str]]:
    """Extract the given (internal_path, filename) pairs from container_path into output_dir.

    Files land directly in output_dir (flat) rather than mirroring the container's internal
    folder structure, since the whole point of picking specific files is to not have to dig
    through that structure again on disk. Two selected files that happen to share a filename
    are disambiguated with a "(2)" suffix instead of one silently overwriting the other. A
    single file's extraction failure is recorded in the returned error list rather than
    aborting the rest. Returns (extracted_count, error_messages).
    """
    adapter = ContainerFactory.create(container_path)
    extracted = 0
    errors: List[str] = []
    used_names: set = set()
    output_dir.mkdir(parents=True, exist_ok=True)
    with adapter:
        for internal_path, filename in files:
            dest = _unique_dest(output_dir, filename, used_names)
            used_names.add(dest.name)
            try:
                with open(dest, "wb") as out_f:
                    adapter.extract_file(internal_path, out_f)
                extracted += 1
            except Exception as exc:
                errors.append(f"{internal_path}: {exc}")
            if on_file_progress is not None:
                on_file_progress(internal_path)
    return extracted, errors
