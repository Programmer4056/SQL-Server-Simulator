# SQL Server Simulator v0.8.4 | Changes

- Add row editing and deletion in Data tabs and the Edit Rows grid, with PK/FK checks and stale-row detection.
- Add Drop action for views, procedures and functions in Object Explorer (with confirmation).
- Add Open SQL Script (UTF-8/UTF-16, <=10 MB), preview and explicit execution confirmation.
- Add educational IntelliSense suggestions for SQL keywords, table/view names and columns.
- Add visible Query Editor zoom buttons (+, −, 100%), Ctrl+mousewheel zoom and keyboard shortcuts Ctrl++, Ctrl+=, Ctrl+-, Ctrl+0.
- Add matching diagram keyboard shortcuts scoped to the Diagram tab.
- Add limited translation of SQL Server-style single-column ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ... to a real SQLite FK.
- Persist the SQL Editor font zoom setting.
- Include tests covering identity preservation, referential integrity, concurrent row edits, SQL script encodings and importing an actual foreign-key relationship.

## Limitations

- Arbitrary Microsoft SQL Server .sql exports are not supported. Only the documented subset will work.
- Import scripts are not globally atomic: some commands may have completed before a later unsupported command fails. Back up data first.
- Qt GUI tests must be run on the target platform with PySide6 installed; they were skipped in the development environment.
- Built installers must be generated and tested on Windows/macOS/Linux runners independently.
