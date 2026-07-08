# IsaacMM Agent Guide

## 1. Think Before Coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

    State your assumptions explicitly. If uncertain, ask.
    If multiple interpretations exist, present them - don't pick silently.
    If a simpler approach exists, say so. Push back when warranted.
    If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.

    No features beyond what was asked.
    No abstractions for single-use code.
    No "flexibility" or "configurability" that wasn't requested.
    No error handling for impossible scenarios.
    If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

Touch only what you must. Clean up only your own mess.

When editing existing code:

    Don't "improve" adjacent code, comments, or formatting.
    Don't refactor things that aren't broken.
    Match existing style, even if you'd do it differently.
    If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:

    Remove imports/variables/functions that YOUR changes made unused.
    Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

    "Add validation" → "Write tests for invalid inputs, then make them pass"
    "Fix the bug" → "Write a test that reproduces it, then make it pass"
    "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Project structure
IsaacMM/source/ houses the core functionality of the application
IsaacMM/source/components stores all UI generating code, which is separated from the Logic code

## Coding conventions
- All platform-specific code gated behind sys.platform checks
- Never import platform libs at module level
- Use ManagedWorker for all background tasks (see source/worker.py)
- Config accessed via config.field_name (module-level __getattr__)

## Before making changes
1. Read PROGRESS.md and identify the target item
2. Check its Blocked by: field - do not implement if blocker is incomplete
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
