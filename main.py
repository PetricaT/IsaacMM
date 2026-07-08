import faulthandler
import os
import sys
import traceback

# Safeguard for console=False builds from pyinstaller
if sys.stderr is None:
    try:
        sys.stderr = open("crash.log", "w", 1)
    except Exception:
        import io

        sys.stderr = io.StringIO()

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

# SDL3 Python binding extracts its native .so to a bin/ subdirectory next
# to __init__.py at import time. Inside an AppImage the mount point is
# read-only so this fails. Redirect to a writable temp dir instead.
if os.environ.get("APPIMAGE"):
    import tempfile
    _sdl3_bin = os.path.join(tempfile.gettempdir(), "isaacmm_sdl3_bin")
    os.makedirs(_sdl3_bin, exist_ok=True)
    os.environ["SDL_BINARY_PATH"] = _sdl3_bin

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
