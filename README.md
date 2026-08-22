# iso-extractor

Batch-extracts files from disc images and archives without mounting them, driven by
user-defined search rules. See [claude.md](claude.md) for the full architecture and
container-format caveats.

## Install

```
pip install -r requirements.txt
```

`libarchive-c` is a binding, not the library itself — it needs the native **libarchive**
shared library installed and discoverable at runtime for `.mdf`/`.bin`/`.rar`/`.7z` support:

- Linux: `apt install libarchive13` (or equivalent for your distro)
- macOS: `brew install libarchive`
- Windows: place `archive.dll` (from a libarchive release) somewhere on `PATH`

`.iso` and `.zip` have no native dependency — `pycdlib` and stdlib `zipfile` are pure Python.

## Configure

Edit `config.yaml`:

```yaml
global:
  source_dir: "/media/isos"
  output_dir: "/output"
  output_mode: by_iso        # flat | by_iso | by_type | by_search
  log_file: "extraction.csv"

searches:
  - name: "Audio completo"
    output_subdir: "audio"
    match:
      - extensions: [.mp3, .mp2, .wma, .wav]
```

Each search's `match` list is a set of OR'd rules; within one rule, `extensions`,
`path_contains`, and `filename_contains` are AND'd together. See `config.yaml` for more
examples, including per-search `source_dir` overrides.

## Run

```
python main.py --config config.yaml
```

Progress is shown per container file; a summary table (matched / extracted / skipped /
errors per search) prints at the end, and every processed file is logged to
`global.log_file` as CSV.

## GUI

```
python gui_main.py
```

A PySide6 desktop app for building `config.yaml` visually instead of hand-writing match
rules:

- **Explorar disco** — pick a folder of discs (or open a single container file), open
  one from the list, and browse its real internal folder tree. Check the
  folders/files you want, click "Generar expresión regular" to get a `path_regex`
  pattern covering the selection, then add it as a named search with one click.
- **Batch** — pick the source folder of discs to process and the destination folder for
  extracted files, choose `output_mode`, load/save a `config.yaml`, review/remove the
  configured searches, and run the extraction with a live progress bar and log.

Note: a regex generated from one disc's tree matches that disc's exact internal paths.
It generalizes well for stable top-level folder names (`RADIO/`, `WEB/`) across the
collection, but a very specific nested path may not exist under the same name on every
disc — see `claude.md` for why disc layouts vary release to release.
