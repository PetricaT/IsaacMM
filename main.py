import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from source import config, paths
from source.window import DragApp

if __name__ == "__main__":
    config.load()

    application = QApplication(sys.argv)
    config._native_style = application.style().name()
    if config.theme != "native":
        application.setStyle(config.theme)

    if sys.platform == "win32":
        application.setWindowIcon(QIcon("assets/icon.ico"))
    elif sys.platform == "darwin":
        application.setWindowIcon(QIcon("assets/icon.icns"))
    else:
        application.setWindowIcon(QIcon("assets/icon.png"))

    main_window = DragApp()
    main_window.show()
    sys.exit(application.exec())
