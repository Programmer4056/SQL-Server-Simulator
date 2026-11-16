# Changes in SQL Server Simulator v0.8.5

- Added safe 1:N foreign-key-as-part-of-child-composite-PK option; existing child PK may alternatively stay independent.
- Verified both pre-existing N:M junction strategies (FK-pair composite PK vs surrogate IDENTITY + unique FK pair) and actual FK integrity checks.
- Rebuilt Generate Scripts Wizard to offer on-disk `.sql` output or open generated T-SQL in the Query Editor without executing it.
- Enabled edit-in-place in main Data tabs and Edit Rows grid; IDENTITY and binary cells are read-only. Changes use parameterized, optimistic row updates and DB constraints.
- Reduced Welcome card to a compact ~480px wide portrait/square layout with scroll fallback.
- Localized Gmail and mailto bug-report subject/body to Persian when Persian is selected.
- Preserved Ctrl++/Ctrl+=, Ctrl+-, Ctrl+0 and mouse/toolbar zoom in Query Editor and Diagram.
- Added a shared Persian label library, common SQLite error summaries, and localized standard message-box actions.
- Version number updated to 0.8.5 in app, installer and build workflows.

## Important limitations
- No bundled native SQL Server engine. Advanced T-SQL semantics remain unsupported.
- PySide6 was absent in this build environment; GUI tests in this package remain to be run on a target desktop OS.
- Technical diagnostics may retain original English details for troubleshooting.
