"""Generic QThread worker for background tasks."""
from __future__ import annotations


import platform
from typing import Optional

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, Signal, Slot


def _get_rss_mb() -> float:
    """Return current process RSS in MB (best-effort, cross-platform)."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            from ctypes import wintypes

            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            class _PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            pmc = _PMC()
            pmc.cb = ctypes.sizeof(pmc)
            if psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(),
                ctypes.byref(pmc),
                ctypes.sizeof(pmc),
            ):
                return pmc.WorkingSetSize / (1024 * 1024)
        elif system == "Linux":
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024.0
        else:  # macOS / BSD
            import resource

            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if system == "Darwin":
                return rss / (1024 * 1024)
            return rss / 1024.0
    except Exception:
        pass
    return 0.0


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
                rss = _get_rss_mb()
                _logging.warning(
                    "WorkerThread '%s' still running after %dms wait "
                    "(RSS: %.1f MB), leaking to prevent crash",
                    self.objectName(), WAIT_MS, rss,
                )
                _LEAKED_THREADS.append(self)
        except RuntimeError:
            pass


_LEAKED_THREADS: list[WorkerThread] = []


class ManagedWorker(QObject):
    """
    Owns a single WorkerThread slot. Safe to use as an instance attribute.
    Guarantees: only one thread runs at a time, thread is waited on owner
    destruction, result signals only fire if not superseded.

    Usage:
        class MyWidget(QWidget):
            def __init__(self):
                self._load = ManagedWorker(parent=self)
                self._load.finished.connect(self._on_loaded)
                self._load.error.connect(self._on_error)

            def reload(self):
                self._load.start(my_fn, arg1, arg2, name="Load")
    """
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self._thread: WorkerThread | None = None
        self._generation: int = 0

    @property
    def is_running(self) -> bool:
        t = self._thread
        if t is None:
            return False
        try:
            return t.isRunning()
        except RuntimeError:
            return False

    def start(self, fn, *args, name: str = "Worker", cancel_running: bool = False, **kwargs) -> bool:
        """
        Launch fn(*args, **kwargs) in a background thread.
        Returns False and does nothing if already running and cancel_running=False.
        If cancel_running=True, waits up to 3s for current thread to finish.
        """
        if self._thread is not None:
            try:
                if self._thread.isRunning():
                    if not cancel_running:
                        return False
                    self._thread.wait(3000)
            except RuntimeError:
                pass

        gen = self._generation + 1
        self._generation = gen

        thread = WorkerThread(fn, *args, name=name, **kwargs)
        thread.finished.connect(lambda r, g=gen: self._on_finished(r, g))
        thread.error.connect(lambda e, g=gen: self._on_error(e, g))
        self._thread = thread
        thread.start()
        return True

    def wait(self, msecs: int = 5000) -> None:
        t = self._thread
        if t is not None:
            try:
                if t.isRunning():
                    t.wait(msecs)
            except RuntimeError:
                pass

    def _on_finished(self, result: object, gen: int) -> None:
        if gen != self._generation:
            return
        QTimer.singleShot(0, lambda g=gen, r=result: self._emit_finished(g, r))

    def _on_error(self, msg: str, gen: int) -> None:
        if gen != self._generation:
            return
        QTimer.singleShot(0, lambda g=gen, m=msg: self._emit_error(g, m))

    def _emit_finished(self, gen: int, result: object) -> None:
        if gen != self._generation:
            return
        self._thread = None
        self.finished.emit(result)

    def _emit_error(self, gen: int, msg: str) -> None:
        if gen != self._generation:
            return
        self._thread = None
        self.error.emit(msg)
