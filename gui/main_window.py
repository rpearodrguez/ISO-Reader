"""Main GUI window: explore a container's internal tree and build regex-based searches,
plus a batch tab to configure and run the actual extraction."""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from extractor.batch_runner import discover_containers
from extractor.factory import ContainerFactory, UnsupportedContainerError

from . import config_state
from .direct_extraction_worker import DirectExtractionWorker
from .disc_tree import collect_checked, install_checkbox_propagation, populate_tree
from .extraction_worker import ExtractionWorker
from .regex_builder import build_regex
from .search_dialog import SearchDialog

_OUTPUT_MODES = ["flat", "by_iso", "by_type", "by_search"]


def _container_filter() -> str:
    exts = sorted(ContainerFactory.supported_extensions().keys())
    patterns = " ".join(f"*{ext}" for ext in exts)
    return f"Contenedores soportados ({patterns});;Todos los archivos (*)"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ISO Reader - Explorador y extractor por lotes")
        self.config: dict = config_state.default_config()
        self.config_path: Optional[Path] = None
        self.worker: Optional[ExtractionWorker] = None
        self.direct_worker: Optional[DirectExtractionWorker] = None
        self._current_task_label = ""
        self._current_container_path: Optional[Path] = None
        self._current_entries: list = []

        tabs = QTabWidget()
        tabs.addTab(self._build_explorer_tab(), "Explorar disco")
        tabs.addTab(self._build_batch_tab(), "Batch")
        self.setCentralWidget(tabs)

        self._refresh_searches_table()

    # ---------------------------------------------------------------- Explorer tab
    def _build_explorer_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        pick_row = QHBoxLayout()
        pick_folder_btn = QPushButton("Elegir carpeta de discos…")
        pick_folder_btn.clicked.connect(self._on_pick_explore_folder)
        pick_file_btn = QPushButton("Abrir un archivo…")
        pick_file_btn.clicked.connect(self._on_pick_explore_file)
        pick_row.addWidget(pick_folder_btn)
        pick_row.addWidget(pick_file_btn)
        pick_row.addStretch(1)
        layout.addLayout(pick_row)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Carpeta de destino por defecto:"))
        self.explore_output_dir_edit = QLineEdit()
        self.explore_output_dir_edit.setPlaceholderText("Carpeta donde se guardarán los archivos extraídos")
        dest_row.addWidget(self.explore_output_dir_edit, 1)
        dest_pick_btn = QPushButton("Elegir…")
        dest_pick_btn.clicked.connect(self._on_pick_explore_output_dir)
        dest_row.addWidget(dest_pick_btn)
        layout.addLayout(dest_row)

        body = QHBoxLayout()

        left = QVBoxLayout()
        left.addWidget(QLabel("Contenedores encontrados (doble click para explorar):"))
        self.container_list = QListWidget()
        self.container_list.itemDoubleClicked.connect(self._on_container_double_clicked)
        left.addWidget(self.container_list)
        body.addLayout(left, 1)

        right = QVBoxLayout()
        self.current_container_label = QLabel("(ningún contenedor abierto)")
        right.addWidget(self.current_container_label)
        self.disc_tree_widget = QTreeWidget()
        self.disc_tree_widget.setHeaderLabels(["Nombre", "Tamaño"])
        self.disc_tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        install_checkbox_propagation(self.disc_tree_widget)
        right.addWidget(self.disc_tree_widget, 1)
        body.addLayout(right, 2)

        layout.addLayout(body, 1)

        extract_row = QHBoxLayout()
        extract_btn = QPushButton("Extraer seleccionados")
        extract_btn.clicked.connect(self._on_extract_selected)
        extract_row.addWidget(extract_btn)
        self.explore_status_label = QLabel("")
        extract_row.addWidget(self.explore_status_label, 1)
        layout.addLayout(extract_row)

        generate_row = QHBoxLayout()
        generate_btn = QPushButton("Generar expresión regular")
        generate_btn.clicked.connect(self._on_generate_regex)
        generate_row.addWidget(generate_btn)
        self.regex_output = QLineEdit()
        self.regex_output.setReadOnly(True)
        self.regex_output.setPlaceholderText("Marca carpetas/archivos en el árbol y genera el regex")
        generate_row.addWidget(self.regex_output, 1)
        layout.addLayout(generate_row)

        add_group = QGroupBox("Agregar como búsqueda al config")
        form = QFormLayout(add_group)
        self.new_search_name = QLineEdit()
        self.new_search_subdir = QLineEdit()
        form.addRow("Nombre:", self.new_search_name)
        form.addRow("Carpeta de salida (output_subdir):", self.new_search_subdir)
        add_btn = QPushButton("Agregar a config")
        add_btn.clicked.connect(self._on_add_search)
        form.addRow(add_btn)
        layout.addWidget(add_group)

        return widget

    def _on_pick_explore_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de discos")
        if not folder:
            return
        containers = discover_containers(Path(folder))
        self.container_list.clear()
        for path in containers:
            item = QListWidgetItem(str(path.relative_to(folder)))
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.container_list.addItem(item)
        if not containers:
            QMessageBox.information(self, "Sin resultados", "No se encontraron contenedores soportados en esa carpeta.")

    def _on_pick_explore_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Abrir contenedor", "", _container_filter())
        if not file_path:
            return
        self._open_container(Path(file_path))

    def _on_container_double_clicked(self, item: QListWidgetItem) -> None:
        self._open_container(Path(item.data(Qt.ItemDataRole.UserRole)))

    def _on_pick_explore_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Elegir carpeta de destino por defecto")
        if folder:
            self.explore_output_dir_edit.setText(folder)

    def _open_container(self, container_path: Path) -> None:
        try:
            adapter = ContainerFactory.create(container_path)
        except UnsupportedContainerError as exc:
            QMessageBox.warning(self, "Formato no soportado", str(exc))
            return
        try:
            with adapter:
                entries = list(adapter.walk())
        except Exception as exc:
            QMessageBox.critical(self, "Error al abrir", f"No se pudo leer {container_path.name}:\n{exc}")
            return
        self.current_container_label.setText(str(container_path))
        self._current_container_path = container_path
        self._current_entries = entries
        populate_tree(self.disc_tree_widget, entries)
        self.regex_output.clear()
        self.explore_status_label.clear()

    def _on_generate_regex(self) -> None:
        checked = collect_checked(self.disc_tree_widget)
        if not checked:
            QMessageBox.information(self, "Nada seleccionado", "Marca al menos una carpeta o archivo en el árbol.")
            return
        self.regex_output.setText(build_regex(checked))

    def _expand_selection_to_files(self, checked: list) -> list:
        """Turn (path, is_folder) selections into a flat list of (internal_path, filename)
        pairs, using the currently open container's walk() entries to resolve folders to
        the files they contain."""
        file_paths = {path for path, is_folder in checked if not is_folder}
        folder_paths = [path for path, is_folder in checked if is_folder]
        result = []
        seen = set()
        for internal_path, filename, _size in self._current_entries:
            normalized = internal_path.strip("/")
            matches = internal_path in file_paths or any(
                normalized == folder or normalized.startswith(folder + "/") for folder in folder_paths
            )
            if matches and internal_path not in seen:
                seen.add(internal_path)
                result.append((internal_path, filename))
        return result

    def _on_extract_selected(self) -> None:
        if self._current_container_path is None:
            QMessageBox.information(self, "Nada abierto", "Abre un contenedor primero.")
            return
        if self.direct_worker is not None and self.direct_worker.isRunning():
            QMessageBox.information(self, "En curso", "Ya hay una extracción en curso.")
            return
        checked = collect_checked(self.disc_tree_widget)
        if not checked:
            QMessageBox.information(self, "Nada seleccionado", "Marca al menos una carpeta o archivo en el árbol.")
            return
        output_dir = self.explore_output_dir_edit.text().strip()
        if not output_dir:
            QMessageBox.information(
                self, "Falta carpeta de destino", "Elige la carpeta de destino por defecto antes de extraer."
            )
            return
        files = self._expand_selection_to_files(checked)
        if not files:
            QMessageBox.information(self, "Nada que extraer", "La selección no contiene archivos.")
            return

        self.explore_status_label.setText(f"Extrayendo 0/{len(files)}…")
        self._extract_total = len(files)
        self._extract_done = 0
        self.direct_worker = DirectExtractionWorker(
            self._current_container_path, files, Path(output_dir)
        )
        self.direct_worker.file_progress.connect(self._on_direct_file_progress)
        self.direct_worker.finished_ok.connect(self._on_direct_extraction_finished)
        self.direct_worker.failed.connect(self._on_direct_extraction_failed)
        self.direct_worker.start()

    def _on_direct_file_progress(self, _internal_path: str) -> None:
        self._extract_done += 1
        self.explore_status_label.setText(f"Extrayendo {self._extract_done}/{self._extract_total}…")

    def _on_direct_extraction_finished(self, extracted: int, errors: list) -> None:
        if errors:
            self.explore_status_label.setText(f"Listo: {extracted} extraídos, {len(errors)} errores.")
            QMessageBox.warning(
                self,
                "Extracción con errores",
                f"Se extrajeron {extracted} archivos.\n\nErrores:\n" + "\n".join(errors[:20]),
            )
        else:
            self.explore_status_label.setText(f"Listo: {extracted} archivos extraídos.")

    def _on_direct_extraction_failed(self, message: str) -> None:
        self.explore_status_label.setText("Error en la extracción.")
        QMessageBox.critical(self, "Error en la extracción", message)

    def _on_add_search(self) -> None:
        regex = self.regex_output.text().strip()
        name = self.new_search_name.text().strip()
        subdir = self.new_search_subdir.text().strip()
        if not regex:
            QMessageBox.information(self, "Falta el regex", "Primero genera la expresión regular.")
            return
        if not name or not subdir:
            QMessageBox.information(self, "Faltan datos", "Completa nombre y carpeta de salida.")
            return
        config_state.add_regex_search(self.config, name, subdir, regex)
        self.new_search_name.clear()
        self.new_search_subdir.clear()
        self.regex_output.clear()
        self._refresh_searches_table()

    # ---------------------------------------------------------------- Batch tab
    def _build_batch_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.source_dir_edit, source_row = self._dir_picker_row("Elegir carpeta de discos a procesar")
        self.output_dir_edit, output_row = self._dir_picker_row("Elegir carpeta de destino")
        form.addRow("Carpeta de discos (source_dir):", source_row)
        form.addRow("Carpeta de destino (output_dir):", output_row)

        self.output_mode_combo = QComboBox()
        self.output_mode_combo.addItems(_OUTPUT_MODES)
        form.addRow("Modo de salida (output_mode):", self.output_mode_combo)

        self.log_file_edit, log_row = self._file_picker_row("Elegir archivo de log")
        self.log_file_edit.setText(self.config["global"]["log_file"])
        form.addRow("Archivo de log (log_file):", log_row)
        layout.addLayout(form)

        config_row = QHBoxLayout()
        load_btn = QPushButton("Cargar config.yaml…")
        load_btn.clicked.connect(self._on_load_config)
        save_btn = QPushButton("Guardar config.yaml…")
        save_btn.clicked.connect(self._on_save_config)
        config_row.addWidget(load_btn)
        config_row.addWidget(save_btn)
        config_row.addStretch(1)
        layout.addLayout(config_row)

        layout.addWidget(QLabel("Búsquedas configuradas:"))
        self.searches_table = QTableWidget(0, 3)
        self.searches_table.setHorizontalHeaderLabels(["Nombre", "Output subdir", "Regla"])
        self.searches_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.searches_table)

        buttons_row = QHBoxLayout()
        add_search_btn = QPushButton("Agregar búsqueda")
        add_search_btn.clicked.connect(self._on_add_batch_search)
        buttons_row.addWidget(add_search_btn)
        edit_search_btn = QPushButton("Editar búsqueda seleccionada")
        edit_search_btn.clicked.connect(self._on_edit_batch_search)
        buttons_row.addWidget(edit_search_btn)
        remove_btn = QPushButton("Quitar búsqueda seleccionada")
        remove_btn.clicked.connect(self._on_remove_search)
        buttons_row.addWidget(remove_btn)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        run_row = QHBoxLayout()
        run_btn = QPushButton("Ejecutar extracción")
        run_btn.clicked.connect(self._on_run_extraction)
        run_row.addWidget(run_btn)
        self.progress_bar = QProgressBar()
        run_row.addWidget(self.progress_bar, 1)
        layout.addLayout(run_row)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        layout.addWidget(self.log_console, 1)

        return widget

    def _dir_picker_row(self, dialog_title: str):
        edit = QLineEdit()
        btn = QPushButton("Elegir…")

        def pick() -> None:
            folder = QFileDialog.getExistingDirectory(self, dialog_title)
            if folder:
                edit.setText(folder)

        btn.clicked.connect(pick)
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(edit, 1)
        row_layout.addWidget(btn)
        return edit, row_widget

    def _file_picker_row(self, dialog_title: str):
        edit = QLineEdit()
        btn = QPushButton("Elegir…")

        def pick() -> None:
            file_path, _ = QFileDialog.getSaveFileName(self, dialog_title, edit.text() or "extraction.csv")
            if file_path:
                edit.setText(file_path)

        btn.clicked.connect(pick)
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(edit, 1)
        row_layout.addWidget(btn)
        return edit, row_widget

    def _refresh_searches_table(self) -> None:
        searches = self.config.get("searches", [])
        self.searches_table.setRowCount(len(searches))
        for row, search in enumerate(searches):
            self.searches_table.setItem(row, 0, QTableWidgetItem(search.get("name", "")))
            self.searches_table.setItem(row, 1, QTableWidgetItem(search.get("output_subdir", "")))
            self.searches_table.setItem(row, 2, QTableWidgetItem(config_state.summarize_match(search.get("match", []))))

    def _on_remove_search(self) -> None:
        row = self.searches_table.currentRow()
        if row < 0:
            return
        config_state.remove_search(self.config, row)
        self._refresh_searches_table()

    def _on_add_batch_search(self) -> None:
        dialog = SearchDialog(self, title="Agregar búsqueda")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, subdir, extensions, path_contains, filename_contains = dialog.values()
        if not name or not subdir:
            QMessageBox.information(self, "Faltan datos", "Completa nombre y carpeta de salida.")
            return
        if not extensions and not path_contains and not filename_contains:
            QMessageBox.information(
                self,
                "Falta la regla",
                "Completa al menos extensiones, ruta contiene o nombre contiene.",
            )
            return
        config_state.add_search(self.config, name, subdir, extensions, path_contains, filename_contains)
        self._refresh_searches_table()

    def _on_edit_batch_search(self) -> None:
        row = self.searches_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Nada seleccionado", "Selecciona una búsqueda de la tabla primero.")
            return
        search = self.config["searches"][row]
        if not config_state.is_simple_search(search):
            QMessageBox.information(
                self,
                "No editable",
                "Esta búsqueda tiene una regla que este editor simple no puede representar "
                "(regex, múltiples reglas OR, o source_dir propio). Editá el config.yaml a mano "
                "o quitala y volvela a crear.",
            )
            return
        rule = search.get("match", [{}])[0]
        dialog = SearchDialog(self, title="Editar búsqueda")
        dialog.set_values(
            search.get("name", ""),
            search.get("output_subdir", ""),
            rule.get("extensions") or [],
            rule.get("path_contains", ""),
            rule.get("filename_contains", ""),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, subdir, extensions, path_contains, filename_contains = dialog.values()
        if not name or not subdir:
            QMessageBox.information(self, "Faltan datos", "Completa nombre y carpeta de salida.")
            return
        if not extensions and not path_contains and not filename_contains:
            QMessageBox.information(
                self,
                "Falta la regla",
                "Completa al menos extensiones, ruta contiene o nombre contiene.",
            )
            return
        config_state.update_search(self.config, row, name, subdir, extensions, path_contains, filename_contains)
        self._refresh_searches_table()

    def _sync_config_from_form(self) -> None:
        self.config["global"]["source_dir"] = self.source_dir_edit.text().strip()
        self.config["global"]["output_dir"] = self.output_dir_edit.text().strip()
        self.config["global"]["output_mode"] = self.output_mode_combo.currentText()
        self.config["global"]["log_file"] = self.log_file_edit.text().strip() or "extraction.csv"

    def _apply_config_to_form(self) -> None:
        global_cfg = self.config.get("global", {})
        self.source_dir_edit.setText(global_cfg.get("source_dir", ""))
        self.output_dir_edit.setText(global_cfg.get("output_dir", ""))
        mode = global_cfg.get("output_mode", "by_iso")
        index = self.output_mode_combo.findText(mode)
        self.output_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.log_file_edit.setText(global_cfg.get("log_file", "extraction.csv"))
        self._refresh_searches_table()

    def _on_load_config(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Cargar config.yaml", "", "YAML (*.yaml *.yml)")
        if not file_path:
            return
        try:
            self.config = config_state.load_config(Path(file_path))
        except Exception as exc:
            QMessageBox.critical(self, "Error al cargar", str(exc))
            return
        self.config_path = Path(file_path)
        self._apply_config_to_form()

    def _on_save_config(self) -> None:
        self._sync_config_from_form()
        default_name = str(self.config_path) if self.config_path else "config.yaml"
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar config.yaml", default_name, "YAML (*.yaml *.yml)")
        if not file_path:
            return
        try:
            config_state.save_config(Path(file_path), self.config)
        except Exception as exc:
            QMessageBox.critical(self, "Error al guardar", str(exc))
            return
        self.config_path = Path(file_path)
        QMessageBox.information(self, "Guardado", f"Config guardada en {file_path}")

    def _on_run_extraction(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, "En curso", "Ya hay una extracción en curso.")
            return
        self._sync_config_from_form()
        if not self.config["global"]["source_dir"] or not self.config["global"]["output_dir"]:
            QMessageBox.information(self, "Faltan datos", "Elige la carpeta de discos y la carpeta de destino.")
            return
        if not self.config.get("searches"):
            QMessageBox.information(self, "Sin búsquedas", "Agrega al menos una búsqueda antes de ejecutar.")
            return

        self.log_console.clear()
        self.progress_bar.setValue(0)
        self.worker = ExtractionWorker(self.config)
        self.worker.container_started.connect(self._on_worker_container_started)
        self.worker.file_progress.connect(self._on_worker_file_progress)
        self.worker.container_error.connect(lambda msg: self.log_console.appendPlainText(f"ERROR: {msg}"))
        self.worker.source_missing.connect(lambda path: self.log_console.appendPlainText(f"Carpeta no encontrada: {path}"))
        self.worker.file_error.connect(self._on_worker_file_error)
        self.worker.container_finished.connect(self._on_worker_container_finished)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.failed.connect(lambda msg: QMessageBox.critical(self, "Error en la extracción", msg))
        self.worker.start()

    def _on_worker_container_started(self, name: str, total: int) -> None:
        self._current_task_label = name
        self.progress_bar.setMaximum(max(total, 1))
        self.progress_bar.setValue(0)
        self.log_console.appendPlainText(f"Explorando {name} ({total} archivos)…")

    def _on_worker_file_progress(self) -> None:
        self.progress_bar.setValue(self.progress_bar.value() + 1)

    def _on_worker_file_error(self, internal_path: str, message: str) -> None:
        self.log_console.appendPlainText(f"  ERROR extrayendo {internal_path}: {message}")

    def _on_worker_container_finished(self, name: str, counts: dict) -> None:
        self.log_console.appendPlainText(
            f"  {name}: {counts['matched']} coincidencias, {counts['extracted']} extraídos, "
            f"{counts['skipped']} saltados, {counts['errors']} errores"
        )

    def _on_worker_finished(self, stats: dict) -> None:
        self.log_console.appendPlainText("Extracción terminada.")
        for name, counts in stats.items():
            self.log_console.appendPlainText(
                f"  {name}: matched={counts['matched']} extracted={counts['extracted']} "
                f"skipped={counts['skipped']} errors={counts['errors']}"
            )
