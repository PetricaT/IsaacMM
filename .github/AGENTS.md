# IsaacMM Agent Guide

## Process

1. Read `PROGRESS.md` before making changes. Identify the target item. Check `Blocked by:` — do not implement if blocker is incomplete. Read all `Files:` listed. After completing, update the item status and COMPLETION SUMMARY table.
2. State plan, verify after each step. No speculative features.
3. Remove imports/variables YOUR changes made unused. Don't touch pre-existing dead code unless asked.
4. Do not touch `packaging/`, `masterlist.yaml`, `game_versions.json`. `assets/` is read-only.

## Project structure

- `main.py` — entrypoint. Creates `QApplication`, calls `config.load()`, shows `DragApp`.
- `source/` — core logic and UI wiring.
- `source/components/` — all UI widget code (separated from logic).
- `source/window.py:DragApp` — main window (QWidget), owns all panels.
- `source/worker.py:ManagedWorker` — **must use this for ALL background tasks.** Wraps QThread with finished/error signals. Usage: `self._worker = ManagedWorker(parent=self); self._worker.start(fn, arg, name="Name")`. Workers must be waited in `closeEvent`.
- `source/config.py` — dataclass + module-level `__getattr__`. Access: `config.field_name`.
- `source/database.py` — SQLite (WAL mode). Schema migrations via `MIGRATIONS` dict. `PRAGMA user_version` tracks version.
- `source/theme_helpers.py` — `palette_color(role, widget, alpha)` and `text_color_for_bg(bg_qcolor)` for palette-derived colors.

## Developer commands

```sh
uv run main.py              # launch app (requires .venv with PySide6 etc.)
source .venv/bin/activate   # activate uv venv
```

## Conventions

- Platform-specific code gated with `if sys.platform == "win32":` etc. Never import platform libs at module level.
- Use `config.field_name` for all settings. Config defaults in the dataclass and in `config.load()`.
- Logging via `logger.log(level, msg)` (loguru wrapper). Colored console output via `log_colored(segments)`.

## Testing

No test framework is set up. Verification steps:
1. `python -c "import ast; ast.parse(open('file.py').read())"` — syntax check
2. `uv run main.py` — launch, verify no crash within 5s, then kill it

## PROGRESS.md

The file at `.github/PROGRESS.md` is the single source of truth for planned/completed work. It uses status markers: `[ ]` not started, `[~]` in progress, `[x]` complete, `[!]` blocked. Always update the COMPLETION SUMMARY table when changing item status.

## Key backend patterns

- **Conflict detection**: `source/conflict_index.py` — blake2b fingerprinting + quick tokens. `get_cached_files(mod_folder)` returns `dict[rel_path, list[mod_folder]]`.
- **Folder watching**: `source/folder_watcher.py:ModFolderWatcher` wraps `watchdog.Observer`. Buffers events, flushes via QTimer (500ms).
- **Undo/redo**: In-memory `_undo_stack`/`_redo_stack` in `ModListPanel` (max 50). Ctrl+Z/Y in eventFilter.
- **Sorting**: `source/sorter.py` — auto-sort algorithm. Runs in `ManagedWorker`. Results emitted as mod list.
