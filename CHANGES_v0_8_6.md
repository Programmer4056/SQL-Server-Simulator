# SQL Server Simulator v0.8.6 · Release Candidate

## Data-integrity improvements

- All no-query record inserts and updates use common column-type and required-value validation.
- Parent-side FK existence is checked before writing for 1:1, 1:N, N:M (composite or surrogate bridge), and self-references. The SQLite FK constraint remains the final authority.
- Invalid FK values, missing required fields, bad integer/decimal/BIT values, oversized `NVARCHAR(n)`, and invalid ISO date/time values produce explicit errors. Failed writes do not change existing records.
- Database-generated IDENTITY columns remain read-only in both insert and edit interfaces.

## Data-entry workflow

- Data tabs include a permanent last row marked NEW and a Save New Row action, with ordinary Tab-key cell navigation and a Ctrl+Enter shortcut.
- After saving, the table reloads and another blank NEW row is available for consecutive inserts.
- The prior standalone Insert Record dialog remains an alternative. GridRowEditor returns keyboard focus to its next NEW row after each insert.

## Credits

- **Development:** Ali Sayyadi (علی صیادی)
- **Software testing & quality assurance:** Mahan Pakravan-Nasab (ماهان پاکروان‌نسب)
- The contributor's name is stored centrally in `src/version_info.py` and appears in the English and Persian About and Welcome views. More contributors can be added in later releases.

## Known limitations

- Built on SQLite, not Microsoft SQL Server. Only a documented T-SQL subset is simulated.
- Cross-platform GUI tests and installer smoke checks must be executed on their respective systems before stable release.
