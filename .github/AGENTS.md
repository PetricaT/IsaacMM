# IsaacMM Agent Guide

## Project structure
IsaacMM/source/ houses the core functionality of the application
IsaacMM/source/components stores all UI generating code, which is separated from the Logic code

## Coding conventions
- All platform-specific code gated behind sys.platform checks
- Never import platform libs at module level
- Use ManagedWorker for all background tasks (see source/worker.py)
- Config accessed via config.field_name (module-level __getattr__)

## Key patterns
[the WorkerThread pattern, the RemoteCache pattern, etc.]

## Before making changes
1. Read PROGRESS.md and identify the target item
2. Check its Blocked by: field — do not implement if blocker is incomplete
3. Read all Files: listed in the item before touching anything
4. After completing, update item status in PROGRESS.md

## Testing
You must activate the virtual environment created by uv (source .venv/bin/activate)
You must verify that there are no linting errors, no indentation errors, and the code compiles via ast.
You must run the application with uv run main.py to check for crashes on startup, and have a 5 second timeout to close it if it didnt crash.

## Do not touch
- packaging/ unless the task explicitly involves it
- masterlist.yaml
- game_versions.json
- assets/ is READ only
