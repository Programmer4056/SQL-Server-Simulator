# SQL Server Simulator v0.7.0: UI, SQL and diagram quality update

- Added a controlled, documented educational T-SQL compatibility layer: local CREATE DATABASE / USE, GO batches, a limited CREATE TABLE IDENTITY parser, and explicitly simulated CREATE USER / GRANT / DENY metadata.
- Added guarded DROP TABLE and DROP COLUMN engine APIs. The diagram and Object Explorer offer destructive operations with confirmation.
- Improved stale schema handling using sqlite_master, PRAGMA schema_version polling, and safe closing of tabs referencing missing tables.
- Replaced dark-mode-unfriendly system toolbar glyphs with palette-aware hand-drawn icons; applied a Qt palette to native controls.
- Reduced minimum main-window size; made explorer, properties and output docks closable, draggable and floatable; enabled movable toolbar, panel resizing and Reset Window Layout.
- Added Auto Layout (connected-component/degree-based center-first layout), spacious scrollable canvas, middle-mouse panning, Ctrl+wheel zoom and safe zoom bounds.
- Added horizontally scrollable diagram toolbar to support small displays.
- Added comprehensive non-Qt regression tests and optional Qt smoke tests executed on Windows before packaging.

## Important scope limitations

SQLite remains the database engine. SQL Server security statements are recorded as **un-enforced teaching metadata only**. No SQL Server logins/roles, SQL Server native backups, or complete T-SQL grammar are implemented. We did not change proprietary Microsoft code or assets.
