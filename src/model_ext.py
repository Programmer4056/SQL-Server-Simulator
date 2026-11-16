"""Safe no-query data editing helpers for the teaching database.

The database engine (SQLite) generates identity keys, not the UI.
"""
from __future__ import annotations
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, time
from uuid import UUID
from core import LabDatabase, LabError, identifier, q


def table_ddl(db: LabDatabase, table: str) -> str:
    db._exists(table)
    row = db.connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row[0] if row else ''


def is_identity(db: LabDatabase, table: str, column: str) -> bool:
    """True only for an explicitly declared INTEGER PRIMARY KEY AUTOINCREMENT.

    No heuristic based on primary key name, since not every PK is IDENTITY.
    """
    ddl = table_ddl(db, table)
    quoted = re.escape('"' + identifier(column) + '"')
    unquoted = re.escape(identifier(column))
    pattern = r'(?:' + quoted + r'|\b' + unquoted + r'\b)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b'
    return re.search(pattern, ddl, re.I) is not None



_INTEGER_RANGES = {
    'TINYINT': (0, 255), 'SMALLINT': (-32768, 32767),
    'INT': (-2147483648, 2147483647),
    'INTEGER': (-9223372036854775808, 9223372036854775807),
    'BIGINT': (-9223372036854775808, 9223372036854775807),
}


def validate_value(db: LabDatabase, table: str, column: str, value):
    """Validate GUI data against declared SQL Server logical types.

    SQLite's flexible type affinity alone is not an adequate teaching check.
    Use this path for INSERT and UPDATE through the no-query interface.
    """
    if value is None:
        return None
    typ = db.logical_type(table, column).upper().strip()
    if typ in _INTEGER_RANGES or typ in ('BIT', 'BOOLEAN'):
        if isinstance(value, (bytes, bytearray)):
            raise LabError(f'Data type mismatch: {column} must be an integer ({typ}).')
        if isinstance(value, str):
            value = value.strip()
            if not re.fullmatch(r'[+-]?\d+', value):
                raise LabError(f'Data type mismatch: {column} requires an integer ({typ}).')
        try:
            number = int(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise LabError(f'Data type mismatch: {column} requires an integer ({typ}).') from exc
        if isinstance(value, float) and (not value.is_integer()):
            raise LabError(f'Data type mismatch: {column} requires an integer ({typ}).')
        if typ in ('BIT', 'BOOLEAN'):
            if number not in (0, 1):
                raise LabError(f'Data type mismatch: {column} BIT accepts only 0 or 1.')
        else:
            low, high = _INTEGER_RANGES[typ]
            if not low <= number <= high:
                raise LabError(f'Data type mismatch: {column} exceeds the range of {typ}.')
        return number
    if typ.startswith(('DECIMAL', 'NUMERIC')) or typ in ('FLOAT', 'REAL', 'MONEY', 'SMALLMONEY', 'DOUBLE'):
        try:
            numeric = Decimal(str(value).strip())
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise LabError(f'Data type mismatch: {column} requires a numeric value ({typ}).') from exc
        if not numeric.is_finite():
            raise LabError(f'Data type mismatch: {column} must be a finite number.')
        spec = re.fullmatch(r'(?:DECIMAL|NUMERIC)\((\d+)(?:,\s*(\d+))?\)', typ)
        if spec:
            precision, scale = int(spec.group(1)), int(spec.group(2) or 0)
            sign, digits, exponent = numeric.as_tuple()
            frac = max(0, -exponent)
            integer_digits = max(0, len(digits) + exponent)
            if frac > scale or integer_digits > precision - scale:
                raise LabError(f'Data type mismatch: {column} exceeds {typ} precision/scale.')
        return float(numeric)
    if typ in ('DATE', 'DATETIME', 'SMALLDATETIME', 'DATETIME2', 'TIME') or typ.startswith(('DATETIME2(', 'TIME(')):
        if not isinstance(value, str):
            raise LabError(f'Data type mismatch: {column} requires an ISO date/time string.')
        try:
            if typ == 'DATE': date.fromisoformat(value)
            elif typ.startswith('TIME'): time.fromisoformat(value)
            else: datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError) as exc:
            raise LabError(f'Data type mismatch: {column} requires a valid ISO date/time ({typ}).') from exc
        return value
    if typ == 'UNIQUEIDENTIFIER':
        try: UUID(str(value))
        except ValueError as exc:
            raise LabError(f'Data type mismatch: {column} requires a valid UUID.') from exc
        return str(value)
    if typ.startswith(('NVARCHAR', 'VARCHAR', 'NCHAR', 'CHAR', 'TEXT')):
        if not isinstance(value, str):
            raise LabError(f'Data type mismatch: {column} requires text ({typ}).')
        match = re.fullmatch(r'(?:N?VARCHAR|N?CHAR)\((\d+)\)', typ)
        if match and len(value) > int(match.group(1)):
            raise LabError(f'Data type mismatch: {column} exceeds {typ} maximum length.')
        return value
    if typ.startswith(('BINARY', 'VARBINARY')):
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise LabError(f'Data type mismatch: {column} requires binary data.')
        return bytes(value)
    return value


def check_row_constraints(db: LabDatabase, table: str, values: dict, *, inserting=False):
    """Check required columns and all FK parent rows before writing.

    Database-level FK constraints remain authoritative, including during
    concurrent changes and for raw SQL. The preflight only makes errors clearer.
    """
    columns = db.columns(table)
    normalized = dict(values)
    for column in columns:
        name = column['name']
        if name not in normalized:
            if inserting and (column['notnull'] or column['pk']) and not is_identity(db, table, name) and column['dflt_value'] is None:
                raise LabError(f'Required field: {table}.{name} must have a value.')
            continue
        value = normalized[name]
        if value is None or (isinstance(value, str) and not value.strip()):
            if column['notnull'] or column['pk']:
                raise LabError(f'Required field: {table}.{name} must have a value.')
        if value is not None:
            normalized[name] = validate_value(db, table, name, value)
    fks = db.foreign_keys(table)
    groups = {}
    for fk in fks:
        groups.setdefault(fk['id'], []).append(fk)
    for components in groups.values():
        components.sort(key=lambda fk: fk['seq'])
        parent = components[0]['table']
        foreign_values = [normalized.get(fk['from']) for fk in components]
        # SQLite MATCH SIMPLE: if a component is NULL, a composite FK is satisfied.
        if any(value is None for value in foreign_values):
            continue
        remote_fields = []
        for fk in components:
            if fk['to']:
                remote_fields.append(fk['to'])
            else:
                key_cols = sorted((c for c in db.columns(parent) if c['pk']), key=lambda c:c['pk'])
                if len(key_cols) != len(components):
                    raise LabError(f'Foreign key schema mismatch: {table} -> {parent}.')
                remote_fields = [c['name'] for c in key_cols]
                break
        # Self-referencing insert/update can refer to its own new primary key.
        if table.casefold() == parent.casefold() and all(normalized.get(col) == val for col, val in zip(remote_fields, foreign_values)):
            continue
        predicate = ' AND '.join(f'{q(k)} IS ?' for k in remote_fields)
        found = db.connection.execute(f'SELECT 1 FROM {q(parent)} WHERE {predicate} LIMIT 1', foreign_values).fetchone()
        if found is None:
            fknames = ', '.join(fk['from'] for fk in components)
            raise LabError(f'Foreign key constraint: {table}.{fknames} = {foreign_values!r} not found in parent table {parent}.')
    return normalized

def insert_data(db: LabDatabase, table: str, values: dict) -> tuple[int, dict]:
    """Insert data using placeholders, deliberately omitting identity columns.

    An attempted supplied identity value raises rather than silently overwriting it.
    The return value contains the actual committed row retrieved from the engine.
    """
    table = identifier(table)
    db._exists(table)
    columns = db.columns(table)
    names = {c['name'].casefold(): c['name'] for c in columns}
    safe = {}
    for key, value in values.items():
        canon = names.get(identifier(key).casefold())
        if not canon:
            raise LabError(f'Unknown column: {key}')
        if is_identity(db, table, canon):
            raise LabError(f'{canon} is an identity field. Its value must be generated by the database.')
        if canon in safe:
            raise LabError(f'Duplicate column: {canon}')
        safe[canon] = value
    safe = check_row_constraints(db, table, safe, inserting=True)
    if safe:
        sql = f'INSERT INTO {q(table)} (' + ', '.join(q(k) for k in safe) + ') VALUES (' + ','.join('?' for _ in safe) + ')'
        params = list(safe.values())
    else:
        sql, params = f'INSERT INTO {q(table)} DEFAULT VALUES', []
    try:
        with db.connection:
            cursor = db.connection.execute(sql, params)
            rowid = cursor.lastrowid
            identity = db.identity_settings(table)
            if identity is not None and identity['next_value'] is not None and (identity['seed'], identity['increment']) != (1,1):
                # AFTER INSERT trigger adjusts the rowid; cursor.lastrowid is the temporary id.
                current = db.connection.execute('SELECT next_value, increment FROM __lab_identity WHERE table_name=?',(table,)).fetchone()
                rowid = current['next_value'] - current['increment']
            row = db.connection.execute(f'SELECT * FROM {q(table)} WHERE rowid=?', (rowid,)).fetchone()
        return rowid, dict(row) if row is not None else {}
    except sqlite3.Error as exc:
        raise LabError(f'Database constraint: {exc}') from exc


def get_rows(db: LabDatabase, table: str, limit: int = 500) -> tuple[list[str], list[tuple]]:
    table = identifier(table)
    db._exists(table)
    cols = [c['name'] for c in db.columns(table)]
    rows = [tuple(r) for r in db.connection.execute(f'SELECT * FROM {q(table)} LIMIT ?', (limit,))]
    return cols, rows


def editable_records(db: LabDatabase, table: str, limit: int = 500):
    """Rows with stable PK snapshots for safe edit/delete (rowid fallback for legacy tables).

    Return names, rows, locators.  A locator contains the original values to
    guard against editing a row changed since the user opened the editor.
    """
    table = identifier(table)
    db._exists(table)
    cols = db.columns(table)
    names = [c['name'] for c in cols]
    pk = [c['name'] for c in sorted(cols, key=lambda c: c['pk']) if c['pk']]
    if pk:
        records = db.connection.execute(f'SELECT * FROM {q(table)} LIMIT ?', (limit,)).fetchall()
        rows = [tuple(row) for row in records]
        locators = [{'key': {name: row[name] for name in pk},
                     'original': dict(row)} for row in records]
    else:
        try:
            records = db.connection.execute(
                f'SELECT _rowid_ AS __lab_row_locator__, * FROM {q(table)} LIMIT ?', (limit,)
            ).fetchall()
        except sqlite3.Error as exc:
            raise LabError('This table has no primary key or usable SQLite rowid; row editing is unavailable.') from exc
        rows = [tuple(row[name] for name in names) for row in records]
        locators = [{'rowid': row['__lab_row_locator__'],
                     'original': {name: row[name] for name in names}} for row in records]
    return names, rows, locators


def _row_where(db: LabDatabase, table: str, locator: dict):
    db._exists(table)
    original = locator.get('original')
    if not isinstance(original, dict) or not original:
        raise LabError('Invalid row reference. Refresh the table and try again.')
    allowed = {c['name'] for c in db.columns(table)}
    if not set(original).issubset(allowed):
        raise LabError('Table structure changed. Refresh the editor and try again.')
    key = locator.get('key')
    if isinstance(key, dict) and key:
        if not set(key).issubset(allowed):
            raise LabError('Primary key changed. Refresh the editor and try again.')
        clauses = [f'{q(name)} IS ?' for name in key]
        params = list(key.values())
    elif 'rowid' in locator:
        clauses = ['_rowid_=?']
        params = [locator['rowid']]
    else:
        raise LabError('No usable row identifier. Refresh the editor.')
    # Compare original values too, to prevent silently overwriting another edit.
    clauses.extend(f'{q(name)} IS ?' for name in original)
    params.extend(original.values())
    return ' AND '.join(clauses), params


def update_record(db: LabDatabase, table: str, locator: dict, values: dict) -> None:
    """Update exactly one record with parameters and referential-integrity checks."""
    table = identifier(table)
    where, key_params = _row_where(db, table, locator)
    column_names = {c['name'].casefold(): c['name'] for c in db.columns(table)}
    change = {}
    for name, value in values.items():
        actual = column_names.get(identifier(name).casefold())
        if actual is None:
            raise LabError(f'Unknown column: {name}')
        if is_identity(db, table, actual):
            raise LabError(f'{actual} is database-generated and cannot be changed manually.')
        change[actual] = value
    if not change:
        raise LabError('No fields selected to update.')
    # Validate the final record, not just the changed column, for FK combinations.
    final_values = {**locator['original'], **change}
    checked = check_row_constraints(db, table, final_values)
    change = {name:checked[name] for name in change}
    stmt = f'UPDATE {q(table)} SET ' + ', '.join(f'{q(k)}=?' for k in change)
    try:
        with db.connection:
            cursor = db.connection.execute(stmt + ' WHERE ' + where,
                                           list(change.values()) + key_params)
            if cursor.rowcount != 1:
                raise LabError('This record was changed or deleted. Refresh before editing.')
    except sqlite3.Error as exc:
        raise LabError(f'Update rejected by database constraints: {exc}') from exc


def delete_record(db: LabDatabase, table: str, locator: dict) -> None:
    """Delete one user-confirmed record; database FKs can veto the operation."""
    table = identifier(table)
    where, params = _row_where(db, table, locator)
    try:
        with db.connection:
            cursor = db.connection.execute(f'DELETE FROM {q(table)} WHERE {where}', params)
            if cursor.rowcount != 1:
                raise LabError('This record was changed or deleted. Refresh before deleting.')
    except sqlite3.Error as exc:
        raise LabError(f'Delete rejected by referential integrity or other constraints: {exc}') from exc
