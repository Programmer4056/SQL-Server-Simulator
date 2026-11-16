# SQL Server Simulator v0.8.7 | Persian UI & Welcome Layout

- Translated Database Diagram context menus and selection/hide/restore actions.
- Translated relationship removal warnings and link instructions, and aligned Persian menus RTL.
- Added live language switching to Diagram and TableNode tooltips without renaming database identifiers.
- Removed fixed card heights, separated development and QA credits, enabled scrolling on small welcome windows.
- Updated Windows/macOS/Linux packaging metadata to 0.8.7.
- Added `tests/test_v087_localization.py` for translation coverage and optional offscreen Qt layout checks.

**Validation:** 161 tests discovered: 124 passed, 37 Qt tests skipped because PySide6 is not installed in the current environment. GUI verification must be run on a machine with Qt installed.
