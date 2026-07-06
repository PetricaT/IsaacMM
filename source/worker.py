"""Generic QThread worker for background tasks."""
from __future__ import annotations


from PySide6.QtCore import QMetaObject, Qt, QThread, Signal, Slot


class WorkerThread(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, name: str = "Worker", **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._result = None
        self._error: str | None = None
        self._done = False
        self.setObjectName(name)

    def run(self):
        self.setObjectName(self.objectName() + " (running)")
        try:
            self._result = self._fn(*self._args, **self._kwargs)
            QMetaObject.invokeMethod(self, "_emit_finished", Qt.QueuedConnection)
        except Exception as exc:
            self._error = str(exc)
            QMetaObject.invokeMethod(self, "_emit_error", Qt.QueuedConnection)

    @Slot()
    def _emit_finished(self) -> None:
        r = self._result
        self._result = None
        self._done = True
        self.finished.emit(r)

    @Slot()
    def _emit_error(self) -> None:
        e = self._error
        self._error = None
        self._done = True
        self.error.emit(e)

    def __del__(self) -> None:
        try:
            if not self.isRunning():
                return
        except RuntimeError:
            return
        WAIT_MS = 15000
        try:
            self.wait(WAIT_MS)
        except RuntimeError:
            return
        try:
            if self.isRunning():
                import logging as _logging
                _logging.warning(
                    "WorkerThread '%s' still running after %dms wait, "
                    "leaking to prevent crash",
                    self.objectName(), WAIT_MS,
                )
                _LEAKED_THREADS.append(self)
        except RuntimeError:
            pass


_LEAKED_THREADS: list[WorkerThread] = []
