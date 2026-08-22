"""Pure logic (no Qt) for turning a set of checked disc-tree paths into a single regex.

Kept separate from disc_tree.py so it can be exercised with a plain script, no display
required.
"""
import re
from typing import List, Tuple


def build_regex(items: List[Tuple[str, bool]]) -> str:
    """Build a `path_regex` pattern matching any of the given (internal_path, is_folder) pairs.

    A folder entry matches itself and everything under it (`^prefix/.*`); a file entry
    matches only that exact internal path (`^path$`). Each path is escaped so slashes stay
    literal separators while any other regex metacharacter in a real filename is neutralized.
    """
    if not items:
        raise ValueError("No hay ninguna selección para generar un regex")

    parts = []
    for path, is_folder in items:
        normalized = path.strip("/")
        escaped = re.escape(normalized)
        if is_folder:
            parts.append(f"^{escaped}/.*")
        else:
            parts.append(f"^{escaped}$")
    return f"(?:{'|'.join(parts)})"
