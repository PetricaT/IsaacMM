import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from source import config, paths
from source.window import DragApp

if __name__ == "__main__":
    config.load()

    app = QApplication(sys.argv)
    app.setStyle("fusion")

    if sys.platform == "win32":
        app.setWindowIcon(QIcon("assets/icon.ico"))
    elif sys.platform == "darwin":
        app.setWindowIcon(QIcon("assets/icon.icns"))
    else:
        app.setWindowIcon(QIcon("assets/icon.png"))

    window = DragApp()
    window.show()
    sys.exit(app.exec())
