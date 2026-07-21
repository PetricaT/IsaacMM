"""Self-update logic — GitHub release check, download, AppImage update."""
from .updater import (
    get_latest_release,
    is_newer_version,
    get_download_asset,
    get_appimage_path,
    is_appimage,
    find_appimageupdatetool,
    run_appimage_delta_update,
    download_asset,
    install_appimage_update,
    install_windows_update,
)
