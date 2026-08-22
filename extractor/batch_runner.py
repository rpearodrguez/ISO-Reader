"""Business logic for running a batch extraction: discovering containers, grouping
searches, and walking/extracting each container.

Framework-agnostic on purpose so both the `rich`-based CLI (main.py) and the PySide6 GUI
drive the exact same extraction path instead of maintaining two copies of it. Progress
is reported through plain callbacks rather than a `rich.Progress` instance.
"""
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .factory import ContainerFactory, UnsupportedContainerError
from .file_handler import FileHandler
from .log_writer import LogWriter
from .search_engine import Search, load_searches

# (container_name, total_entries) -> None
OnContainerStart = Callable[[str, int], None]
# () -> None, called once per entry walked in the current container
OnFileProgress = Callable[[], None]
# (message) -> None, called for container-level failures that don't abort the batch
OnContainerError = Callable[[str], None]


def discover_containers(source_dir: Path) -> List[Path]:
    """Recursively find every file whose extension has a registered adapter."""
    supported = set(ContainerFactory.supported_extensions().keys())
    return sorted(p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in supported)


def group_searches_by_source(searches: List[Search], default_source_dir: Path) -> Dict[Path, List[Search]]:
    """Group searches by their effective source_dir so each container is walked once
    regardless of how many searches apply to it."""
    groups: Dict[Path, List[Search]] = defaultdict(list)
    for search in searches:
        effective_source = Path(search.source_dir) if search.source_dir else default_source_dir
        groups[effective_source].append(search)
    return groups


def process_container(
    container_path: Path,
    searches: List[Search],
    file_handler: FileHandler,
    log_writer: LogWriter,
    stats: dict,
    on_container_start: Optional[OnContainerStart] = None,
    on_file_progress: Optional[OnFileProgress] = None,
    on_container_error: Optional[OnContainerError] = None,
) -> None:
    """Walk one container exactly once and check every applicable search against each entry."""
    try:
        adapter = ContainerFactory.create(container_path)
    except UnsupportedContainerError as exc:
        log_writer.log(container_path.name, "", None, 0, f"error: {exc}", "")
        return

    try:
        with adapter:
            entries = list(adapter.walk())
            if on_container_start is not None:
                on_container_start(container_path.name, len(entries))
            for internal_path, filename, size in entries:
                extension_dir = Path(filename).suffix.lower() or "noext"
                for search in searches:
                    if not search.matches(internal_path, filename):
                        continue
                    stats[search.name]["matched"] += 1
                    existing = file_handler.is_duplicate(search.output_subdir, filename, size)
                    if existing is not None:
                        stats[search.name]["skipped"] += 1
                        log_writer.log(
                            container_path.name, internal_path, str(existing), size, "skipped", search.name
                        )
                        continue
                    dest = file_handler.resolve_dest_path(
                        search.output_subdir, container_path.stem, filename, extension_dir
                    )
                    file_handler.ensure_parent(dest)
                    try:
                        with open(dest, "wb") as out_f:
                            adapter.extract_file(internal_path, out_f)
                        file_handler.mark_written(search.output_subdir, filename, size, dest)
                        stats[search.name]["extracted"] += 1
                        log_writer.log(
                            container_path.name, internal_path, str(dest), size, "extracted", search.name
                        )
                    except Exception as exc:
                        stats[search.name]["errors"] += 1
                        log_writer.log(
                            container_path.name, internal_path, None, size, f"error: {exc}", search.name
                        )
                if on_file_progress is not None:
                    on_file_progress()
    except Exception as exc:
        # Corrupted or unsupported container content must not abort the batch.
        if on_container_error is not None:
            on_container_error(f"Failed to read {container_path.name}: {exc}")
        log_writer.log(container_path.name, "", None, 0, f"error: {exc}", "")


def run_batch(
    config: dict,
    on_container_start: Optional[OnContainerStart] = None,
    on_file_progress: Optional[OnFileProgress] = None,
    on_container_error: Optional[OnContainerError] = None,
    on_source_missing: Optional[Callable[[Path], None]] = None,
) -> dict:
    """Run every search in `config` across all discovered containers and return stats.

    `config` has the same shape as the parsed config.yaml (a `global` block plus a
    `searches` list). This is the single entry point both the CLI and the GUI call to
    execute an actual extraction run.
    """
    global_cfg = config["global"]
    default_source_dir = Path(global_cfg["source_dir"])
    output_dir = Path(global_cfg["output_dir"])
    output_mode = global_cfg.get("output_mode", "by_iso")
    log_file = Path(global_cfg.get("log_file", "extraction.csv"))

    searches = load_searches(config.get("searches", []))
    stats = defaultdict(lambda: {"matched": 0, "extracted": 0, "skipped": 0, "errors": 0})
    for search in searches:
        stats[search.name]  # pre-populate so the summary lists every search, even with 0 matches

    file_handler = FileHandler(output_dir, output_mode)
    groups = group_searches_by_source(searches, default_source_dir)

    with LogWriter(log_file) as log_writer:
        for group_source, group_searches in groups.items():
            if not group_source.exists():
                if on_source_missing is not None:
                    on_source_missing(group_source)
                continue
            for container_path in discover_containers(group_source):
                process_container(
                    container_path,
                    group_searches,
                    file_handler,
                    log_writer,
                    stats,
                    on_container_start=on_container_start,
                    on_file_progress=on_file_progress,
                    on_container_error=on_container_error,
                )

    return dict(stats)
