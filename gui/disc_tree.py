"""Builds a checkable QTreeWidget from the flat (internal_path, filename, size) tuples
that every ContainerAdapter.walk() yields, and handles checkbox propagation.
"""
from typing import Iterable, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

_PATH_ROLE = Qt.ItemDataRole.UserRole


class _Node:
    """One folder or file in the in-memory tree built from the container's flat entry list."""

    def __init__(self, name: str, full_path: str, is_folder: bool):
        self.name = name
        self.full_path = full_path
        self.is_folder = is_folder
        self.size: Optional[int] = None
        self.children: dict = {}  # name -> _Node, only populated for folders


def _build_tree(entries: Iterable[Tuple[str, str, int]]) -> _Node:
    root = _Node("", "", True)
    for internal_path, filename, size in entries:
        parts = [p for p in internal_path.strip("/").split("/") if p]
        dir_parts = parts[:-1] if parts else []
        node = root
        path_acc = ""
        for part in dir_parts:
            path_acc = f"{path_acc}/{part}" if path_acc else part
            child = node.children.get(part)
            if child is None:
                child = _Node(part, path_acc, True)
                node.children[part] = child
            node = child
        file_node = _Node(filename, internal_path, False)
        file_node.size = size
        node.children[filename] = file_node
    return root


def _format_size(size: Optional[int]) -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _add_children(parent_node: _Node, parent_item: QTreeWidgetItem) -> None:
    folder_names = sorted(name for name, n in parent_node.children.items() if n.is_folder)
    file_names = sorted(name for name, n in parent_node.children.items() if not n.is_folder)
    for name in folder_names + file_names:
        child_node = parent_node.children[name]
        item = QTreeWidgetItem(parent_item, [name, _format_size(child_node.size)])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        item.setData(0, _PATH_ROLE, (child_node.full_path, child_node.is_folder))
        if child_node.is_folder:
            _add_children(child_node, item)


def populate_tree(tree_widget: QTreeWidget, entries: Iterable[Tuple[str, str, int]]) -> None:
    """Clear and repopulate tree_widget from a container's flat walk() entries."""
    tree_widget.clear()
    root = _build_tree(entries)
    _add_children(root, tree_widget.invisibleRootItem())


def install_checkbox_propagation(tree_widget: QTreeWidget) -> None:
    """Wire parent<->child checkbox propagation: checking a folder checks all its
    descendants; a folder reflects Checked/Unchecked/PartiallyChecked based on its children.
    """
    guard = {"updating": False}

    def _set_children_state(item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            _set_children_state(child, state)

    def _update_ancestors(item: Optional[QTreeWidgetItem]) -> None:
        while item is not None:
            states = {item.child(i).checkState(0) for i in range(item.childCount())}
            if states == {Qt.CheckState.Checked}:
                item.setCheckState(0, Qt.CheckState.Checked)
            elif states == {Qt.CheckState.Unchecked}:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            else:
                item.setCheckState(0, Qt.CheckState.PartiallyChecked)
            item = item.parent()

    def _on_item_changed(item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or guard["updating"]:
            return
        guard["updating"] = True
        try:
            state = item.checkState(0)
            if state != Qt.CheckState.PartiallyChecked:
                _set_children_state(item, state)
            _update_ancestors(item.parent())
        finally:
            guard["updating"] = False

    tree_widget.itemChanged.connect(_on_item_changed)


def collect_checked(tree_widget: QTreeWidget) -> List[Tuple[str, bool]]:
    """Return (internal_path, is_folder) for every fully-checked node, stopping at the
    first fully-checked ancestor so a checked folder doesn't also list its children.
    """
    result: List[Tuple[str, bool]] = []

    def _walk(item: QTreeWidgetItem) -> None:
        state = item.checkState(0)
        if state == Qt.CheckState.Unchecked:
            return
        if state == Qt.CheckState.Checked:
            result.append(item.data(0, _PATH_ROLE))
            return
        for i in range(item.childCount()):
            _walk(item.child(i))

    root = tree_widget.invisibleRootItem()
    for i in range(root.childCount()):
        _walk(root.child(i))
    return result
