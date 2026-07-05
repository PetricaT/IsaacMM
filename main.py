import faulthandler
import sys
import traceback

if sys.stderr is None:
    try:
        sys.stderr = open("crash.log", "w", 1)
    except Exception:
        import io
        sys.stderr = io.StringIO()

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from source import config
from source.window import DragApp

if __name__ == "__main__":
    trace_mode = "--trace" in sys.argv
    if trace_mode:
        sys.argv.remove("--trace")
        try:
            faulthandler.enable(sys.stderr)
        except (io.UnsupportedOperation, AttributeError):
            pass

        def _excepthook(etype, val, tb):
            traceback.print_exception(etype, val, tb)
            if sys.stderr is not None:
                sys.stderr.flush()

        sys.excepthook = _excepthook

        def _qt_msg_handler(msg_type, context, message):
            if sys.stderr is not None:
                sys.stderr.write(f"[Qt {msg_type}] {message}\n")
                sys.stderr.flush()

        qInstallMessageHandler(_qt_msg_handler)

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
