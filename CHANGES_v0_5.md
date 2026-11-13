# SQL Server Simulator 0.5.0 · Visual field linking and close controls

Designed and developed by Ali Sayyadi.

## User-facing changes

- Direct drag from a parent **PK field row** to a child **FK field row** in Database Diagram, including reverse FK-to-PK drag for convenience. No SQL code needed and no need to enable table-level Connect-by-Drag for column linking.
- The relationship wizard displays the selected parent and child fields and can use an existing FK column or create a new one. Users can select 1:N, shared-PK 1:1, N:M with a junction table, or self-reference.
- Before applying, the engine rejects invalid parent fields, incompatible logical SQL types, duplicate FK use, existing orphan values, invalid required NULLs and unsupported shared-PK identity configurations. Relationships are actual SQLite foreign-key constraints and checked in the engine.
- Close table cards via **×** in their upper-right corner or context menu. Closing only hides the table in the *current diagram*. **Reopen Tables** or diagram context menu restores it. Refresh preserves the hidden state.
- Open table-data tabs are closable via tab **×** and a prominent **Close View** button. Closing views does not delete data. Query and Diagram workspaces remain open.
- Diagram edges for physical relationships now align with column rows where possible, making FK mapping easier to explain.

## Validation and limitations

- In this environment, 46 underlying database tests passed and six Qt smoke tests were skipped because PySide6 was not installed. The Windows build script runs all Qt tests before generating EXE.
- The SQLite engine implements an educational subset of SQL Server behavior, not all Microsoft SQL Server features or T-SQL.
- Only single-column PK targets are supported in the visual wizard. Composite-parent-key FKs and arbitrary UNIQUE-key references are beyond this educational wizard.
- For tables with existing data, potentially destructive schema migrations are denied when safety cannot be assured. Always back up important .db files before redesign.
- Windows Defender or other antivirus software may block locally packed PyInstaller executables. Do not disable security protections; run from source for testing and inspect any detections.
