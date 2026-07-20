# Code Map

## Source Layout

```
main.py                        -- Application entry point
source/
  config.py                    -- Config dataclass + TOML I/O
  database.py                  -- SQLite persistence + migrations
  logger.py                    -- loguru wrapper
  models.py                    -- FlatDropModel (drag-drop model)
  sorter.py                    -- Masterlist auto-sort + topological sort
  paths.py                     -- Path resolution, symlinks, Isaac folder detection
  theme.py                     -- Filesystem theme loader (palette + QSS)
  theme_helpers.py             -- palette_color(), text_color_for_bg()
  conflict_index.py            -- blake2b fingerprinting for conflict cache
  folder_watcher.py            -- watchdog-based live mod folder sync
  controller.py                -- SDL3 gamepad input manager
  worker.py                    -- QThread worker infrastructure
  updater.py                   -- Self-update via GitHub releases
  remote_cache.py              -- Generic fetch/cache/bundled chain
  backup.py                    -- Mod backup/restore
  modlist_io.py                -- CSV import/export
  notifications.py             -- Desktop notification wrapper (notify-py)
  game_versions.py             -- Game update date tracking
  widgets.py                   -- ModInfoPanel, ConflictTreeWidget
  window.py                    -- Main DragApp window

source/components/
  modlist.py                   -- ModListPanel — main list + conflict UI
  console.py                   -- ConsoleWidget — log output
  dialogs.py                   -- SettingsPanel, ConflictDelegate, SeparatorDialog
  preview.py                   -- PreviewWidget — image/anm2 tooltip popup
  controller_ui.py             -- ControllerRouter, FocusOverlay, AxisScroller
  workshop.py                  -- WorkshopQueue, rate limiter, Steam API fetches
  file_utils.py                -- open_path / open_url
  text_utils.py                -- BBCode to HTML converter
```

## Key Classes & Locations

### `source/window.py` — DragApp (main window)
| Method | Line | Purpose |
|---|---|---|
| `__init__` | 66 | Init workers, geometry, UI, controller |
| `initUi()` | 219 | Build splitter layout |
| `_apply_theme_data()` | 146 | Apply palette + QSS via safe repaint |
| `closeEvent()` | 181 | Save state, cleanup threads, stop watcher |
| `changeEvent()` | 489 | Re-apply theme on PaletteChange/StyleChange |

### `source/components/modlist.py` — ModListPanel
| Signal/Method | Line | Purpose |
|---|---|---|
| `mod_selected` | 117 | Emitted on row click |
| `log_message` | 118 | Console output |
| `mods_loaded` | 120 | Scan complete |
| `load_mod_list()` | 284 | Start background scan |
| `_on_mods_scanned()` | 307 | Populate model from scan result |
| `_update_conflict_indicators()` | 493 | **Core:** 2-pass win/loss/overwrite scan |
| `_on_mod_selected()` | 674 | Emit mod_selected with conflict data |
| `_refresh_selection_conflicts()` | 737 | Per-selection conflict data |
| `_scan_mod_files()` | 782 | Get conflict files (cached) |
| `_on_mod_folder_changed()` | 799 | Watchdog → invalidate + rescan |
| `apply_mod_order()` | 874 | Write sorted names to metadata.xml |
| `auto_sort_mods()` | 1011 | Background auto-sort |
| `_on_sort_done()` | 1050 | Rebuild model from sorted list |
| `restore_last_order()` | 959 | Background restore |
| `_on_item_changed()` | 807 | Checkbox toggle → conflict timer |
| `_undo()` / `_redo()` | 477/485 | Undo/redo drag-drop |

### `source/widgets.py` — ModInfoPanel & ConflictTreeWidget
| Method | Line | Purpose |
|---|---|---|
| `ConflictTreeWidget._find_imagediff()` | 110 | Locate imagediff binary |
| `ConflictTreeWidget._on_context_menu()` | 125 | Right-click → merge with imagediff |
| `ModInfoPanel.show_mod_info()` | 350 | Load icon, desc, conflicts, files |
| `ModInfoPanel._on_merge_requested()` | 843 | Collect images, launch imagediff |

### `source/components/console.py` — ConsoleWidget
| Method | Line | Purpose |
|---|---|---|
| `_write_console()` | 157 | Core: format tag + timestamp + message, dedup |
| `log_colored()` | 198 | Multi-color segment line |
| `_update_rate_bar()` | 217 | Workshop rate/cooldown labels |
| `_mid_tone()` | 131 | Blend Text:Base at 40:60 for timestamp |
| `_insert_tag()` | 147 | Bold colored level tag |
| `_insert_timestamp()` | 153 | Mid-tone timestamp |
| `_dedup_key()` | 155 | Strip digits for pattern-based dedup |

### `source/components/dialogs.py` — SettingsPanel & ConflictDelegate
| Method | Line | Purpose |
|---|---|---|
| `ConflictDelegate.paint()` | 113 | Draw +/- conflict indicators |
| `SettingsPanel._save_settings()` | 918 | Write all widgets to config |
| `SettingsPanel._apply_theme()` | 771 | Load theme, apply palette+QSS |

### `source/folder_watcher.py` — ModFolderWatcher
| Method | Line | Purpose |
|---|---|---|
| `start()` | 58 | Begin recursive watch |
| `stop()` | 72 | Stop observer, clear buffer |
| `clear_pending()` | 83 | Discard buffered events |

### `source/sorter.py`
| Function | Line | Purpose |
|---|---|---|
| `auto_sort()` | 210 | Group priority + topological mod sort |
| `should_preserve_name()` | 200 | Check if mod name is locked |
| `save_last_order()` | 55 | Persist order to DB |
| `load_last_order()` | 59 | Load last order from DB |

### `source/config.py` — _Config
| Method | Line | Purpose |
|---|---|---|
| `load()` | 189 | Read config.toml, init DB |
| `save()` | 284 | Debounced config write |
| `get_settings()` | 185 | QSettings for UI state |

### `source/conflict_index.py`
| Function | Line | Purpose |
|---|---|---|
| `get_cached_files()` | 50 | Return conflict files (cached via fingerprint) |
| `invalidate()` | 75 | Clear cached fingerprint for folder |
| `_quick_token()` | 80 | Dir mtime + entry-name token |

### `source/controller.py` — ControllerManager
| Signal | Line | Purpose |
|---|---|---|
| `connected(str, int)` | 80 | Gamepad name + type |
| `disconnected()` | 81 | Disconnected |
| `activity_changed(bool)` | 82 | Active/inactive |
| `button_down(int)` | 83 | Button pressed |
| `axis_moved(int, int)` | 85 | Axis index + value |

### `source/database.py`
| Function | Line | Purpose |
|---|---|---|
| `init()` | 112 | Create tables + run migrations |
| `get_mod_fingerprint()` | 236 | Get cached fingerprint |
| `set_mod_fingerprint()` | 244 | Store fingerprint |
| `save_load_order()` | 206 | Save order, keep last 50 |
| `load_latest_order()` | 219 | Load most recent order |

## Startup Flow (main.py)
1. `config.load()` — read TOML, init DB, detect mods folder
2. `QApplication(sys.argv)` — save native style name
3. Apply theme if `active_theme != "System"` (load palette + QSS + color overrides)
4. `DragApp()` — initUi builds splitter, start watcher, masterlist refresh, controller init
5. `main_window.show()` → `application.exec()`

## Module-Level Constants
| Constant | File | Line | Value |
|---|---|---|---|
| `CONFLICT_ROLE` | `dialogs.py` | 83 | `UserRole + 1` |
| `SEPARATOR_ROLE` | `dialogs.py` | 84 | `UserRole + 2` |
| `PREV_CHECK_ROLE` | `dialogs.py` | 85 | `UserRole + 3` |
| `OVERWRITTEN_ROLE` | `dialogs.py` | 86 | `UserRole + 4` |
| `NORMALIZED_NAME_ROLE` | `dialogs.py` | 87 | `UserRole + 5` |
| `WINS_ROLE` | `dialogs.py` | 88 | `UserRole + 6` |
| `LOSSES_ROLE` | `dialogs.py` | 89 | `UserRole + 7` |
| `LEVEL_TAGS` | `console.py` | 31 | `debug/info/warning/error → ([TAG], QColor)` |
| `sorted_pattern` | `modlist.py` | 53 | `r"[0-9]{3}\s.*"` — detected sorted prefix |
| `SEPARATOR_SUFFIX` | `modlist.py` | 52 | `"_separator"` |
| `WORKSHOP_RATE_LIMIT` | `workshop.py` | 84 | 180 requests per window |

## Notes
- Console dedup uses `_dedup_key()` which strips all digits (`\d+ → #`) before comparing.
- Conflict timer is a 150ms `QTimer` debounce — all `_conflict_timer.start()` calls are deduped.
- Watchdog has a 500ms debounce timer — event types filtered to `{created, modified, deleted, moved}`.
- `hashlib.blake2b` is used for fingerprinting (stdlib, no C-extension issues).
- `app.setStyle()` only called when `config.theme != "native"` — native mode leaves platform QStyle.
- System icons via `QFileIconProvider` — always enabled, `use_system_icons` checkbox forced checked+disabled.
- `notify-py` for desktop notifications (libnotify/osascript/PowerShell toast).
- `imagediff` merge uses `--output` flag (not `--minimal`).
