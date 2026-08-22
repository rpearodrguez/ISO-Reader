"""GUI entrypoint: explore disc/archive containers and configure/run batch extraction."""
import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1100, 750)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
