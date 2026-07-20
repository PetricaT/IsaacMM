"""Watchdog-based live mod folder sync.

Emits ``folder_changed(folder_name)`` when files are created, modified or
deleted inside any mod subfolder, with built-in 500 ms debounce.
"""

from __future__ import annotations

import os
import threading

from PySide6.QtCore import QObject, QTimer, Signal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class _Handler(FileSystemEventHandler):
    MODIFY_EVENTS = {"created", "modified", "deleted", "moved"}

    def __init__(self, watcher: "ModFolderWatcher") -> None:
        super().__init__()
        self._watcher = watcher

    def on_any_event(self, event) -> None:
        if event.event_type not in self.MODIFY_EVENTS:
            return
        if event.is_directory:
            return
        self._watcher._notify_change(event.src_path)


class ModFolderWatcher(QObject):
    """Watches *mods_path* recursively and emits ``folder_changed`` per mod.

    Call ``start(mods_path)`` to begin watching.  Call ``stop()`` before
    shutting down the application.
    """

    folder_changed = Signal(str)
    is_active_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._observer = Observer()
        self._handler = _Handler(self)
        self._changed: set[str] = set()
        self._lock = threading.Lock()
        self._debounce = QTimer(self)
        self._debounce.setInterval(500)
        self._debounce.timeout.connect(self._flush)
        self._watch = None
        self._mods_path = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, mods_path: str) -> None:
        """Begin watching *mods_path* for filesystem changes."""
        self._mods_path = mods_path
        if self._watch is not None:
            self.stop()
        if not os.path.isdir(mods_path):
            return
        self._watch = self._observer.schedule(self._handler, mods_path, recursive=True)
        self._observer.start()
        self._debounce.start()
        self.is_active_changed.emit()

    def stop(self) -> None:
        """Stop watching and clean up the observer thread."""
        self._debounce.stop()
        if self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=3)
        self._watch = None
        with self._lock:
            self._changed.clear()
        self.is_active_changed.emit()

    def clear_pending(self) -> None:
        """Discard all buffered filesystem events without emitting."""
        with self._lock:
            self._changed.clear()

    @property
    def is_active(self) -> bool:
        return self._observer.is_alive()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _notify_change(self, path: str) -> None:
        """Called from the watchdog thread on any filesystem event."""
        folder = self._extract_folder(path)
        if not folder:
            return
        with self._lock:
            self._changed.add(folder)

    def _extract_folder(self, path: str) -> str | None:
        """Extract the mod folder name from an absolute *path*.

        ``/path/to/mods/MyMod/resource/file.png`` → ``"MyMod"``
        """
        if not self._mods_path:
            return None
        rel = os.path.relpath(path, self._mods_path)
        if rel.startswith(".."):
            return None
        parts = rel.replace("\\", "/").split("/", 1)
        return parts[0] if parts else None

    def _flush(self) -> None:
        """Emit all buffered folder names (main thread, called by debounce timer)."""
        with self._lock:
            folders = list(self._changed)
            self._changed.clear()
        for f in folders:
            self.folder_changed.emit(f)
