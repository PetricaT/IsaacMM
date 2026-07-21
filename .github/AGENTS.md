# IsaacMM Agent Guide

## Process

1. Read `PROGRESS.md` before making changes. Identify the target item. Check `Blocked by:` — do not implement if blocker is incomplete. Read all `Files:` listed. After completing, update the item status and COMPLETION SUMMARY table.
2. State plan, verify after each step. No speculative features.
3. Remove imports/variables YOUR changes made unused. Don't touch pre-existing dead code unless asked.
4. Do not touch `packaging/`, `masterlist.yaml`, `game_versions.json`. `assets/` is read-only.

## Project structure

- `main.py` — entrypoint. Creates `QApplication`, calls `config.load()`, shows `DragApp`.
- `source/core/` — config, database, logger, worker, paths, models, notifications.
- `source/mods/` — backup, conflict_index, folder_watcher, game_versions, modlist_io, remote_cache, sorter, workshop.
- `source/theme/` — theme loader (TOML + QSS), palette helpers.
- `source/ui/dialogs/` — settings.py (SettingsPanel), delegates.py (ConflictDelegate + _colorize), separator.py.
- `source/ui/panels/` — mod_list.py, mod_info.py, conflict_tree.py, console.py, preview.py.
- `source/ui/window.py:DragApp` — main window (QWidget), owns all panels.
- `source/controller/` — SDL3 gamepad input manager + controller UI overlay.
- `source/updater/` — GitHub release self-update (AppImage/Windows).
- `source/worker.py:ManagedWorker` — **must use this for ALL background tasks.** Wraps QThread with finished/error signals. Usage: `self._worker = ManagedWorker(parent=self); self._worker.start(fn, arg, name="Name")`. Workers must be waited in `closeEvent`.
- `source/core/config.py` — `_Config` dataclass + module-level `__getattr__`. Access: `config.field_name`.
- `source/core/database.py` — SQLite (WAL mode). Schema migrations via `MIGRATIONS` dict. `PRAGMA user_version` tracks version.
- `source/theme/theme_helpers.py` — `palette_color(role, widget, alpha)` and `text_color_for_bg(bg_qcolor)` for palette-derived colors.

## Developer commands

```sh
uv run main.py              # launch app (requires .venv with PySide6 etc.)
source .venv/bin/activate   # activate uv venv
```

## Conventions

- Platform-specific code gated with `if sys.platform == "win32":` etc. Never import platform libs at module level.
- Use `config.field_name` for all settings. Config defaults in the dataclass and in `config.load()`.
- Logging via `logger.log(level, msg)` (loguru wrapper). Colored console output via `log_colored(segments)` where segments are `(text, Optional[str | QTextCharFormat])`.
- Console dedup via `_dedup_key()` which strips digits for pattern matching.
- Backup automatically ignores: `.git`, `__pycache__`, `.DS_Store`, `Thumbs.db`, `MERGED`.
- Use `isinstance(instance, QApplication)` guard to satisfy type checkers when calling `.palette()` on `QApplication.instance()`.
- Use `QHeaderView.ResizeMode.Stretch` / `.Interactive` instead of legacy `QHeaderView.Stretch` / `.Interactive`.
- Use `QEvent.Type.MouseMove` / `.Leave` instead of `QEvent.MouseMove` / `.Leave`.
- Use `QAbstractItemView.SelectionMode.NoSelection` instead of legacy `.NoSelection`.
- Use `QListWidget.Flow.LeftToRight` instead of legacy `.LeftToRight`.
- Use `QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator` instead of legacy `.ShowIndicator`.
- `QImage.save()` expects `bytes` format string: use `b"PNG"` not `"PNG"`.
- `QByteArray` → `bytes` conversion: use `.data()` for type safety.

## Testing

No test framework is set up. Verification steps:
1. `python -c "import ast; ast.parse(open('file.py').read())"` — syntax check
2. `pyright source/<file>.py` — type check (requires PySide6 stubs)
3. `uv run main.py` — launch, verify no crash within 5s, then kill it

## PROGRESS.md

The file at `.github/PROGRESS.md` is the single source of truth for planned/completed work. It uses status markers: `[ ]` not started, `[~]` in progress, `[x]` complete, `[!]` blocked. Always update the COMPLETION SUMMARY table when changing item status.

## Key backend patterns

- **Conflict detection**: `source/mods/conflict_index.py` — blake2b fingerprinting + quick tokens. `get_cached_files(mod_folder)` returns `dict[rel_path, list[mod_folder]]`.
- **Folder watching**: `source/mods/folder_watcher.py:ModFolderWatcher` wraps `watchdog.Observer`. Buffers events, flushes via QTimer (500ms).
- **Undo/redo**: In-memory `_undo_stack`/`_redo_stack` in `ModListPanel` (max 50). Ctrl+Z/Y in eventFilter.
- **Sorting**: `source/mods/sorter.py` — auto-sort algorithm. Runs in `ManagedWorker`. Results emitted as mod list.
- **Backup**: `source/mods/backup.py` — `backup_all()` compares versions via `packaging.Version`, returns `(mod_name, old_ver, new_ver, magnitude)` results. Version text colorized via `_colorize()` in delegates.py.
- **Theme engine**: `source/theme/theme.py` — discovers TOML theme files, builds `QPalette` + QSS, supports System/Native/File themes.
- **Controller**: `source/controller/controller.py` — SDL3-based gamepad support, emits `button_down(int)` signal. `Button` IntEnum maps SDL constants.
