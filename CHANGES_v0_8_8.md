# SQL Server Simulator 0.8.8

## Welcome Card
- One-line title in both languages; explicit title/description label minimum heights.
- Compact quality-assurance credits; names preserved.
- Height adapts with vertical scroll on small screens.

## Generate Scripts
- Emits SQL Server T-SQL for the supported subset, with SSMS-style GO/session SET statements.
- Preserves PK, composite PK, FK, UNIQUE constraints and basic ordinary indexes.
- Preserves identity seeds/increments, Unicode strings and row values.
- Creates schema then data then checked foreign keys.
- Data-only scripts order parent rows before child rows where acyclic.
- Explicit error for custom CHECK expressions/triggers, incompatible SQL Server types or unsafe index cases.
- Sample export in examples/SQLServer_2022_TSQL_v0_8_8.sql.

## Limitations
- Not a SQL Server .bak backup or byte-identical SSMS export.
- Views, procedures, scalar functions and security catalog are not included.
- Qt visual test and real SQL Server execution must be completed on target machines.
