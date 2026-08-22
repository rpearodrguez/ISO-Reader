"""Evaluates search match rules against files discovered while walking a container.

A search has one or more match rules (list items under `match:` in config.yaml). OR logic
applies between rules; AND logic applies between the fields set within a single rule.
"""
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import List, Optional, Pattern


@dataclass
class MatchRule:
    """A single AND-combined match rule. Fields left unset (None) are not checked."""

    extensions: Optional[List[str]] = None
    path_contains: Optional[str] = None
    filename_contains: Optional[str] = None
    path_regex: Optional[str] = None
    _compiled_regex: Optional[Pattern] = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Compiled once here rather than per-file during the container walk.
        if self.path_regex is not None:
            self._compiled_regex = re.compile(self.path_regex, re.IGNORECASE)

    def matches(self, internal_path: str, filename: str) -> bool:
        if self.extensions is not None:
            ext = PurePosixPath(filename).suffix.lower()
            wanted = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in self.extensions}
            if ext not in wanted:
                return False
        if self.path_contains is not None:
            if self.path_contains.lower() not in internal_path.lower():
                return False
        if self.filename_contains is not None:
            if self.filename_contains.lower() not in filename.lower():
                return False
        if self._compiled_regex is not None:
            if not self._compiled_regex.search(internal_path):
                return False
        return True


@dataclass
class Search:
    """A named search job: where to look, where results go, and what counts as a match."""

    name: str
    output_subdir: str
    match_rules: List[MatchRule] = field(default_factory=list)
    source_dir: Optional[str] = None

    def matches(self, internal_path: str, filename: str) -> bool:
        # OR between rules: any single rule matching is enough for the file to be selected.
        return any(rule.matches(internal_path, filename) for rule in self.match_rules)


def load_searches(raw_searches: list) -> List[Search]:
    """Build Search objects from the parsed `searches:` section of config.yaml."""
    searches = []
    for raw in raw_searches:
        rules = [MatchRule(**rule) for rule in raw.get("match", [])]
        searches.append(
            Search(
                name=raw["name"],
                output_subdir=raw["output_subdir"],
                match_rules=rules,
                source_dir=raw.get("source_dir"),
            )
        )
    return searches
