"""CLI entrypoint: loads config.yaml and runs every configured search across all discovered
container files, extracting matching files without mounting the containers.
"""
import argparse
from pathlib import Path

import yaml
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from extractor.batch_runner import run_batch

console = Console()


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_summary(stats: dict) -> None:
    table = Table(title="Extraction Summary")
    table.add_column("Search")
    table.add_column("Matched", justify="right")
    table.add_column("Extracted", justify="right")
    table.add_column("Skipped (dup)", justify="right")
    table.add_column("Errors", justify="right")
    for name, counts in stats.items():
        table.add_row(
            name, str(counts["matched"]), str(counts["extracted"]), str(counts["skipped"]), str(counts["errors"])
        )
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-extract files from disc images and archives.")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"), help="Path to config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    if not config.get("searches"):
        console.print("[yellow]No searches defined in config.yaml -- nothing to do.[/yellow]")
        return

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = None

        def on_container_start(name: str, total: int) -> None:
            nonlocal task_id
            task_id = progress.add_task(name, total=total)

        def on_file_progress() -> None:
            progress.update(task_id, advance=1)

        def on_container_error(message: str) -> None:
            console.print(f"[red]{message}[/red]")

        def on_source_missing(source_dir: Path) -> None:
            console.print(f"[red]Source dir not found: {source_dir}[/red]")

        def on_file_error(internal_path: str, message: str) -> None:
            console.print(f"[red]  Error extracting {internal_path}: {message}[/red]")

        def on_container_finished(name: str, counts: dict) -> None:
            console.print(
                f"  {name}: {counts['matched']} matched, {counts['extracted']} extracted, "
                f"{counts['skipped']} skipped, {counts['errors']} errors"
            )

        stats = run_batch(
            config,
            on_container_start=on_container_start,
            on_file_progress=on_file_progress,
            on_container_error=on_container_error,
            on_source_missing=on_source_missing,
            on_file_error=on_file_error,
            on_container_finished=on_container_finished,
        )

    print_summary(stats)


if __name__ == "__main__":
    main()
