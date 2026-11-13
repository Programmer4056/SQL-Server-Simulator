# v0.6.1 fixes

- Diagram two-click and direct-drag linking fixed: moving preview no longer intercepts the destination field.
- New Fit Diagram and 100% controls prevent tiny non-clickable fields.
- Welcome title and description now use larger minimum heights and scroll vertically on smaller windows.
- Windows pre-build tests simulate mouse movements and verify welcome geometry (test_qt_click_link_v061.py).

# SQL Server Simulator v0.6.1 | New diagram tools

Designed and developed by **Ali Sayyadi**. Initial preview; bugs may exist. Report: `Ali.sayyadi200@gmail.com`.

## New in 0.6

- **Select a relationship:** Click its line or its label in Database Diagram. The selected line highlights and details appear in Properties.
- **Delete a relationship:** Right-click the line, press the Delete key with the diagram focused, or use **Delete Link**. Confirm the action. This removes a **real FK constraint** but preserves the related tables, columns and data. Future invalid references will no longer be blocked for that relationship.
- **Delete an N:M relationship:** Click the dashed N:M annotation to remove both physical FKs of the junction in one transactional rebuild. The junction table and its records remain intact. Deleting only one bridge FK removes only that FK.
- **Manual relationship drawing:** Choose **Draw Link (2 clicks)**, click a parent PK field, then a child FK field to open the mapping wizard. Press Esc to cancel. Direct field drag-and-drop is still available.
- **Welcome panel:** Readable separated labels, wrapping, bilingual text direction, warning, and direct Gmail bug report.

## Start on Windows

Extract the full ZIP into a new folder. Run `run_windows.bat` to test the application, then `build_windows.bat` to create a distributable EXE. Inno Setup 6 is needed for a Setup installer. Before changing schema, back up your `.db` file. If Windows security blocks packaging, investigate Protection History instead of disabling antivirus.

This is a teaching application with an SQLite engine, not Microsoft SQL Server or the official SSMS. It does not implement all T-SQL features.

---

# SQL Server Simulator v0.6.1 (Windows desktop)

**Designed and developed by Ali Sayyadi**. Report bugs from Help > Report a bug via Gmail or email `Ali.sayyadi200@gmail.com`.

Educational Qt/PySide6 + SQLite-based alternative **inspired by** SSMS, not Microsoft SQL Server. This preview may contain bugs. It is not affiliated with Microsoft and does not implement all T-SQL features.

## v0.5: Direct field mapping and closable views

- Drag from a **parent PK field row** to a **child FK field row** in Database Diagram. This works without switching on Connect by Drag. Drag the **table header** to reposition a table.
- A field-mapping wizard opens with your exact selected columns. Choose 1:N, shared-key 1:1, N:M (creates a real junction table), or SELF hierarchy. Existing columns or a new FK column can be selected where applicable.
- Constraints are checked before changing the schema: PK target, type compatibility, existing orphan values, NULL for required FKs, and FK reuse. Invalid changes are blocked, preserving data.
- Click **× on a table card** or right-click **Close table in diagram** to hide it without dropping it. Use the **Reopen Tables** button or the diagram's context menu to restore hidden cards.
- Close a table data view using its **tab ×** or **Close View** button; the database is unchanged. Dialogs support Cancel and window close.

## Run and build

1. Extract the complete archive into a **new folder**.
2. Double-click `run_windows.bat` to use the Qt desktop app directly (Python 3.10+; initial dependency installation requires internet).
3. After testing, run `build_windows.bat`. The script runs core and Qt smoke tests before packaging.
4. Portable folder executable: `dist\SQLServerSimulator\SQLServerSimulator.exe`. Keep the complete folder, including `_internal`.
5. With Inno Setup 6 installed, the build script also creates `installer_out\SQL_Server_Simulator_Setup_v0.6.1.exe`. The compiled Setup is NOT included in this source ZIP.

## Database Diagram: no SQL needed

- Click **New Table**, or right-click the diagram background > **New Table…**.
- Double-click a table in Database Diagram, or right-click a table in the diagram / Object Explorer > **Design Table…** to edit its columns. Design supports data-type dropdowns (`NVARCHAR`, `DECIMAL`, etc.), PK, nullable, identity seed/increment, adding/deleting/renaming columns. Existing rows are retained if the transaction passes validations.
- Click **Connect by Drag**, then drag **from the parent table to the child table**. The relationship wizard opens with source and target selected. Or use the normal Relationship Wizard / right-click menu.
- Available types: **shared-PK 1:1**, **1:N** (parent PK copied to child FK), **N:M** (real junction table, composite or surrogate PK), and **SELF** (same-table hierarchical 1:N). N:M appears as two actual 1:N FKs through the bridge plus a dashed conceptual overlay.
- Referential integrity is enforced for all non-NULL foreign keys. Invalid references fail; `Database > Check Referential Integrity…` verifies the whole project. The Query Editor cannot disable foreign-key checks.
- If a redesign would violate relationships/constraints, it is rolled back. The visual designer intentionally refuses advanced custom defaults/triggers/indexes and risky referenced-PK changes rather than silently damaging data.

## Try the included sample

Open `examples\Diagram_Training_v0_4.db`. It includes Department, Student, Profile, Course and Enrollment with 1:1, 1:N, N:M and Student.MentorID self-reference plus valid sample records.

## Other features

Dark/light themes; English by default, Persian selectable; SQL editor; data entry and grid viewer; identity seed/increment; PNG export; T-SQL `.sql` generation with table/data scope and requested SQL Server target version. A `.sql` script is NOT a native `.bak` backup. Compatibility across server versions has not been fully verified. SQLite differs from SQL Server in types and identity implementation.

## Tests

```
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Qt UI tests require PySide6 and are executed on the target Windows machine before packaging.
