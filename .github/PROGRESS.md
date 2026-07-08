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

## SECTION 2 - ARCHITECTURE & STATE

These touch the data layer and unlock multiple features downstream.

---

- [ ] SQLITE-STATE - Consolidate state files into SQLite
      Lib: `sqlite3` (stdlib)
      Files: `source/config.py`, `source/sorter.py`, `source/components/workshop.py`,
             new file `source/database.py`
      Notes: Create `source/database.py` as the single DB access layer.
             Migrate the following out of config.toml and yaml files:
               - `workshop_timestamps` → `workshop_items` table
               - `dead_workshop_ids` → `workshop_items.status` column
               - `last_order.yaml` → `load_order_history` table (enables undo/redo)
               - Workshop icon/details cache → `workshop_items` table
             Keep `config.toml` for user-editable settings only (paths, theme,
             feature flags). DB file lives at `paths.user_data_dir / isaacmm.db`.
             Schema:
               workshop_items(id INTEGER PK, title, preview_url, description,
                              last_fetched, status TEXT)
               load_order_history(id INTEGER PK, timestamp, order_json TEXT,
                                  label TEXT)
             Migration: on first run with new version, import existing data from
             config.toml and yaml files into DB, then remove the old keys.
      Blocked by: PLATFORMDIRS (needs stable paths)

- [ ] SQLITE-MIGRATIONS - DB schema versioning and migration mechanism
      Lib: `sqlite3` (stdlib)
      Files: `source/database.py`
      Notes: The DB must be versioned from day one so schema changes never break
             existing installs. On every app launch, compare stored `user_version`
             (SQLite's built-in pragma) against the current code version and run
             any pending migration functions in order.
             Pattern:
               MIGRATIONS = {
                   1: _migrate_v1,   # initial schema
                   2: _migrate_v2,   # e.g. added profiles table
               }
               current = db.execute("PRAGMA user_version").fetchone()[0]
               for v, fn in sorted(MIGRATIONS.items()):
                   if v > current:
                       fn(db)
                       db.execute(f"PRAGMA user_version = {v}")
             CRITICAL — column and table names must be stable and future-proof
             from the start. Use generic descriptive names, never names tied to
             current UI labels (e.g. `item_id` not `workshop_id`, `sort_index`
             not `sort_position`) so future data model changes do not require
             column renames. SQLite does not support ALTER TABLE RENAME COLUMN
             cleanly before 3.25 — add new columns and deprecate old ones instead,
             or recreate the table in the migration.
             Each migration function must be idempotent — safe to run twice.
             Wrap each migration in a transaction so a failed migration leaves
             the DB unchanged and the app falls back gracefully.
      Blocked by: SQLITE-STATE

- [ ] CONFLICT-INDEX - File-level conflict detection
      Lib: `blake3`
      Files: new file `source/conflict_index.py`, `source/components/modlist.py`,
             `source/database.py`, `requirements.txt`, `pyproject.toml`
      Notes: Build a `dict[relative_path, list[mod_folder]]` by walking each
             enabled mod's folder. Any entry with >1 mod is a conflict. Winner is
             mods[0] (highest in load order), losers are everything after.
             Use blake3 to fingerprint each mod folder (hash of all relative file
             paths + mtimes concatenated). Store fingerprint in DB alongside the
             index. On next launch, only re-index mods whose fingerprint changed.
             Surface conflicts in the existing conflict tree panel - add a new
             "File Conflicts" column or tab showing which specific files clash.
             No hashing needed for detection itself - only for cache invalidation.
      Blocked by: SQLITE-STATE

---

## SECTION 3 - UX FEATURES

New user-facing functionality. Implement after Section 1 is stable.

---

- [ ] WATCHDOG - Live mod folder sync
      Lib: `watchdog`
      Files: new file `source/folder_watcher.py`, `source/components/modlist.py`,
             `source/window.py`, `requirements.txt`, `pyproject.toml`
      Notes: Watch `config.mods_path` for `FileCreatedEvent`, `FileDeletedEvent`,
             `FileModifiedEvent`. On event, debounce 500ms then trigger a mod list
             rescan. Run the watchdog observer in a background thread.
             Stop the observer in `window.closeEvent`.
             Update CONFLICT-INDEX incrementally on change events rather than full
             rebuild - only re-index the changed mod folder.
             Add a status indicator in the UI (small icon) showing watcher active/inactive.
      Blocked by: nothing (can land before CONFLICT-INDEX)

- [ ] LOAD-ORDER-HISTORY - Undo/redo for sort operations
      Lib: `sqlite3` (stdlib, already in SQLITE-STATE)
      Files: `source/database.py`, `source/components/modlist.py`, `source/window.py`
      Notes: On every sort or manual reorder, write current order to
             `load_order_history` table with timestamp and optional label.
             Keep last 50 entries. Expose Ctrl+Z / Ctrl+Y in the mod list to
             step through history. Add a "History" button or menu that shows
             a list of past orders with timestamps and lets user jump to any.
      Blocked by: SQLITE-STATE

- [ ] NOTIFICATIONS - Desktop notifications for async operations
      Lib: `notify-py`
      Files: new file `source/notifications.py`, `source/window.py`,
             `source/backup.py`, `requirements.txt`, `pyproject.toml`
      Notes: Send notifications for: update available (new version found).
             Make notification opt-in via a settings toggle.
             On Linux uses libnotify, on macOS osascript, on Windows PowerShell toast.
             For richer platform-native notifications see OS-SPECIFIC section.

- [ ] UPDATE-CHECKER - Check for new app versions on GitHub
      Lib: `httpx` (already in HTTPX), `packaging`
      Files: new file `source/updater.py`, `source/window.py`,
             `source/components/dialogs.py`
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
      Blocked by: HTTPX, SQLITE-MIGRATIONS

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

## SECTION 4 - OS-SPECIFIC INTEGRATIONS

Implement last. Each is self-contained and platform-gated.

---

### macOS

- [ ] MACOS-NOTIFICATIONS - Native UNUserNotificationCenter notifications
      Lib: `pyobjc-framework-UserNotifications`
      Files: `source/notifications.py` (extend existing), `requirements.txt`
      Notes: Replace `notify-py` macOS backend with direct
             `UNUserNotificationCenter` calls for action button support.
             Request notification permission at first launch.
             Add action buttons to sort-complete notification: "View Log".
             Gate behind `sys.platform == "darwin"` check.
             Falls back to `notify-py` if pyobjc not available.
      Blocked by: NOTIFICATIONS

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

- [ ] WINDOWS-TOAST - Native Win10/11 toast notifications
      Lib: `winrt-runtime`, `winrt-Windows.UI.Notifications`
      Files: `source/notifications.py` (extend existing), `requirements.txt`
      Notes: Replace `notify-py` Windows backend with WinRT toast API for proper
             Win10/11 notifications with action buttons and app icon.
             Action button on sort-complete: "View Log".
             Falls back to `notify-py` if winrt not available (older Windows).
             Gate behind `sys.platform == "win32"` check.
      Blocked by: NOTIFICATIONS

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

- [ ] LINUX-NATIVE-BINARY - Ship a plain native Linux ELF binary
      Files: new file `packaging/native/build.sh`,
             new file `packaging/native/IsaacMM-Linux-Native.spec`
      Notes: PyInstaller `--onefile` already produces a self-extracting ELF.
             The AppImage build does this internally — skip the appimagetool wrap.
             Output named `IsaacMM-linux-x86_64` for clarity in release assets.
             No .desktop or icon integration — user's responsibility with this format.
             Intended for users placing the binary in `~/.local/bin/` manually.
             The LD_LIBRARY_PATH xdg-open fix in `file_utils.py` still applies —
             PyInstaller onefile sets LD_LIBRARY_PATH on extraction regardless of
             whether wrapped in an AppImage.
             CI: add as a second artifact in `build-appimage.yml` or a separate
             `build-native.yml`. Both attached to GitHub release.
      Blocked by: nothing

- [ ] APPIMAGE-UPDATER - Delta self-update for AppImage via AppImageUpdate
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
      Blocked by: UPDATE-CHECKER (for the in-app trigger), LINUX-NATIVE-BINARY

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
      Blocked by: UPDATE-CHECKER

- [ ] LINUX-INSTALLER - Optional GUI installer for Linux (MAYBE)
      Files: new file `packaging/linux-installer/build.sh`,
             new file `packaging/linux-installer/installer.py`,
             new file `packaging/linux-installer/IsaacMM-Installer.spec`,
             new file `.github/workflows/build-installer-linux.yml`
      Notes: STATUS: MAYBE — AppImage and Flatpak remain primary Linux artifacts.
             A Linux installer provides: user-chosen install path via QWizard
             (default `~/.local/share/IsaacMM/` or `/opt/IsaacMM/` for system),
             automatic `.desktop` file at
             `~/.local/share/applications/io.github.PetricaT.IsaacMM.desktop`,
             icon at `~/.local/share/icons/hicolor/256x256/apps/`,
             optional `~/.local/bin/IsaacMM` symlink, and an uninstall script.
             Implementation: a separate small PySide6 QWizard bundled as its own
             PyInstaller onefile ELF. Pages: Welcome → Choose Path → Installing
             → Finish. Produces `IsaacMM-Installer-linux-x86_64`.
             After writing .desktop file run:
               `update-desktop-database ~/.local/share/applications`
             After installing icon run:
               `xdg-icon-resource install --size 256 icon.png io.github.PetricaT.IsaacMM`
             Self-update for installed native binary: download new installer ELF
             to temp, run with `--update` flag (skips wizard, overwrites binary,
             relaunches). Use `packaging` lib for version comparison. Show a
             non-intrusive banner in UI when update is available rather than a
             blocking dialog. This path is separate from APPIMAGE-UPDATER —
             it applies only to the binary installed by this installer.
             Uninstaller: `uninstall.sh` removes binary, .desktop, icon, symlink.
             Does NOT remove user data — prompt the user separately.
             Gate behind actual user demand before investing time.
      Blocked by: LINUX-NATIVE-BINARY

- [ ] WINDOWS-INSTALLER - Optional NSIS installer for Windows (MAYBE)
      Files: new file `packaging/windows/installer.nsi`,
             new file `.github/workflows/build-installer-windows.yml`
      Notes: STATUS: MAYBE — portable .exe remains the primary Windows artifact.
             NSIS recommended over WiX — simpler, better PyInstaller community
             support, produces `IsaacMM-Setup-x.y.z.exe`.
             Provides: Start Menu shortcut, optional Desktop shortcut,
             Add/Remove Programs entry, uninstaller.
             Self-update: TUFUP-AUTOUPDATER handles Windows auto-update already
             for both portable and installed variants — no separate update
             mechanism needed here. The NSIS installer just handles first install
             and uninstall cleanly.
             Both portable `IsaacMM.exe` and `IsaacMM-Setup-x.y.z.exe` attached
             to the GitHub release. Do not remove the portable build.
             Gate behind actual user demand before investing time.
      Blocked by: nothing (but do not start until MAYBE becomes YES)

---

## COMPLETION SUMMARY

> Auto-update this section when items are checked off.

| Section | Total | Complete | In Progress | Blocked |
|---|---|---|---|---|---|---|
| 1 - Drop-in simplifications | 5 | 5 | 0 | 0 |
| 1b - Bug fixes (Windows) | 4 | 4 | 0 | 0 |
| 2 - Architecture & state | 3 | 0 | 0 | 0 |
| 3 - UX features | 8 | 0 | 0 | 0 |
| 4 - OS integrations | 5 | 0 | 0 | 0 |
| 5 - Packaging | 9 | 0 | 0 | 0 |
| **Total** | **34** | **9** | **0** | **0** |

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

- [ ] **BACKGROUND-CHECK-SILENT** — On startup, check for updates silently (no popup).
      `_check_for_updates_silent` already exists (QTimer 5s) but currently opens
      the `UpdateDialog` popup when a new version is found. Change it so that
      the popup is **only** shown for interactive/forced checks. For background
      checks, store the result and let the Settings UI reflect it.

- [ ] **SETTINGS-UPDATE-UI** — When a background check finds a newer version,
      replace the static version label in the "Updates" group with:
      `Current version: {VERSION} -> {NEW_VERSION}`
      Change the button text from "Check for Updates" to **"Update now"**.
      Clicking "Update now" launches the same update flow (asset download,
      progress bar, AppImage restart) that `UpdateDialog` does.

- [ ] **CHANGELOGS-BUTTON** — Add a permanent "Changelogs" button next to
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
