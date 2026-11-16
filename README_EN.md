# v0.8.9: closable panels and offline Windows EXE

- Obvious × controls on Object Explorer, Properties and Results docks; reopen from **View**.
- SQL Editor and Database Diagram tabs can be closed and reopened without discarding their content.
- `build_windows_offline.bat` creates a **single-file offline Windows EXE** bundling Python and Qt dependencies; university machines need no Python installation or internet.
- See [`OFFLINE_DEPLOYMENT_FA.md`](OFFLINE_DEPLOYMENT_FA.md) for delivery options.

---

# v0.8.8: Welcome screen and SQL Server scripting

- Compact one-line Persian/English welcome titles with measured minimum label heights and scrollable layout. Credits for Ali Sayyadi and Mahan Pakravan-Nasab remain visible.
- Generate Scripts produces SQL Server-oriented T-SQL for the supported subset: tables, primary/foreign keys, unique constraints, simple indexes, rows, Unicode, and IDENTITY(seed,increment). Schema/data ordering is appropriate for SSMS execution.
- Unsafe SQLite-specific schema features now raise explicit errors instead of silently disappearing.
- Example: [`examples/SQLServer_2022_TSQL_v0_8_8.sql`](examples/SQLServer_2022_TSQL_v0_8_8.sql).
- **Limits:** SQL script, not a `.bak`; no complete View/Procedure/Function/user/permission export; no live Microsoft SQL Server verification in this environment. Test against a non-production SQL Server instance.

---

# SQL Server Simulator v0.8.7

## v0.8.7: Persian localization and responsive welcome card

- Localized the Database Diagram context menus, relationship actions, table visibility actions, and field-linking hints.
- Applied RTL direction to Persian context menus. User-defined table/column identifiers remain unchanged.
- Rebuilt the welcome card to size vertically with its contents and scroll on smaller viewports. Developer and QA credits are independent labels.
- Synchronized the version with cross-platform builders and About text.

## Previous v0.8.6 features: data records, SQL file import and query editor zoom

- **Edit/delete records** from Data tabs or Edit Rows. Database FK and identity rules are enforced.
- **Open SQL Script** using File → Open SQL Script… or `Ctrl+Shift+O`; UTF-8/UTF-16 text is shown for review, and execution needs confirmation. Partial execution is possible if later statements fail.
- **Educational IntelliSense** suggests SQL keywords, table and view names, and columns; use `Ctrl+Space`, then Enter/Tab to accept.
- **Query font zoom** via `+`, `−`, `100%`, `Ctrl+Mouse Wheel`, `Ctrl++`, `Ctrl+=`, `Ctrl+-` and `Ctrl+0`.
- **Diagram zoom** supports matching shortcuts while the diagram tab is active.
- Import demo: [`examples/SQL_Import_v0_8_4.sql`](examples/SQL_Import_v0_8_4.sql).

The simulator uses SQLite and supports only a documented educational T-SQL subset. It cannot reliably execute arbitrary SQL Server exports.


**Designed and developed by Ali Sayyadi**

An educational Windows desktop application for understanding table design, primary/foreign keys, referential integrity, and SQL database diagrams. Built with **Python 3.12**, **PySide6/Qt 6**, and **SQLite 3**.

> **Independent educational tool.** It is not Microsoft SQL Server and is not affiliated with Microsoft. T-SQL support is a limited teaching subset, not full compatibility. This preview may contain bugs.

## Key features

- No-SQL database and table wizards; a SQL Server-style field designer with NVARCHAR/DECIMAL and IDENTITY seed/increment controls.
- Mouse-driven 1:1, 1:N, N:M (junction table), and self-referencing links with real foreign-key constraints.
- Interactive diagram with link selection, relationship deletion, field-to-field linking, and drag-to-connect.
- Auto Layout that prioritizes high-degree tables, scrollable/expandable canvas, middle-mouse panning, Ctrl+wheel zoom.
- Right-click Drop Table / Drop Column actions with confirmation and guarded migrations; hidden diagram cards never delete tables.
- Resizable, floating, closable Object Explorer / Properties / Query Results docks, draggable toolbar, Reset Window Layout command.
- Theme-aware native icons; English and Persian UI; dark and light modes.
- T-SQL teaching commands: `CREATE DATABASE`, `USE`, standalone `GO`, a small `CREATE TABLE` subset with IDENTITY; `CREATE USER`, `GRANT`, and `DENY` are **metadata-only demonstrations, NOT enforced security**.
- Generate educational SQL Server scripts. A script export is **not** a real binary SQL Server `.bak` backup.

## Run on Windows

Extract the ZIP and launch `run_windows.bat` (requires Python 3.12). To package the desktop app, run `build_windows.bat` (PyInstaller). Install Inno Setup 6 to generate the graphical installer. Neither EXE nor Setup is precompiled in this source package.

## Example

Run [`examples/TSQL_Teaching_v0_7.sql`](examples/TSQL_Teaching_v0_7.sql) from the SQL editor. `CREATE DATABASE Training; GO; USE Training` creates/opens a local SQLite-backed educational project. Unsupported SQL Server server/security commands fail explicitly. Permission catalog records do not authenticate users or enforce access restrictions.

## Validation

```shell
python -m unittest discover -s tests -v
```

The Windows builder runs engine and Qt regression tests before packaging. Source tests on systems without PySide6 skip the graphical checks; those UI behaviors must be validated on Windows.

**Bug reports:** [Ali.sayyadi200@gmail.com](mailto:Ali.sayyadi200@gmail.com)

[Persian README](README.md) | [Detailed Persian guide](README_FA.md)


Cross-platform build: use run_unix.sh for macOS/Linux source runs, build_macos.sh and build_linux.sh for native artifacts, or the GitHub Actions multi-platform workflow. Windows continues to use its .bat scripts. Python/PySide6/SQLite source is shared; platform-specific binaries are built separately.

## Diagram zoom controls (v0.8.3)

**Zoom In (+)** and **Zoom Out (−)** are now available in Database Diagram. They remain operational after **Auto Layout** fits very large diagrams to a scale below the former 20% limit. **Fit Diagram**, **100%**, and **Ctrl + mouse wheel** continue to work. The current zoom percentage is displayed in the toolbar.


## Educational T-SQL modules (v0.8.3)

- `CREATE VIEW dbo.Name AS SELECT ...` creates a **real SQLite view** that can be queried with `SELECT`.
- `CREATE PROC` or `CREATE PROCEDURE` stores a limited parameterized procedure. `EXEC` / `EXECUTE` runs its `SELECT`, `INSERT`, `UPDATE`, or `DELETE` statements transactionally.
- `CREATE FUNCTION` registers a persisted scalar `RETURN` expression, callable with `SELECT dbo.FunctionName(...)`.
- `CREATE OR ALTER` and `DROP VIEW/PROC/FUNCTION` are supported for these limited objects.
- Separate module definitions with a standalone `GO`. Example: [`examples/TSQL_Modules_v0_8_3.sql`](examples/TSQL_Modules_v0_8_3.sql).

**Limitations:** This is an educational SQLite translation, not SQL Server stored procedure or UDF execution. No IF/WHILE, cursors, TRY/CATCH, output parameters, dynamic SQL, table-valued functions, or complex procedural bodies. Unsupported commands fail explicitly.

## What's new in v0.8.7

- True many-to-many junction with either a composite PK (both FKs) or a surrogate IDENTITY PK plus a UNIQUE pair constraint.
- Optional 1:N child composite PK, with safety checks preventing a composite PK combined with an existing IDENTITY.
- Generate Scripts Wizard now offers Save to `.sql` or Open in Query Editor without execution.
- In-place table-cell editing via double-click/F2. IDENTITY cells remain read-only. Type and PK/FK/UNIQUE constraints are checked on every update.
- Compact, responsive welcome card; bilingual Gmail and mailto bug-report drafts.
- Ctrl++ / Ctrl+= / Ctrl+- / Ctrl+0 keyboard zoom shortcuts, button zoom, and Ctrl+wheel zoom.
- Improved Persian labels, confirmation buttons and human-readable error summaries. Raw technical messages remain available in Details.

This is a teaching simulator backed by SQLite, not Microsoft SQL Server; T-SQL feature coverage remains limited.

## v0.8.7 Release candidate

- Validate FK parent values, required fields and common SQL data types before row insert/update, while keeping SQLite constraints authoritative.
- Editable NEW row at the bottom of the table data tab, with Tab navigation and a Save New Row action (Ctrl+Enter).
- Existing record cells remain editable in place; database-generated IDENTITY values remain read-only.
- **Software testing & quality assurance:** Mahan Pakravan-Nasab (ماهان پاکروان‌نسب).

The project is a teaching simulator, not the SQL Server engine. Cross-platform GUI testing is required before publishing a stable release.
