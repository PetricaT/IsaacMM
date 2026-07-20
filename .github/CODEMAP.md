# Code Map

## Source Layout

```
main.py                                        -- Application entry point

source/
  controller/
    controller.py                              -- SDL3 gamepad input manager
    controller_ui.py                           -- ControllerRouter, FocusOverlay, AxisScroller

  core/
    config.py                                  -- _Config dataclass + TOML I/O + module-level __getattr__
    database.py                                -- SQLite (WAL) + migrations
    logger.py                                  -- loguru wrapper
    models.py                                  -- FlatDropModel (drag-drop model)
    notifications.py                           -- Desktop notification wrapper (notify-py)
    paths.py                                   -- Path resolution, symlinks, Isaac folder detection
    worker.py                                  -- WorkerThread + ManagedWorker (QThread wrapper)

  mods/
    backup.py                                  -- Mod backup/restore (backup_all, _read_version)
    conflict_index.py                          -- blake2b fingerprinting for conflict cache
    folder_watcher.py                          -- watchdog-based live mod folder sync
    game_versions.py                           -- Game update date tracking (RemoteCache)
    modlist_io.py                              -- CSV import/export
    remote_cache.py                            -- Generic fetch/cache/bundled chain
    sorter.py                                  -- Masterlist auto-sort + topological sort
    workshop.py                                -- WorkshopQueue, rate limiter, Steam API fetches

  theme/
    theme.py                                   -- Filesystem theme loader (Theme dataclass, palette + QSS)
    theme_helpers.py                           -- palette_color(), text_color_for_bg()

  ui/
    dialogs/
      delegates.py                             -- ConflictDelegate, _colorize(), SettingsPanelOwner protocol
      separator.py                             -- SeparatorDialog (create/edit separators)
      settings.py                              -- SettingsPanel (full settings tab UI)

    panels/
      conflict_tree.py                         -- ConflictTreeWidget (file tree + merge context menu)
      console.py                               -- ConsoleWidget (log output with dedup + colored segments)
      mod_info.py                              -- ModInfoPanel (icon, desc, conflicts, file tree, merge)
      mod_list.py                              -- ModListPanel (main list + drag-drop + conflict UI)
      preview.py                               -- PreviewWidget (image/anm2 tooltip popup)

    file_utils.py                              -- open_path / open_url
    text_utils.py                              -- BBCode to HTML converter
    window.py                                  -- DragApp (main window, owns all panels)

  updater/
    updater.py                                 -- Self-update via GitHub releases (AppImage/Windows)
```

## Key Classes & Locations

### `source/ui/window.py` — DragApp (main window, line 52)
| Method | Line | Purpose |
|---|---|---|
| `__init__` | 69 | Init workers, geometry, UI, controller |
| `_build_ui` (was `initUi`) | — | Build splitter layout |
| `_apply_theme_data()` | 146 | Apply palette + QSS via safe repaint |
| `closeEvent()` | 181 | Save state, cleanup threads, stop watcher |
| `changeEvent()` | 489+ | Re-apply theme on PaletteChange/StyleChange |
| `log()` | 473 | Delegate to console_widget.log |
| `log_colored()` | 476 | Delegate to console_widget.log_colored |

### `source/ui/panels/mod_list.py` — ModListPanel (line 131)
| Signal/Method | Line | Purpose |
|---|---|---|
| `mod_selected` | — | Emitted on row click |
| `log_message` | — | Console output |
| `mods_loaded` | — | Scan complete |
| `load_mod_list()` | — | Start background scan |
| `_on_mods_scanned()` | — | Populate model from scan result |
| `_update_conflict_indicators()` | — | **Core:** 2-pass win/loss/overwrite scan |
| `_on_mod_selected()` | — | Emit mod_selected with conflict data |
| `_refresh_selection_conflicts()` | — | Per-selection conflict data |
| `_scan_mod_files()` | — | Get conflict files (cached) |
| `_on_mod_folder_changed()` | — | Watchdog → invalidate + rescan |
| `apply_mod_order()` | — | Write sorted names to metadata.xml |
| `auto_sort_mods()` | — | Background auto-sort |
| `_on_sort_done()` | — | Rebuild model from sorted list |
| `restore_last_order()` | — | Background restore |
| `_on_item_changed()` | — | Checkbox toggle → conflict timer |
| `_undo()` / `_redo()` | — | Undo/redo drag-drop |

### `source/ui/panels/mod_info.py` — ModInfoPanel (line 106)
| Method | Line | Purpose |
|---|---|---|
| `show_mod_info()` | — | Load icon, desc, conflicts, files |
| `_on_merge_requested()` | ~805 | Collect images, launch imagediff |
| `save_column_state()` | ~795 | Save column state to bytes |

### `source/ui/panels/conflict_tree.py` — ConflictTreeWidget (line 12)
| Method | Line | Purpose |
|---|---|---|
| `_find_imagediff()` | — | Locate imagediff binary |
| `_on_context_menu()` | — | Right-click → merge with imagediff |

### `source/ui/panels/preview.py` — PreviewWidget (line 229)
| Function | Line | Purpose |
|---|---|---|
| `_resolve_spritesheet()` | 16 | Parse spritesheet metadata |
| `_load_preview_data()` | 46 | Load image/anm2 preview |
| `_parse_anm2_frames()` | 101 | Parse anm2 frame data |

### `source/ui/panels/console.py` — ConsoleWidget (line 39)
| Method | Line | Purpose |
|---|---|---|
| `_write_console()` | 157 | Core: format tag + timestamp + message, dedup |
| `log_colored()` | 198 | Multi-color/multi-format segment line |
| `_update_rate_bar()` | — | Workshop rate/cooldown labels |
| `_mid_tone()` | 131 | Blend Text:Base at 40:60 for timestamp |
| `_insert_tag()` | 147 | Bold colored level tag |
| `_insert_timestamp()` | 153 | Mid-tone timestamp |
| `_dedup_key()` | 155 | Strip digits for pattern-based dedup |

### `source/ui/dialogs/settings.py` — SettingsPanel (line 55)
| Method | Line | Purpose |
|---|---|---|
| `_save_settings()` | 760 | Write all widgets to config |
| `_apply_theme()` | — | Load theme, apply palette+QSS |

### `source/ui/dialogs/delegates.py`
| Class/Function | Line | Purpose |
|---|---|---|
| `_colorize()` | 13 | Split version text into colored segments (win/lose) |
| `SettingsPanelOwner` (Protocol) | 30 | Interface for DragApp owner reference |
| `ConflictDelegate` | 52 | QStyledItemDelegate drawing +/- conflict indicators |
| `CONFLICT_ROLE` | 40 | `UserRole + 1` |
| `SEPARATOR_ROLE` | 41 | `UserRole + 2` |
| `PREV_CHECK_ROLE` | 42 | `UserRole + 3` |
| `OVERWRITTEN_ROLE` | 43 | `UserRole + 4` |
| `NORMALIZED_NAME_ROLE` | 44 | `UserRole + 5` |
| `WINS_ROLE` | 45 | `UserRole + 6` |
| `LOSSES_ROLE` | 46 | `UserRole + 7` |
| `EMPTY_ROLE` | 47 | `UserRole + 8` |

### `source/mods/backup.py`
| Function | Line | Purpose |
|---|---|---|
| `_read_version()` | 15 | Read version from metadata.xml |
| `_versions_differ()` | 30 | Compare versions with packaging.Version |
| `_classify_magnitude()` | 37 | Classify as major/minor/patch |
| `backup_needed()` | 50 | Check if backup is needed |
| `backup_mod()` | 62 | Copy mod folder to backup (with ignore patterns) |
| `backup_all()` | 77 | Iterate mod list, backup changed mods |
| `get_backup_root()` | 94 | Resolve backup root path |

### `source/mods/sorter.py`
| Function | Line | Purpose |
|---|---|---|
| `fetch_initial()` | 37 | Fetch masterlist on first run |
| `save_last_order()` | 55 | Persist order to DB |
| `load_last_order()` | 59 | Load last order from DB |
| `_topological_sort()` | 156 | Dependency-based ordering |
| `should_preserve_name()` | 200 | Check if mod name is locked |
| `auto_sort()` | 210 | Group priority + topological mod sort |

### `source/mods/conflict_index.py`
| Function | Line | Purpose |
|---|---|---|
| `get_cached_files()` | 49 | Return conflict files (cached via fingerprint) |
| `invalidate()` | 74 | Clear cached fingerprint for folder |
| `_quick_token()` | 79 | Dir mtime + entry-name token |

### `source/mods/folder_watcher.py` — ModFolderWatcher
| Method | Line | Purpose |
|---|---|---|
| `start()` | — | Begin recursive watch |
| `stop()` | — | Stop observer, clear buffer |
| `clear_pending()` | — | Discard buffered events |

### `source/core/config.py` — _Config (dataclass, line 24)
| Method | Line | Purpose |
|---|---|---|
| `load()` | 190 | Read config.toml, init DB |
| `save()` | 287 | Debounced config write |
| `get_settings()` | 186 | QSettings for UI state |
| `apply_preset()` | 274 | Apply theme preset |

### `source/core/worker.py`
| Class | Line | Purpose |
|---|---|---|
| `WorkerThread` | 61 | QThread wrapper with finished/error signals |
| `ManagedWorker` | 129 | High-level worker manager (start/wait/cancel) |

### `source/controller/controller.py` — ControllerManager
| Class/Signal | Line | Purpose |
|---|---|---|
| `GamepadType` (IntEnum) | 15 | PlayStation/Nintendo/Generic |
| `Button` (IntEnum) | 30 | All button constants |
| `Axis` (IntEnum) | 54 | All axis constants |
| `ControllerManager` | 79 | SDL3 gamepad manager |
| `connected(str, int)` | — | Gamepad name + type |
| `disconnected()` | — | Disconnected |
| `activity_changed(bool)` | — | Active/inactive |
| `button_down(int)` | — | Button pressed |
| `axis_moved(int, int)` | — | Axis index + value |

### `source/theme/theme.py` — Theme (dataclass, line 88)
| Function | Line | Purpose |
|---|---|---|
| `discover_themes()` | 110 | Scan themes directory |
| `load_colors()` | 138 | Load TOML colors |
| `load_qss()` | 161 | Load QSS stylesheet |
| `build_palette()` | 177 | Build QPalette from colors |
| `load_theme_colors()` | 211 | Load and apply theme colors |

### `source/updater/updater.py`
| Function/Class | Line | Purpose |
|---|---|---|
| `get_latest_release()` | 55 | Fetch latest GitHub release |
| `is_newer_version()` | 63 | Compare versions |
| `get_download_asset()` | 67 | Get download URL for platform |
| `download_asset()` | 125 | Download update asset |
| `install_appimage_update()` | 154 | Install AppImage delta update |
| `install_windows_update()` | 172 | Install Windows NSIS update |
| `UpdateDialog` | 213 | Update notification dialog |

## Startup Flow (main.py)
1. `config.load()` — read TOML, init DB, detect mods folder
2. `QApplication(sys.argv)` — save native style name
3. Apply theme if `active_theme != "System"` (load palette + QSS + color overrides)
4. `DragApp()` — build_ui builds splitter, start watcher, masterlist refresh, controller init
5. `main_window.show()` → `app.exec()`

## Module-Level Constants
| Constant | File | Line | Value |
|---|---|---|---|
| `CONFLICT_ROLE` | `delegates.py` | 40 | `UserRole + 1` |
| `SEPARATOR_ROLE` | `delegates.py` | 41 | `UserRole + 2` |
| `PREV_CHECK_ROLE` | `delegates.py` | 42 | `UserRole + 3` |
| `OVERWRITTEN_ROLE` | `delegates.py` | 43 | `UserRole + 4` |
| `NORMALIZED_NAME_ROLE` | `delegates.py` | 44 | `UserRole + 5` |
| `WINS_ROLE` | `delegates.py` | 45 | `UserRole + 6` |
| `LOSSES_ROLE` | `delegates.py` | 46 | `UserRole + 7` |
| `EMPTY_ROLE` | `delegates.py` | 47 | `UserRole + 8` |
| `LEVEL_TAGS` | `console.py` | 31 | `debug/info/warning/error → ([TAG], QColor)` |

## Notes
- Console dedup uses `_dedup_key()` which strips all digits (`\d+ → #`) before comparing.
- Conflict timer is a 150ms `QTimer` debounce — all `_conflict_timer.start()` calls are deduped.
- Watchdog has a 500ms debounce timer — event types filtered to `{created, modified, deleted, moved}`.
- `hashlib.blake2b` is used for fingerprinting (stdlib, no C-extension issues).
- `app.setStyle()` only called when `config.theme != "native"` — native mode leaves platform QStyle.
- `notify-py` for desktop notifications (libnotify/osascript/PowerShell toast).
- `imagediff` merge uses `--output` flag.
- Backup ignores `MERGED` directory (no point in backing up merged results).
- `log_colored(segments)` supports both `str` (color hex) and `QTextCharFormat` per-segment formatting.
