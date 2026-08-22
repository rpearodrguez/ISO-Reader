# iso-extractor — project context

Batch-extracts files from disc images and archives **without mounting them**, driven by
user-defined searches in `config.yaml`. Built for a library of Japanese anime magazine
discs (Minami, Dokan, and similar, 2000s–2010s era) containing mixed audio, video, HTML,
image, and installer content across many different container formats.

## Why this exists

The discs are inconsistent: content that lives under `RADIO/` on one disc might live under
`AUDIO/` on another, file layouts vary release to release, and the containers themselves are
a mix of ISO images, Alcohol 120% images, BIN/CUE rips, and plain archives. Mounting each one
by hand and hunting through folders doesn't scale. Instead, the user describes *what* they
want (extensions, path substrings, filename substrings) once, and the tool applies that
description across the whole disc collection.

## Architecture

```
main.py                      CLI entrypoint: loads config, wires rich progress/summary, calls batch_runner
gui_main.py                   GUI entrypoint: launches the PySide6 MainWindow
extractor/
  adapters/
    base.py                  ContainerAdapter ABC: open() / walk() / extract_file() / close()
    iso_adapter.py            .iso            — pycdlib (Joliet > Rock Ridge > ISO9660 fallback)
    archive_adapter.py         .mdf, .bin, .rar, .7z — libarchive-c, entry-by-entry streaming
    zip_adapter.py             .zip           — stdlib zipfile
  factory.py                  ContainerFactory: file extension -> adapter class
  search_engine.py            MatchRule / Search: OR-between-rules, AND-within-a-rule matching
  batch_runner.py              discover_containers / run_batch: the actual extraction logic,
                               framework-agnostic (plain callbacks, no rich/Qt dependency) so
                               both main.py and the GUI drive the same code path
  file_handler.py             output path resolution per output_mode, duplicate skip tracking
  log_writer.py                CSV run log writer
  direct_extract.py            extract_selected(): hand-picked (internal_path, filename) list
                               from one already-open container -> flat destination folder,
                               framework-agnostic like batch_runner.py, used by the GUI's
                               explorer-tab "Extraer seleccionados" button
gui/
  main_window.py               QMainWindow: "Explorar disco" tab + "Batch" tab
  disc_tree.py                  builds a checkable QTreeWidget from adapter.walk(), tri-state
                                 parent/child propagation, collect_checked()
  regex_builder.py               pure function: checked (path, is_folder) pairs -> path_regex
  config_state.py                 in-memory config dict helpers (load/save YAML, add/remove search)
  extraction_worker.py             QThread wrapping batch_runner.run_batch for the GUI
  direct_extraction_worker.py       QThread wrapping direct_extract.extract_selected for the GUI
```

Every adapter implements the same 4-method interface (`ContainerAdapter` in
`extractor/adapters/base.py`), so callers never branch on container type — they always
walk and extract through the same interface, and `ContainerFactory` is the only place that
knows which adapter handles which extension.

`ContainerAdapter.walk()` yields `(internal_path, filename, size_bytes)` tuples.
`ContainerAdapter.extract_file(internal_path, dest_file_obj)` streams bytes into an open file
object — nothing is ever unpacked to a temp directory first.

## Container format support and caveats

| Format         | Library      | Notes |
|----------------|--------------|-------|
| `.iso`         | pycdlib      | Picks Joliet names if present, else Rock Ridge, else plain ISO9660 (8.3, uppercase). Every facility's raw file identifier carries a `;1` version suffix; it's stripped from the displayed filename regardless of facility, but kept in `internal_path` since pycdlib needs it to look the entry back up. |
| `.mdf`         | libarchive-c | Alcohol 120% images. Only read correctly when the payload is a plain 2048-byte-sector ISO9660 image — libarchive has no real MDS/MDF format reader, it works by luck when the sectors line up with what its ISO9660 reader expects. |
| `.bin`         | libarchive-c | CUE/BIN rips. Same caveat as `.mdf` — multi-track or 2352-byte raw-sector BIN files are not guaranteed to parse. |
| `.rar`, `.7z`  | libarchive-c | Requires the system libarchive native library to be installed and discoverable (not just the Python binding) — see README. |
| `.zip`         | stdlib `zipfile` | No external dependency. |

**`.mds` and `.cue` sidecar files are intentionally *not* registered as openable containers.**
They're small metadata/index files (Alcohol 120% descriptor, CUE sheet) that point at the real
data in the paired `.mdf`/`.bin` file — libarchive can't parse them, so `ContainerFactory` only
maps `.mdf` and `.bin` themselves. `discover_containers()` in `main.py` will simply skip
`.mds`/`.cue` files when scanning a source directory.

A container that fails to open or read (corrupted, unsupported internal structure) is caught
per-file in `extractor/batch_runner.py`: the batch logs an error row and moves on to the next
container — it never aborts the whole run. Both the CLI and the GUI single-file "explore a
container" path (`gui/main_window.py`) also catch this per-container, showing a dialog instead
of a log line.

`archive_adapter.py` imports `libarchive` lazily, inside `open()`/`extract_file()`, not at
module load. `libarchive` loads the native libarchive shared library via `ctypes` as soon as
it's imported, so if that library isn't installed on the host, an eager module-level import
would crash the whole CLI on startup — even for a run that only touches `.iso`/`.zip` files.
With the lazy import, a missing native library only surfaces as a per-container error the
first time an `.mdf`/`.bin`/`.rar`/`.7z` file is actually opened.

## Search system

Defined under `searches:` in `config.yaml`. Each search has:
- `name` — label, shown in the summary table and CSV log.
- `source_dir` — optional per-search override of `global.source_dir`.
- `output_subdir` — subfolder under `global.output_dir` this search's matches go into.
- `match` — a list of match rules.

**OR between rules, AND within a rule.** A file matches a search if *any* rule in `match`
matches; a rule matches only if *all* the fields set on it (`extensions`, `path_contains`,
`filename_contains`, `path_regex`) match. This is implemented in `extractor/search_engine.py`
(`MatchRule.matches` = AND, `Search.matches` = OR over rules). `path_regex` is matched against
`internal_path` with `re.search` (case-insensitive), compiled once in `MatchRule.__post_init__`
rather than per-file — it's what the GUI's disc-tree selection ends up writing into
`config.yaml`, but it's a plain config field so it works the same if hand-written too.

Searches that share the same effective `source_dir` are grouped in `extractor/batch_runner.py`
(`group_searches_by_source`) so each container is opened and walked exactly once per unique
source directory, regardless of how many searches apply to it — a file can satisfy multiple
searches and gets copied into each one's `output_subdir`.

## Output and duplicate handling

`global.output_mode` controls the destination layout (`extractor/file_handler.py`):
- `flat` — `output_dir/output_subdir/filename`
- `by_iso` — `output_dir/output_subdir/<container filename without extension>/filename`
- `by_type` — `output_dir/output_subdir/<extension>/filename`
- `by_search` — same as `flat`; the search's own `output_subdir` already provides the grouping.

Duplicate detection is `(output_subdir, filename, size)` — if that combination was already
written during this run, the file is skipped and logged as `skipped` rather than overwritten.

## Run log

`extractor/log_writer.py` appends one CSV row per file processed (`container, internal_path,
dest, size, status, search`) to `global.log_file`, across runs (append mode, header written
once). `status` is one of `extracted`, `skipped`, or `error: <message>`.

## Running it

```
python main.py --config config.yaml
```

`rich` renders one progress bar per container file being walked, and a summary table
(matched / extracted / skipped / errors per search) at the end.

## GUI

```
python gui_main.py
```

A PySide6 app for building `config.yaml` without hand-writing match rules: the **Explorar
disco** tab opens a real container (via the same `ContainerFactory`/adapters as the CLI),
renders its internal folder tree in a checkable `QTreeWidget` (`gui/disc_tree.py`). The
checked selection can either be turned into a `path_regex` (`gui/regex_builder.py`) appended
to the in-memory config as a new search (`gui/config_state.py`) for a later batch run, or
extracted immediately via the **Extraer seleccionados** button into a user-chosen default
destination folder — this direct path (`extractor/direct_extract.py`, wrapped for the GUI by
`gui/direct_extraction_worker.py`) is independent of `config.yaml`/searches: checked folders
are expanded to their contained files using the container's already-fetched `walk()` entries,
and every selected file is written flat into the destination folder (not mirroring the
container's internal path — the point of hand-picking files is not having to reproduce that
structure on disk), with same-named picks disambiguated via a `(2)`-style suffix rather than
overwriting each other. The **Batch** tab sets `global.source_dir` / `global.output_dir` /
`output_mode` / `log_file`, loads/saves the YAML, and runs the extraction on a background
`QThread` (`gui/extraction_worker.py`) that calls the exact same
`extractor/batch_runner.run_batch()` the CLI uses — there is only one *batch* extraction code
path, the CLI and GUI just wire its callbacks differently (rich progress bars vs. Qt signals);
the explorer tab's direct-extract path is a separate, simpler flow for a hand-picked selection
from a single already-open container.

Caveat inherent to the workflow: a regex built from one disc's tree matches that disc's exact
paths. It generalizes across the collection for stable top-level folder names (matching the
existing `RADIO/`-vs-`AUDIO/` variance this project already works around), but a deeply nested,
disc-specific path may not exist under the same name on every disc.
