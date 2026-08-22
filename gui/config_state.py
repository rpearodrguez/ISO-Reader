"""Helpers over the raw config dict (same shape as config.yaml) that the GUI edits in
memory before saving. Kept framework-agnostic so it can be exercised without Qt.
"""
from pathlib import Path
from typing import List

import yaml


def default_config() -> dict:
    return {
        "global": {
            "source_dir": "",
            "output_dir": "",
            "output_mode": "by_iso",
            "log_file": "extraction.csv",
        },
        "searches": [],
    }


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("global", {})
    data.setdefault("searches", [])
    return data


def save_config(path: Path, config: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def add_regex_search(config: dict, name: str, output_subdir: str, path_regex: str) -> None:
    config.setdefault("searches", []).append(
        {
            "name": name,
            "output_subdir": output_subdir,
            "match": [{"path_regex": path_regex}],
        }
    )


def remove_search(config: dict, index: int) -> None:
    del config["searches"][index]


def summarize_rule(rule: dict) -> str:
    parts = []
    if rule.get("extensions"):
        parts.append("ext=" + ",".join(rule["extensions"]))
    if rule.get("path_contains"):
        parts.append(f"path~{rule['path_contains']}")
    if rule.get("filename_contains"):
        parts.append(f"name~{rule['filename_contains']}")
    if rule.get("path_regex"):
        parts.append(f"regex={rule['path_regex']}")
    return " & ".join(parts) if parts else "(vacío)"


def summarize_match(match_list: List[dict]) -> str:
    if not match_list:
        return "(sin reglas)"
    return " OR ".join(summarize_rule(rule) for rule in match_list)
