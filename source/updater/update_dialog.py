"""Update dialog widget."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


def _get_full_download_path() -> str:
    suffix = (
        "-x86_64.AppImage"
        if platform.system() == "Linux"
        else ".exe" if platform.system() == "Windows" else ".dmg"
    )
    return tempfile.mktemp(suffix=suffix)


class UpdateDialog(QDialog):
    def __init__(
        self,
        current_version: str,
        new_version: str,
        changelog: str,
        download_url: str,
        parent=None,
    ):
        super().__init__(parent)
        self._download_url = download_url
        self._download_path: Optional[str] = None

        self.setWindowTitle("Update Available")
        self.setMinimumSize(480, 360)

        layout = QVBoxLayout(self)

        header = QLabel(
            f"A new version is available: <b>{new_version}</b>"
            f"<br>(you have <b>{current_version}</b>)"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self._changelog = QTextBrowser()
        self._changelog.setOpenExternalLinks(True)
        self._changelog.setPlainText(changelog or "(no release notes)")
        layout.addWidget(self._changelog)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel()
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        buttons = QDialogButtonBox()
        self._install_btn = buttons.addButton(
            "Download && Install", QDialogButtonBox.ActionRole
        )
        self._open_btn = buttons.addButton(
            "Open Release Page", QDialogButtonBox.ActionRole
        )
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not download_url:
            self._install_btn.setVisible(False)
            self._status_label.setText(
                "No download available for your platform. Open the release page instead."
            )
            self._status_label.setVisible(True)

        self._install_btn.clicked.connect(self._on_install)
        self._open_btn.clicked.connect(self._on_open)

    def _on_open(self) -> None:
        from .updater import RELEASES_URL

        QDesktopServices.openUrl(RELEASES_URL)

    def _on_install(self) -> None:
        self._install_btn.setEnabled(False)
        self._open_btn.setEnabled(False)

        from .updater import (
            find_appimageupdatetool,
            is_appimage,
            run_appimage_delta_update,
        )

        if is_appimage() and find_appimageupdatetool():
            self._progress.setVisible(True)
            self._progress.setRange(0, 0)
            self._status_label.setVisible(True)
            self._status_label.setText("Applying delta update...")
            from ..core.worker import ManagedWorker

            self._dl_worker = ManagedWorker(parent=self)
            self._dl_worker.finished.connect(self._on_delta_done)
            self._dl_worker.error.connect(self._on_delta_error)
            self._dl_worker.start(run_appimage_delta_update, name="DeltaUpdate")
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._status_label.setVisible(True)
        self._status_label.setText("Downloading...")
        self._start_full_download()

    def _on_downloaded(self, ok: bool, path: str) -> None:
        from .updater import (
            install_appimage_update,
            install_windows_update,
            is_appimage,
            RELEASES_URL,
        )

        if not ok:
            self._status_label.setText("Download failed. Check your connection.")
            self._install_btn.setEnabled(True)
            self._open_btn.setEnabled(True)
            return

        self._download_path = path
        self._status_label.setText("Download complete. Installing...")

        if is_appimage():
            self.accept()
            install_appimage_update(path)
        elif platform.system() == "Windows" and getattr(sys, "frozen", False):
            self.accept()
            install_windows_update(path)
        elif platform.system() == "Linux":
            self._status_label.setText(
                f"Downloaded to: {path}\n"
                "Not running as AppImage. Make it executable and run it."
            )
            self._install_btn.setVisible(False)
            QDesktopServices.openUrl(RELEASES_URL)
        else:
            self._status_label.setText(f"Downloaded to: {path}")
            self._install_btn.setVisible(False)
            QDesktopServices.openUrl(RELEASES_URL)

    def download_path(self) -> Optional[str]:
        return self._download_path

    def _on_delta_done(self, ok: bool) -> None:
        import os
        import sys

        from .updater import get_appimage_path

        if ok:
            self._status_label.setText("Update applied. Restarting...")
            self._progress.setRange(0, 100)
            self._progress.setValue(100)
            self.accept()
            appimage = get_appimage_path()
            if appimage:
                QTimer.singleShot(
                    1500,
                    lambda: os.execv(appimage, [appimage] + sys.argv[1:]),
                )
        else:
            self._status_label.setText(
                "Delta update failed. Falling back to full download..."
            )
            self._progress.setRange(0, 100)
            self._progress.setValue(0)
            self._start_full_download()

    def _on_delta_error(self, msg: str) -> None:
        self._status_label.setText(
            "Delta update failed. Falling back to full download..."
        )
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._start_full_download()

    def _start_full_download(self) -> None:
        from .updater import download_asset

        tmp = _get_full_download_path()

        def _progress(pct: float) -> None:
            QTimer.singleShot(0, lambda: self._progress.setValue(int(pct * 100)))

        def _do_download() -> bool:
            return download_asset(self._download_url, tmp, _progress)

        from ..core.worker import ManagedWorker

        self._dl_worker = ManagedWorker(parent=self)
        self._dl_worker.finished.connect(lambda ok: self._on_downloaded(ok, tmp))
        self._dl_worker.error.connect(lambda _: None)
        self._dl_worker.start(_do_download, name="UpdateDownload")
