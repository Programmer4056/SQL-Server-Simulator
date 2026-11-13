# Version 0.4.0

- Interactive Database Diagram: right-click New Table, right-click/double-click Design Table, Connect by Drag (parent to child), preselected relationship wizard, and single-table self-referencing link.
- Relationship types: shared-PK 1:1, 1:N, N:M junction table with conceptual dashed annotation, SELF hierarchy 1:N. Endpoints show 1/N/M markings and cardinality forks.
- Transaction-safe `edit_table` with column add, rename, delete, PK/nullability/type/identity settings; copy existing values, retain FKs and UNIQUE constraints; reject incompatible migrations.
- `self_reference` uses a real SQLite FK to the same table; NULL for root rows.
- New `Check Referential Integrity` action. Query Editor blocks switching FK enforcement off.
- Five-table sample database showing all four relationship patterns.
- Added backend regression tests and Qt smoke tests. Windows build runs them before packaging.
- No Microsoft SQL Server engine or `.bak` backup included; T-SQL subset only.
