# IsaacMM - Improvement Progress Tracker

> **For AI agents:** This file is the single source of truth for planned and completed work.
> When implementing any item, update its status block immediately.
> Status values: `[ ]` not started · `[~]` in progress · `[x]` complete · `[!]` blocked
> Add notes, blockers, and completion dates inline under each item.
> Do not reorder sections - append new items to the relevant section.

---

## HOW TO READ THIS FILE

Each item follows this structure:

```
- [ ] ITEM_NAME - short description
      Lib/API: `library_name`
      Files: source files to create or modify
      Notes: extra context, gotchas, dependencies on other items
      Blocked by: other item names if applicable
```

---

## SECTION 1 - DROP-IN SIMPLIFICATIONS

These replace existing code with no new user-facing features. Do these first.

---

- [x] PLATFORMDIRS - Replace manual AppDirs block in `paths.py`
      Completed: 2026-07-07
      Lib: `platformdirs`
      Files: `source/paths.py`, `requirements.txt`, `pyproject.toml`
      Notes: `PlatformDirs("IsaacMM", "PetricaT")` gives `.user_data_dir`,
             `.user_config_dir`, `.user_cache_dir` correctly on all platforms
             including XDG on Linux. Remove the entire manual
             Windows/macOS/Linux conditional block. Backwards-compatible paths -
             verify the resolved dirs match existing ones before removing the old
             logic so existing user data is not orphaned.

- [x] LOGURU - Replace logger.py with loguru
      Completed: 2026-07-07
      Lib: `loguru`
      Files: `source/logger.py`, `source/components/dialogs.py`, `requirements.txt`,
             `pyproject.toml`
      Notes: Rewrote `source/logger.py` using loguru internally. Kept same
             `log(level, msg)`, `set_handler(callable)` public API so zero
             import changes were needed across the rest of the codebase.
             Added `set_level(level)` for runtime log-level changes, called
             from settings dialog `_save_settings()`. Removed `_handler`
             global and `LOG_LEVELS` dict. Added loguru to deps.

- [x] HTTPX - Replace urllib in remote_cache.py and workshop.py
      Completed: 2026-07-07
      Lib: `httpx`, `tenacity`
      Files: `source/remote_cache.py`, `source/components/workshop.py`,
             `source/game_versions.py`, `requirements.txt`, `pyproject.toml`
      Notes: Removed `ssl`, `urllib.*` imports. Replaced `urlopen` with
             `httpx.Client(follow_redirects=True)`. Added `@retry` on
             transport-level errors (`httpx.RequestError`) with 3 attempts
             and exponential backoff (1s–10s) on `_http_get_text`,
             `_fetch_published_file_details`, and `_scrape_workshop_dates`.
             Changed `on_http_error` callback type from `HTTPError` to
             `httpx.HTTPStatusError` and updated `game_versions.py` caller.
             Removed manual SSL context construction. Added httpx + tenacity
             to deps.

- [x] PACKAGING-VERSION - Fix version comparison in backup.py
      Completed: 2026-07-07
      Lib: `packaging`
      Files: `source/backup.py`, `source/window.py`, `requirements.txt`,
             `pyproject.toml`
      Notes: Replaced string comparison `current_version != backup_version`
             with `Version(current_version) != Version(backup_version)` in
             `backup_needed()`. Falls back to string comparison on
             `InvalidVersion`. `backup_all()` now returns 4-tuples
             `(name, old_ver, new_ver, magnitude)` where magnitude is
             ``"major"``/``"minor"``/``"patch"``/``"?"`` based on which
             semver field changed. Updated `_on_backup_finished` in
             `window.py` to unpack the extra field.

- [x] RAPIDFUZZ - Fuzzy search for mod list filter
      Completed: 2026-07-07
      Lib: `rapidfuzz`
      Files: `source/components/modlist.py`, `requirements.txt`, `pyproject.toml`
      Notes: Added QLineEdit search bar below "Mod List" header. On text
             change, `rapidfuzz.process.extract(query, names,
             score_cutoff=60)` matches rows. Extra pass against
             `NORMALIZED_NAME_ROLE` for loose prefix matches. Non-matching
             rows hidden via `setRowHidden()`. Clears filter when query
             empty. Scrolls to best match.

---

## SECTION 1b — BUG FIXES (Windows)

Windows-specific defects found during testing.

---

- [x] SYMLINK-PERMS - Skip symlink setup on Windows
      Files: `source/paths.py`
      Notes: `os.symlink` on Windows requires admin rights or Developer Mode.
             Added `if sys.platform == "win32": return` at the top of
             `setup_symlinks()` so it is a no-op on Windows regardless of
             caller. The `window.py` guard (`if sys.platform != "win32"`) was
             already present but the paths module itself is now self-defending.

- [x] MISSING-METHOD - `_refresh_masterlist_background` not defined
      Files: `source/window.py`
      Notes: `__init__` called `self._refresh_masterlist_background()` at line
             114 but the method was never defined (only
             `_refresh_game_versions_background` existed). Added the missing
             method. Also removed a duplicate `_masterlist_timer` creation in
             `_on_update_check_done` that would have created a second hourly
             timer.

- [x] OPEN-BTN-GUARD - Disable folder-open buttons if target does not exist
      Files: `source/components/dialogs.py`
      Notes: "Open Config", "Open Data", "Open Cache" buttons in the Settings
             Paths group called `open_path()` unconditionally. On Windows the
             cache dir doesn't exist until something writes to it, causing
             `ShellExecute` error 2. Fixed by calling
             `.setEnabled(os.path.isdir(...))` on each button at init time.
             Buttons no longer try to create folders, they only enable when
             the directory already exists.

- [x] SEARCH-ROW-HIDDEN - Wrong `setRowHidden` signature for PySide6
      Files: `source/components/modlist.py`
      Notes: Called `QTreeView.setRowHidden(row, hidden)` with 2 args; PySide6
             requires 3: `(row, parent, hidden)`. Added `QModelIndex()` as the
             parent argument in both `_filter_mods` call sites, and imported
             `QModelIndex`.

---

## SECTION 2 — ARCHITECTURE & STATE ✅

These touch the data layer and unlock multiple features downstream.

---

- [x] SQLITE-STATE - Consolidate state files into SQLite
      Completed: 2026-07-08
      Lib: `sqlite3` (stdlib)
      Files: `source/database.py`, `source/config.py`, `source/sorter.py`,
             `source/components/workshop.py`
      Notes: Created `source/database.py` with workshop_items and
             load_order_history tables in WAL mode. One-shot migration on first
             run imports from old `last_order.yaml` and
             `workshop_details.json`. `sorter.save/load_last_order` now reads
             from DB. Config fields `workshop_timestamps` and
             `dead_workshop_ids` removed from config.toml. Workshop rate-limiter
             timestamps kept purely in-memory (no longer persisted). Workshop
             details cache replaced with DB queries. Workshop status (dead)
             stored in `workshop_items.status` column. DB at
             `paths.appdata / isaacmm.db`.

- [x] SQLITE-MIGRATIONS - DB schema versioning and migration mechanism
      Completed: 2026-07-08
      Lib: `sqlite3` (stdlib)
      Files: `source/database.py`
      Notes: Formalized the MIGRATIONS dict pattern (`MIGRATIONS = {1: _migrate_v1}`).
             On every init, the framework compares `PRAGMA user_version` against
             MIGRATIONS keys and runs each pending migration in order inside a
             transaction. Failed migrations roll back and raise. Each migration
             function is idempotent. The old `_migrate()` function was renamed
             to `_migrate_v1` (imports from last_order.yaml and
             workshop_details.json). Schema v1 tables are created with
             `CREATE TABLE IF NOT EXISTS` in init(), outside the migration
             framework, so a fresh DB gets tables at version 0 and v1 migration
             adds the fallback "init" row.

- [x] CONFLICT-INDEX - File-level conflict detection
      Completed: 2026-07-08
      Lib: `hashlib.blake2b` (stdlib, dropped `blake3` to avoid C-extension dep)
      Files: new file `source/conflict_index.py`, `source/components/modlist.py`,
             `source/database.py`
      Notes: Build a `dict[relative_path, list[mod_folder]]` by walking each
             enabled mod's folder. Any entry with >1 mod is a conflict. Winner is
             mods[0] (highest in load order), losers are everything after.
             Use blake2b to fingerprint each mod folder (hash of all relative file
             paths + mtimes concatenated). Store fingerprint in DB alongside the
             index. On next launch, only re-index mods whose fingerprint changed.
             Uses a two-level cache: quick token (dir mtime + top-level entry mtimes)
             avoids full walk for unchanged mods; full walk computes blake2b
             fingerprint + file set for changed mods. Replaced
             `_scan_mod_files_for_cache` with `get_cached_files` from
             `conflict_index.py`. DB migration v2 adds `mod_fingerprints` table
             with `(folder, fingerprint, files_json, token, updated_at)`.
             No hashing needed for detection itself - only for cache invalidation.
             Used `hashlib.blake2b` instead of third-party `blake3` — stdlib,
             same security properties, no build/AppImage complications.
      Blocked by: SQLITE-STATE

---

## SECTION 3 - UX FEATURES

New user-facing functionality. Implement after Section 1 is stable.

---

- [x] WATCHDOG - Live mod folder sync
      Completed: 2026-07-08
      Lib: `watchdog`
      Files: new file `source/folder_watcher.py`, `source/components/modlist.py`,
             `source/window.py`, `requirements.txt`
      Notes: Watch `config.mods_path` for `FileCreatedEvent`, `FileDeletedEvent`,
             `FileModifiedEvent`. On event, debounce 500ms then trigger a mod list
             rescan. Run the watchdog observer in a background thread.
             Stop the observer in `window.closeEvent`.
             Update CONFLICT-INDEX incrementally on change events rather than full
             rebuild - only re-index the changed mod folder.
             Add a status indicator in the UI (small icon) showing watcher active/inactive.
             Implemented in source/folder_watcher.py: ModFolderWatcher(QObject) wraps
             watchdog Observer, extracts mod folder name from event path, buffers
             changed folders with a threading.Lock, flushes every 500ms via QTimer
             on main thread. Connected to modlist via set_watcher() which calls
             conflict_index.invalidate() + clears in-memory cache + triggers
             _update_conflict_indicators() for the changed mod only.
             Green dot indicator in modlist header when watcher active, gray when off.
      Blocked by: nothing (can land before CONFLICT-INDEX)

- [x] LOAD-ORDER-HISTORY - Undo/redo for sort operations
      Completed: 2026-07-09
      Lib: `sqlite3` (stdlib, already in SQLITE-STATE)
      Files: `source/database.py`, `source/components/modlist.py`, `source/window.py`
      Notes: On every sort or manual reorder, write current order to
             `load_order_history` table with timestamp and optional label.
             Keep last 50 entries. Expose Ctrl+Z / Ctrl+Y in the mod list to
             step through history.
      Blocked by: SQLITE-STATE

- [x] NOTIFICATIONS - Desktop notifications for async operations
      Completed: 2026-07-13
      Lib: `notify-py`
      Files: new file `source/notifications.py`, `source/window.py`,
             `source/config.py`, `source/components/dialogs.py`,
             `requirements.txt`, `pyproject.toml`
      Notes: Send notifications for: backup complete (after manual backup),
             update available (new version found on silent check).
             Make notification opt-in via a settings toggle (Settings → Updates).
             Uses notify-py: on Linux uses libnotify, on macOS osascript,
             on Windows PowerShell toast.
             Wrapper in source/notifications.py handles ImportError gracefully
             and checks config.notifications_enabled before sending.

- [x] UPDATE-CHECKER - Check for new app versions on GitHub
      Completed: 2026-07-13
      Lib: `httpx`, `packaging`
      Files: `source/updater.py`, `source/window.py`,
             `source/components/dialogs.py`, `source/config.py`
      Notes: On launch (and via Help → Check for Updates), query:
             `https://api.github.com/repos/PetricaT/IsaacMM/releases/latest`
             Compare returned `tag_name` against `paths.version` using
             `packaging.version.Version`. If newer: show a non-intrusive banner
             at the top of the main window with version number and action button.
             Do not check more than once per 24h — store last check timestamp
             in a `app_state` key-value table in the DB.
             Gate network call in a ManagedWorker so it never blocks the UI.
             This item is the prerequisite for APPIMAGE-UPDATER and
             TUFUP-AUTOUPDATER — it detects the update, they apply it.
             Background silent checks store pending update and update Settings UI
             label/button without showing a popup. Interactive checks show the
             full UpdateDialog. Replaced urllib with httpx + tenacity retries.
             Added Changelogs button in Settings. Persisted check_updates_on_startup.

- [ ] LAUNCH-GAME - Launch Isaac directly from the app
      Lib: `subprocess` (stdlib)
      Files: `source/components/modlist.py` or `source/window.py`
      Notes: Add a "Launch Isaac" button to the toolbar. On click:
               `open_url("steam://rungameid/250900")`
             Works on all platforms via the existing `file_utils.open_url` —
             Steam protocol URLs are handled by the OS as long as Steam is
             installed and running. If mods_path is empty, show an inline message
             rather than silently doing nothing.
             Optional: "Sort then Launch" combined action that runs auto-sort
             first and launches Isaac only on success.
      Blocked by: nothing

- [ ] UI-LOCK-ON-ACTIVE-GAME - Disable mod list editing while Isaac is running
      Lib: `psutil`
      Files: new file `source/process_watcher.py`, `source/components/modlist.py`,
             `source/window.py`, `requirements.txt`, `pyproject.toml`
      Notes: Poll for Isaac process using `psutil.process_iter(['name'])` every
             5 seconds in a background thread.
             Process names by platform:
               Windows: `isaac-ng.exe`
               macOS: `The Binding of Isaac Afterbirth+`
               Linux: `isaac-ng` (native) or as child of a wine/proton process
             When Isaac detected as running:
               - Set mod list to read-only (disable drag-drop, checkboxes,
                 sort button, all edit actions)
               - Show status banner: "Isaac is running — mod list locked"
               - Disable Sort and Backup buttons
               - Allow read-only actions: search, scroll, view conflicts
             When Isaac exits: automatically unlock and restore full functionality.
             Add "Lock UI when game is running" toggle in settings, default True.
      Blocked by: nothing

- [ ] TRAY-ICON - System tray with background watcher mode
      Lib: `pystray`
      Files: new file `source/tray.py`, `source/window.py`,
             `requirements.txt`, `pyproject.toml`
      Notes: Show tray icon when window is minimized or closed-to-tray.
             Right-click menu: Show Window, Sort Now, Backup Now, Quit.
             Left-click: restore window.
             Add "Close to tray" toggle in settings.
             Pairs with WATCHDOG - in tray mode the watcher stays active so
             Steam mod updates are detected and optionally auto-sorted.
             Use `assets/icon.png` as tray icon.
      Blocked by: WATCHDOG recommended first

---

## SECTION 3b - NATIVE UI INTEGRATION

Improve native look-and-feel by relying on Qt's platform abstraction instead of
hardcoded colors, metrics and styling.

---

- [X] NATIVE-PALETTE - Use QPalette as the single source of UI colors
      Lib: `PySide6.QtGui.QPalette`
      Files: all custom-painted widgets, theme helpers
      Notes: Remove hardcoded QColor values wherever possible. Retrieve colors
             from the active application palette:
               - Window
               - WindowText
               - Base
               - AlternateBase
               - Button
               - ButtonText
               - Highlight
               - HighlightedText
               - Accent (Qt 6.6+, when available)
             All custom widgets should consume colors from the palette rather
             than embedding theme-specific values. This allows automatic support
             for Windows, KDE Plasma, GNOME, macOS, dark mode, and custom system
             themes without platform-specific code.

- [X] NATIVE-STYLE - Follow the platform QStyle
      Lib: `PySide6.QtWidgets.QStyle`
      Files: application startup, custom widgets
      Notes: Do not force the Fusion style. Allow Qt to select the platform
             style automatically (Windows, Breeze, macOS, Adwaita, etc.).
             Avoid style sheets that replace native widget painting.
             Custom widgets should obtain spacing, frame widths and control
             metrics from QStyle rather than hardcoded constants.

- [X] NATIVE-FONTS - Use the operating system UI font
      Lib: `QApplication`, `QFontDatabase`
      Files: application startup
      Notes: Use the application's default font rather than specifying fonts
             manually. This automatically follows:
               - Windows: Segoe UI
               - KDE: configured system font
               - GNOME: configured interface font
               - macOS: San Francisco
             Avoid fixed font sizes except where technically required.

- [x] NATIVE-ICONS - Integrate with platform icon themes
      Completed: 2026-07-09
      Lib: `QStyle`, `QIcon`
      Files: `source/config.py`, `source/widgets.py`, `source/components/dialogs.py`
      Notes: Flipped `config.use_system_icons` default to `True`. On first launch
             the app now prefers `QIcon.fromTheme("folder")` and
             `QIcon.fromTheme("image-x-generic")` over bundled PNGs. On Linux this
             follows the user's desktop icon theme (Breeze, Adwaita, etc.).
             Toggle available in Settings → Appearance. The existing settings
             checkbox and `refresh_icons()` wiring was already in place —
             only the default changed. Controller button artwork remains bundled
             (no native equivalent).
      Lib: `QStyle`, `QIcon`
      Files: toolbar creation, dialogs
      Notes: Prefer `QStyle.standardIcon()` for common actions and
             `QIcon.fromTheme()` for named icons. On Linux this automatically
             follows the user's selected icon theme. Only bundle application-
             specific artwork that has no native equivalent.

- [X] NATIVE-WINDOW - Preserve native window decorations
      Files: main window
      Notes: Continue using the operating system's native window frame.
             Do not implement a custom title bar. This preserves:
               - Window buttons
               - Rounded corners
               - Shadows
               - Accent/title bar colors
               - Platform-specific effects (Mica, KWin decorations, etc.)

- [x] THEME-CHANGE - React to runtime theme changes
      Completed: 2026-07-09
      Lib: `QEvent`
      Files: `source/window.py`
      Notes: `changeEvent` already handled `PaletteChange` (reload QSS +
             re-apply theme). Added `StyleChange` handling. Both now call
             `_refresh_on_theme_change()` which runs `modInfoPanel.refresh_icons()`
             so icon theme changes are picked up immediately.
             Theme switches do not require an application restart.

- [ ] CUSTOM-PAINTING - Use palette and style APIs for all custom rendering
      Blocker: POSTPONED
      Lib: `QPainter`, `QPalette`, `QStyle`
      Files: all custom-painted controls
      Notes: Whenever drawing custom UI, obtain colors from the widget's
             palette and sizing information from QStyle. Avoid hardcoded
             padding, border widths, radii and colors unless they are part
             of the application's visual identity.

- [ ] PLATFORM-THEME-AUDIT - Remove stylesheet-based native overrides
      Blocker: POSTPONED
      Files: all `.setStyleSheet()` usage
      Notes: Audit all stylesheets. Remove any stylesheet whose only purpose
             is recoloring or restyling standard Qt widgets. Restrict
             stylesheets to application branding or widget-specific features
             that cannot be achieved through QStyle/QPalette.

---

## SECTION 3c - THEME ENGINE

Provide a flexible theme system while preserving native Qt integration. Themes
must be able to override only colors, only widget styling, or both.

---

- [x] THEME-LOADER - Implement filesystem-based theme loader
      Completed: 2026-07-13
      Lib: `tomllib` (stdlib), `pathlib`
      Files: `source/theme.py`, `source/config.py`,
             `source/window.py`
      Notes: Discover themes from the `{APP_DATA}/themes/` directory. Each immediate
             subdirectory represents a single theme. A theme may contain any
             combination of:
               - `colors.toml`
               - `style.qss`
             Loading must not require every file to exist. Missing files are
             simply skipped. Deleted dead `source/theme_io.py` (wrong format).
             Added `active_theme: str = "System"` to config, loaded/saved from
             `[settings] active_theme`. Built-in "System" theme always available
             as first entry.

- [x] THEME-FOLDER-FORMAT - Define supported theme layout
      Completed: 2026-07-13
      Files: `themes/`, documentation
      Notes: Supported directory structure:

               themes/
                 System/
                 Dracula/
                   colors.toml
                 Catppuccin/
                   colors.toml
                   colors-light.toml
                   colors-dark.toml
                   style.qss
                 Nord/
                   colors.toml
                   colors-light.toml
                   style.qss

             Valid theme types:
               - TOML only
               - QSS only
               - TOML + QSS

             Light/dark variants:
               - ``colors.toml`` only → used for both light and dark
               - ``colors-light.toml`` + ``colors-dark.toml`` → swapped
                 based on system color scheme hint
               - Scheme-specific file takes precedence over ``colors.toml``

- [x] PALETTE-THEME - Apply palette overrides from `colors.toml`
      Completed: 2026-07-13
      Lib: `QPalette`
      Files: `source/theme.py`
      Notes: Begin with the current native application palette and override only
             the color roles explicitly defined in `colors.toml`. Unspecified
             roles continue using the operating system values.
             Supported roles include (but are not limited to):
               Window
               WindowText
               Base
               AlternateBase
               Button
               ButtonText
               Text
               Highlight
               HighlightedText
               Accent (Qt 6.6+, when available)
             Implemented `_PALETTE_MAP` dict mapping TOML keys to
             `QPalette.ColorRole`. `apply_palette(theme)` reads the
             `[palette]` section from `colors.toml`, starts from the native
             app palette, overrides only defined roles, then calls
             `app.setPalette()`. `reset_palette()` restores the native
             standard palette. Accent role gracefully skipped on Qt < 6.6.

- [x] QSS-THEME - Apply optional stylesheet
      Completed: 2026-07-13
      Lib: `QApplication`
      Files: `source/theme.py`
      Notes: If `style.qss` exists, load it after the palette has been applied.
             Encourage theme authors to reference palette colors using
             `palette(...)` rather than embedding literal colors wherever
             possible. QSS should primarily define widget appearance (borders,
             radius, spacing, control styling) rather than replace the palette.
             `apply_qss(theme, base_qss)` concatenates base QSS + theme QSS
             and calls `app.setStyleSheet()`. Theme rules appended last so
             they take precedence. `reset_qss(base_qss)` strips theme QSS
             back to base only.

- [x] SYSTEM-THEME - Native operating system theme
      Completed: 2026-07-13
      Files: `source/theme.py`
      Notes: Provide a built-in "System" theme that performs no overrides.
             Selecting this theme restores the application's fully native
             appearance by clearing any loaded palette overrides and stylesheet.
             `apply_theme("System")` calls `reset_palette()` + `reset_qss()`.
             Unknown theme names also fall back to System behaviour.

- [x] THEME-PIPELINE - Standardize theme loading order
      Completed: 2026-07-13
      Files: `source/theme.py`
      Notes: Theme application must always follow this sequence:

               Native OS Theme
                        ↓
               QApplication.palette()
                        ↓               
               Apply colors.toml (optional)
                        ↓
               app.setPalette(...)
                        ↓
               Apply style.qss (optional)
                        ↓
                   Finished

             This guarantees that every theme builds upon the native platform
             palette instead of replacing it entirely, preserving platform-
             specific colors, disabled states, accessibility improvements and
             future Qt enhancements wherever the theme does not explicitly
             override them.
             Implemented `apply_theme(name, base_qss)` — single entry point
             that orchestrates the full sequence. System/unknown names call
             `reset_palette()` + `reset_qss()`. Other themes call
             `apply_palette()` then `apply_qss()`.
             
---

## SECTION 4 - OS-SPECIFIC INTEGRATIONS

Implement last. Each is self-contained and platform-gated.

---

### macOS

- [ ] MACOS-DOCK-PROGRESS - Dock icon progress during operations
      Lib: `pyobjc-framework-Cocoa`
      Files: new file `source/integrations/macos_dock.py`, `source/window.py`
      Notes: `NSApplication.sharedApplication().dockTile().setBadgeLabel_(str(n))`
             to show progress count on dock icon during backup/sort.
             Clear badge on completion.
             Gate behind `sys.platform == "darwin"` check.

---

### Windows

- [ ] WINDOWS-JUMPLIST - Taskbar jump list
      Lib: `pywin32` (`win32com`)
      Files: new file `source/integrations/windows_shell.py`, `source/window.py`
      Notes: Add jump list entries: "Sort Mods", "Open Mods Folder", "Backup Now".
             Update recent items list with last-used profile names.
             Call at app startup and after each sort.
             Gate behind `sys.platform == "win32"` check.

- [ ] WINDOWS-TASKBAR-PROGRESS - Progress bar in taskbar button
      Lib: `pywin32` (`win32com` / `ITaskbarList3`)
      Files: `source/integrations/windows_shell.py`
      Notes: Show green fill progress on taskbar button during sort and backup.
             Use `ITaskbarList3.SetProgressValue(hwnd, completed, total)`.
             Set to indeterminate (`TBPF_INDETERMINATE`) for operations with
             unknown total. Clear on completion.
             Get HWND from `self.winId()` on the main window.
             Gate behind `sys.platform == "win32"` check.
      Blocked by: WINDOWS-JUMPLIST (shares file)

---

## SECTION 5 - PACKAGING UPDATES

Required once new libraries are added.

---

- [ ] REQUIREMENTS-SYNC - Update requirements.txt and pyproject.toml
      Files: `requirements.txt`, `pyproject.toml`
      Notes: Add all new runtime deps from sections above as they land.
             Split into runtime and dev deps:
               `[project.optional-dependencies]`
               `dev = ["pyinstaller", "ruff"]`
             Platform-conditional deps in pyproject.toml:
               `pywin32` → windows only
               `pyobjc-*` → macOS only
               `jeepney` → linux only

- [ ] FLATPAK-MANIFEST-SYNC - Vendor new deps in Flatpak manifest
      Files: `packaging/flatpak/io.github.PetricaT.IsaacMM.yml`
      Notes: Run `flatpak-pip-generator` for each new pure-Python dep added.
             For deps with C extensions (`blake3`, `rapidfuzz`): check if wheels
             are available for the KDE runtime Python version, or build from sdist.
             Update `python-deps` module sources block with new SHA256 entries.
      Blocked by: REQUIREMENTS-SYNC

- [ ] PYINSTALLER-HOOKS - Ensure new libs bundle correctly
      Lib: `pyinstaller-hooks-contrib`
      Files: `packaging/appimage/IsaacMM-Linux.spec`,
             `packaging/windows/IsaacMM-Windows.spec`,
             `packaging/macos/IsaacMM-MacOS.spec`
      Notes: Add `pyinstaller-hooks-contrib` to dev deps.
             Add hidden imports for: `blake3`, `rapidfuzz`, `httpx`, `tenacity`,
             `loguru`, `watchdog`, `notify_py`, `pystray`, `platformdirs`.
             Test each platform build after adding new deps.
      Blocked by: REQUIREMENTS-SYNC

- [x] APPIMAGE-UPDATER - Delta self-update for AppImage via AppImageUpdate
      Completed: 2026-07-13
      Tool: `AppImageUpdate` / `appimageupdatetool` / `zsync2`
      Files: `packaging/appimage/build.sh`,
             `packaging/appimage/IsaacMM-Linux.spec`,
             `.github/workflows/build-appimage.yml`,
             `source/updater.py` (AppImage branch)
      Notes: AppImageUpdate is purpose-built infrastructure for this — use it
             instead of rolling a custom downloader for the AppImage format.
             How it works: zsync delta updates download only changed bytes, not
             the full binary. A `.zsync` file is hosted alongside the AppImage
             and the update URL is embedded into the AppImage at build time.
             Setup required:
               1. In `build.sh`, pass UpdateInformation to appimagetool:
                  `export UPD_INFO="gh-releases-zsync|PetricaT|IsaacMM|latest|IsaacMM-*x86_64.AppImage.zsync"`
                  `APPIMAGE_EXTRACT_AND_RUN=1 appimagetool --updateinformation "$UPD_INFO" ...`
               2. CI must generate the `.zsync` file after building the AppImage:
                  `zsyncmake IsaacMM-x86_64.AppImage`
                  Upload both `IsaacMM-x86_64.AppImage` and
                  `IsaacMM-x86_64.AppImage.zsync` as release assets.
               3. Bundle AppImageUpdate inside the AppImage by adding it to the
                  AppDir during build so it is available on `$PATH` inside the
                  sandbox.
             In-app trigger (from `source/updater.py`, AppImage branch):
               `appimage_path = os.environ.get("APPIMAGE")`
               `subprocess.Popen(["AppImageUpdate", appimage_path])`
             AppImageUpdate shows its own progress UI — no custom download UI
             needed for this path. After update completes, prompt user to relaunch.
             The old AppImage is backed up as `IsaacMM.AppImage.zs-old` automatically.
      Blocked by: nothing (UPDATE-CHECKER complete)

- [ ] TUFUP-AUTOUPDATER - In-place auto-update for Windows and macOS
      Lib: `tufup`
      Files: `source/updater.py` (Windows/macOS branches),
             new file `packaging/tufup/repo_setup.py` (one-time repo init),
             `requirements.txt`, `pyproject.toml`
      Notes: `tufup` is a cross-platform PyInstaller auto-updater built on
             Python-TUF (The Update Framework). Handles the running-exe
             replacement problem on Windows correctly by starting the install
             script in a new process after which the current process exits.
             On macOS: replaces the .app bundle in-place.
             How it works:
               - A `tufup` repo (metadata + targets) is published alongside
                 GitHub releases. `packaging/tufup/repo_setup.py` initialises
                 the repo structure once. Each CI release run adds the new
                 artifact as a target and rotates metadata.
               - Client calls `tufup.client.Client.check_for_updates()` which
                 returns update info if available.
               - `client.download_and_apply_update()` downloads the delta,
                 verifies signatures, and triggers the platform install script.
             For GitHub-hosted apps, `tufup` can point its repository at a
             GitHub release URL — no separate server needed.
             Do NOT use for Linux AppImage (use APPIMAGE-UPDATER instead).
             Do NOT use for Flatpak (flatpak update handles it).
             Do NOT use for Linux native binary (see AUTO-UPDATER note in
             LINUX-INSTALLER below).
      Blocked by: nothing (UPDATE-CHECKER complete)

---

## COMPLETION SUMMARY

> Auto-update this section when items are checked off.

| Section | Total | Complete | In Progress | Blocked |
|---|---|---|---|---|---|---|---|---|
| 1 - Drop-in simplifications | 5 | 5 | 0 | 0 |
| 1b - Bug fixes (Windows) | 4 | 4 | 0 | 0 |
| 2 - Architecture & state | 3 | 3 | 0 | 0 |
| 3 - UX features | 8 | 4 | 0 | 0 |
| 3b - Native UI integration | 8 | 6 | 0 | 0 |
| 3c - Theme engine | 6 | 6 | 0 | 0 |
| 4 - OS integrations | 5 | 0 | 0 | 0 |
| 5 - Packaging | 9 | 1 | 0 | 0 |
| **Total** | **40** | **24** | **0** | **0** |

---

## NOTES FOR AI AGENTS

- Always re-read this file at the start of a session before making changes
- When starting an item: change `[ ]` to `[~]` and add `Started: YYYY-MM-DD`
- When completing an item: change `[~]` to `[x]` and add `Completed: YYYY-MM-DD`
- When blocked: change to `[!]` and add `Blocked by: reason`
- Update the COMPLETION SUMMARY table counts after any status change
- Never remove completed items - the history is useful
- If an item reveals unexpected complexity or sub-tasks, add them as indented
  sub-bullets under the parent item using the same status prefix convention
- Implementation order within a section is flexible unless a `Blocked by:` exists
- All platform-specific code must be gated: `if sys.platform == "linux":` etc.
  Never import platform-specific libs at module level - import inside the gate

---

## PLANNING — UPDATE-CHECKER REFINEMENT

Changes requested 2026-07-07 for the update-checking feature. **Not yet implemented.**

- [x] **BACKGROUND-CHECK-SILENT** — On startup, check for updates silently (no popup).
      Completed: 2026-07-13
      `_check_for_updates_silent` already exists (QTimer 5s) but currently opens
      the `UpdateDialog` popup when a new version is found. Change it so that
      the popup is **only** shown for interactive/forced checks. For background
      checks, store the result and let the Settings UI reflect it.

- [x] **SETTINGS-UPDATE-UI** — When a background check finds a newer version,
      Completed: 2026-07-13
      replace the static version label in the "Updates" group with:
      `Current version: {VERSION} -> {NEW_VERSION}`
      Change the button text from "Check for Updates" to **"Update now"**.
      Clicking "Update now" launches the same update flow (asset download,
      progress bar, AppImage restart) that `UpdateDialog` does.

- [x] **CHANGELOGS-BUTTON** — Add a permanent "Changelogs" button next to
      Completed: 2026-07-13
      "Check for Updates" / "Update now" in the Settings Updates group.
      Opens `https://github.com/PetricaT/IsaacMM/releases` in the browser
      via `QDesktopServices.openUrl`.

**Implementation sketch** (do not act on yet):
1. `window.py`: `_check_for_updates_silent` -> do NOT open dialog on result.
   Instead store `self._pending_update = release` and emit a signal or flag.
2. `dialogs.py` Settings "Updates" group: expose an `update_available` signal
   or let `window.py` push the release info. When set, swap label + button.
3. `dialogs.py`: add QPushButton "Changelogs" permanently visible.
4. Button logic: "Check for Updates" when idle / "Update now" when pending.
   Both work via `window._check_for_updates_interactive` (existing) and
   a new `window._run_update_download(release)` that bypasses the dialog
   and directly shows the progress / restart flow.
