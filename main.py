import faulthandler
import os
import sys
import traceback

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from source import config
from source.window import DragApp

if __name__ == "__main__":
    trace_mode = "--trace" in sys.argv
    if trace_mode:
        sys.argv.remove("--trace")
        faulthandler.enable()

        def _excepthook(etype, val, tb):
            traceback.print_exception(etype, val, tb)
            sys.stderr.flush()

        sys.excepthook = _excepthook

        def _qt_msg_handler(msg_type, context, message):
            if msg_type >= 3:
                sys.stderr.write(f"[Qt {msg_type}] {message}\n")
                sys.stderr.flush()

        qInstallMessageHandler(_qt_msg_handler)

    config.load()

    application = QApplication(sys.argv)
    config._native_style = application.style().name()
    if config.theme != "native":
        application.setStyle(config.theme)

    qss_path = os.path.join(os.path.dirname(__file__), "assets", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path) as f:
            application.setStyleSheet(f.read())

    if sys.platform == "win32":
        application.setWindowIcon(QIcon("assets/icon.ico"))
    elif sys.platform == "darwin":
        application.setWindowIcon(QIcon("assets/icon.icns"))
    else:
        application.setWindowIcon(QIcon("assets/icon.png"))

    main_window = DragApp()
    main_window.show()
    sys.exit(application.exec())
