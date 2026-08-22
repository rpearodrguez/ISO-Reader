"""Modal dialog for adding or editing a simple search (name, output_subdir, and a single
AND-combined extensions/path_contains/filename_contains rule), used by the Batch tab so the
form doesn't have to sit permanently inline."""
from typing import List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)


class SearchDialog(QDialog):
    def __init__(self, parent=None, title: str = "Agregar búsqueda"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)

        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.subdir_edit = QLineEdit()
        self.extensions_edit = QLineEdit()
        self.extensions_edit.setPlaceholderText(".mp3, .mp2, .wma, .wav")
        self.path_contains_edit = QLineEdit()
        self.path_contains_edit.setPlaceholderText("Opcional, ej: RADIO")
        self.filename_contains_edit = QLineEdit()
        self.filename_contains_edit.setPlaceholderText("Opcional")
        layout.addRow("Nombre:", self.name_edit)
        layout.addRow("Carpeta de salida (output_subdir):", self.subdir_edit)
        layout.addRow("Extensiones (coma):", self.extensions_edit)
        layout.addRow("La ruta contiene:", self.path_contains_edit)
        layout.addRow("El nombre contiene:", self.filename_contains_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def set_values(
        self,
        name: str,
        output_subdir: str,
        extensions: List[str],
        path_contains: str,
        filename_contains: str,
    ) -> None:
        self.name_edit.setText(name)
        self.subdir_edit.setText(output_subdir)
        self.extensions_edit.setText(", ".join(extensions))
        self.path_contains_edit.setText(path_contains)
        self.filename_contains_edit.setText(filename_contains)

    def values(self) -> Tuple[str, str, List[str], str, str]:
        extensions = [e.strip() for e in self.extensions_edit.text().split(",") if e.strip()]
        return (
            self.name_edit.text().strip(),
            self.subdir_edit.text().strip(),
            extensions,
            self.path_contains_edit.text().strip(),
            self.filename_contains_edit.text().strip(),
        )
