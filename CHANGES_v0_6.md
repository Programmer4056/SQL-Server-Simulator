# SQL Server Simulator v0.6.0 | Diagram interaction and welcome UI

Developer: Ali Sayyadi | Preview build

## New: selectable, deletable relationships
- Click a physical FK line or its label/cardinality marker to highlight the relationship.
- Delete from the **Delete Link** toolbar button, right-click the line, or press **Delete** with the diagram focused.
- A confirmation explains that **the real database FK constraint will be removed**, not just a line.
- Physical FK removal keeps tables, data, columns, primary keys and remaining FK constraints intact.
- For a conceptual N:M dashed connection, confirmed deletion removes **both bridge FKs in one transactional rebuild**, preserving the junction table and records. A remaining standalone FK is shown independently if only one link was deleted.
- Custom triggers or indexes that the simulator cannot preserve still block visual rebuilds safely.

## New: draw relationships manually
- Existing column-drag linking is retained.
- **Draw Link (2 clicks)** lets students click the parent PK field, then click the child FK field. It opens the field-mapping wizard using exactly those fields.
- Press **Esc** to cancel draw mode; moving table headers and drawing links remain distinct interactions.
- New relationships are still checked for compatible data types, proper PK ownership, 1:1/1:N/SELF/N:M constraints and existing orphan values.

## New: welcome panel
- New responsive, scrollable, centered welcome card.
- Separate, wrapping labels for title, description, developer attribution, initial-release warning and Gmail bug-report link.
- Per-label RTL for Persian; English default and light/dark theme retained.

## Tests
- Six new core relationship deletion tests: preserve data, identity, other FKs, junction rows, self-reference, and refuse unsupported index changes.
- Three new optional Qt tests: relationship selection, draw-mode toggle, bilingual welcome.
- The source test suite contains 61 tests. 52 non-Qt tests passed in this build environment; nine Qt tests will run on Windows before packaging.

## Important limitations
- This is a SQLite-powered **teaching simulator**, not a Microsoft SQL Server engine, SSMS executable, or complete T-SQL implementation.
- Removing an FK eliminates referential checking for that link. Existing data is preserved, and removing the rule does not automatically make orphan values valid under any future re-added constraint.
- Native Windows EXE and Setup are produced by build_windows.bat on Windows. They are not precompiled in this ZIP.
- Back up important .db files before modifying schema.
