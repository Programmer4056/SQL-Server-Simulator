"""Generate executable T-SQL for the *supported* educational table model.

This produces a .sql script, never an SQL Server .bak backup.  SSMS-style
ordering is intentional: database, tables, data, foreign keys.  Unsupported
schema features are rejected rather than being silently lost.  Microsoft SQL
Server itself is required for final integration testing.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import math
import re
from collections import defaultdict

from core import LabDatabase, LabError, identifier
from version_info import APP_VERSION

TARGET_VERSIONS = ('2012', '2014', '2016', '2017', '2019', '2022', '2025')
EXPORT_MODES = ('schema', 'data', 'both')


def brackets(name: str) -> str:
    name = identifier(name)
    if len(name) > 128:
        raise LabError(f'SQL Server identifiers must be at most 128 characters: {name[:40]}.')
    return '[' + name.replace(']', ']]') + ']'


def fq(name: str) -> str:
    return '[dbo].' + brackets(name)


def sqltype(logical: str) -> str:
    typ = logical.strip().upper()
    aliases = {
        'INTEGER': 'INT', 'TEXT': 'NVARCHAR(MAX)', 'BOOLEAN': 'BIT',
        'BLOB': 'VARBINARY(MAX)', 'NUMERIC': 'DECIMAL(18,4)',
        'DATE': 'DATE', 'DATETIME': 'DATETIME2', 'REAL': 'REAL',
        'DOUBLE': 'FLOAT', 'TINYINT': 'TINYINT', 'INT': 'INT',
        'BIGINT': 'BIGINT', 'SMALLINT': 'SMALLINT', 'FLOAT': 'FLOAT',
        'BIT': 'BIT', 'UNIQUEIDENTIFIER': 'UNIQUEIDENTIFIER',
        'MONEY': 'MONEY', 'SMALLMONEY': 'SMALLMONEY',
        'SMALLDATETIME': 'SMALLDATETIME', 'DATETIME2': 'DATETIME2',
        'TIME': 'TIME', 'CHAR': 'CHAR(1)', 'NCHAR': 'NCHAR(1)',
        'VARCHAR': 'VARCHAR(MAX)', 'NVARCHAR': 'NVARCHAR(MAX)',
    }
    if typ in aliases:
        return aliases[typ]
    fixed = re.fullmatch(r'(NVARCHAR|NCHAR|VARCHAR|CHAR|VARBINARY|BINARY)\((MAX|\d+)\)', typ)
    if fixed:
        kind, size = fixed.groups()
        if size == 'MAX' and kind not in ('NVARCHAR', 'VARCHAR', 'VARBINARY'):
            raise LabError(f'{kind}(MAX) is invalid in SQL Server; use a supported size.')
        limit = 4000 if kind in ('NVARCHAR', 'NCHAR') else 8000
        if size != 'MAX' and not 1 <= int(size) <= limit:
            raise LabError(f'Invalid SQL Server size for {typ}.')
        return typ
    numeric = re.fullmatch(r'(DECIMAL|NUMERIC)\((\d+)(?:,\s*(\d+))?\)', typ)
    if numeric:
        precision, scale = int(numeric.group(2)), int(numeric.group(3) or 0)
        if not (1 <= precision <= 38 and 0 <= scale <= precision):
            raise LabError(f'Invalid SQL Server precision/scale for {typ}.')
        return typ
    tm = re.fullmatch(r'(DATETIME2|TIME)\((\d+)\)', typ)
    if tm and 0 <= int(tm.group(2)) <= 7:
        return typ
    raise LabError(f'Cannot safely export data type {typ!r} to SQL Server.')


def literal(value) -> str:
    """T-SQL constants: Unicode N'..', binary 0x.., NULL, finite numbers."""
    if value is None:
        return 'NULL'
    if isinstance(value, (bytes, bytearray, memoryview)):
        return '0x' + bytes(value).hex().upper()
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise LabError('Cannot export NaN or Infinity as T-SQL data.')
        return repr(value)
    return "N'" + str(value).replace("'", "''") + "'"


def _sql_default(raw, declared_type: str) -> str | None:
    """No silent loss of DEFAULT expressions: only known safe literals are mapped."""
    if raw is None:
        return None
    raw = str(raw).strip()
    if raw.upper() == 'NULL':
        return 'NULL'
    if re.fullmatch(r'[+-]?\d+(?:\.\d+)?', raw):
        return raw
    if re.fullmatch(r"'(?:''|[^'])*'", raw, re.S):
        # TEXT literal from SQLite -> Unicode literal for NVARCHAR in SQL Server.
        return 'N' + raw if sqltype(declared_type).startswith(('NVARCHAR', 'NCHAR')) else raw
    raise LabError(f'Unsupported SQLite DEFAULT expression {raw!r}; edit its T-SQL mapping before exporting.')


def _fk_groups(db: LabDatabase, table: str) -> list[list[dict]]:
    groups = defaultdict(list)
    for row in db.foreign_keys(table):
        groups[int(row['id'])].append(row)
    return [sorted(groups[i], key=lambda r: int(r['seq'])) for i in sorted(groups)]


def _sql_fk_action(action: str) -> str:
    action = action.upper().strip()
    if action == 'RESTRICT':
        return 'NO ACTION'
    if action in ('NO ACTION', 'CASCADE', 'SET NULL', 'SET DEFAULT'):
        return action
    raise LabError(f'Unsupported SQL Server referential action: {action}')


def _indexes(db: LabDatabase, table: str):
    """Keep UNIQUE of junction tables and simple user indexes; reject expressions."""
    found = []
    for entry in db.connection.execute(f'PRAGMA index_list("{table}")'):
        origin = entry['origin']
        if origin == 'pk':
            continue
        name = entry['name']
        if entry['partial']:
            raise LabError(f'Partial index {name} cannot be safely exported to T-SQL.')
        quoted_name = '"' + name.replace('"', '""') + '"'
        fields = [dict(row) for row in db.connection.execute(f'PRAGMA index_info({quoted_name})')]
        if not fields or any(not col['name'] for col in fields):
            raise LabError(f'Expression index {name} cannot be safely exported to T-SQL.')
        cols = [c['name'] for c in sorted(fields, key=lambda r:r['seqno'])]
        found.append({'origin':origin, 'name':name, 'unique':bool(entry['unique']), 'columns':cols})
    return found


def _data_order(db: LabDatabase, selected: set[str]) -> list[str]:
    """Parents before children for Data Only when existing FK constraints are active."""
    parents = {name:set() for name in selected}
    for child in selected:
        for group in _fk_groups(db, child):
            parent = group[0]['table']
            if parent in selected and parent != child:
                parents[child].add(parent)
    result=[]
    while parents:
        available = sorted((x for x, deps in parents.items() if not deps), key=str.casefold)
        if not available:
            raise LabError('Data-only export contains a circular FK dependency. Use Schema and Data, which adds FK constraints after records.')
        result.extend(available)
        for name in available:
            del parents[name]
        for deps in parents.values():
            deps.difference_update(available)
    return result


def _check_source_schema(db: LabDatabase, table: str):
    """Reject unsupported hand-written CHECKs; generated NVARCHAR length checks are native on SQL Server."""
    row = db.connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not row:
        raise LabError(f'Table {table} no longer exists.')
    source = row[0] or ''
    generated = r'CHECK\s*\(\s*"[^"]+"\s+IS\s+NULL\s+OR\s+length\("[^"]+"\)\s*<=\s*\d+\s*\)'
    stripped = re.sub(generated, '', source, flags=re.I)
    if re.search(r'\b(CHECK|GENERATED|COLLATE|WITHOUT\s+ROWID)\b', stripped, re.I):
        raise LabError(f'Table {table} has a schema feature that requires manual T-SQL conversion (CHECK, GENERATED or COLLATE).')
    # Do not omit user triggers as if they never existed.
    for item in db.connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)):
        if not item[0].startswith('__lab_identity_trigger_'):
            raise LabError(f'Table {table} has user-defined SQLite triggers that cannot be exported unchanged to SQL Server.')


def make_script(db: LabDatabase, tables: list[str], mode: str = 'both',
                version: str = '2022', database_name: str | None = None) -> str:
    if mode not in EXPORT_MODES:
        raise LabError('Choose Schema, Data, or Schema and Data.')
    if version not in TARGET_VERSIONS:
        raise LabError('Unsupported target SQL Server version.')
    known = set(db.tables())
    if not tables or len(tables) != len(set(tables)) or any(t not in known for t in tables):
        raise LabError('Select one or more valid, unique tables.')
    if database_name is not None:
        brackets(database_name)
    chosen = set(tables)
    ordered = sorted(chosen, key=str.casefold)
    for table in ordered:
        brackets(table)
        _check_source_schema(db, table)
    generated = datetime.now().strftime('%Y-%m-%d %H:%M')
    out = [
        f'-- SQL Server Simulator v{APP_VERSION} | Designed and developed by Ali Sayyadi',
        f'-- Generated: {generated} | Target SQL Server: {version} | Mode: {mode}',
        '-- Executable T-SQL for the supported table/column/constraint subset.',
        '-- This is a SQL SCRIPT, not a native .bak backup and not a bit-for-bit SSMS export.',
        '-- Review and test against the chosen SQL Server version before deployment.',
        '-- Database users, permissions, views, stored procedures and functions are not included.',
        'SET ANSI_NULLS ON;', 'GO', 'SET QUOTED_IDENTIFIER ON;', 'GO',
        'SET ANSI_PADDING ON;', 'GO', 'SET NOCOUNT ON;', 'GO', ''
    ]
    if database_name and mode != 'data':
        out.extend([f'IF DB_ID({literal(database_name)}) IS NULL',
                    f"    EXEC(N'CREATE DATABASE {brackets(database_name)}');", 'GO',
                    f'USE {brackets(database_name)};', 'GO', ''])
    elif database_name:
        out.extend([f'USE {brackets(database_name)};', 'GO', ''])

    if mode in ('schema', 'both'):
        for table in ordered:
            cols = db.columns(table)
            keys = sorted((c for c in cols if c['pk']), key=lambda c:int(c['pk']))
            if not keys:
                raise LabError(f'Table {table} has no primary key. This exporter requires a primary key.')
            identity = db.identity_settings(table)
            definitions=[]
            for col in cols:
                colname = col['name']
                typ = sqltype(db.logical_type(table,colname))
                definition = '    '+brackets(colname)+' '+typ
                if identity and identity['column_name'] == colname:
                    if typ not in ('TINYINT','SMALLINT','INT','BIGINT'):
                        raise LabError(f'IDENTITY column {table}.{colname} is not an SQL Server integer type.')
                    definition += f" IDENTITY({int(identity['seed'])},{int(identity['increment'])})"
                definition += ' NOT NULL' if col['notnull'] or col['pk'] else ' NULL'
                default = _sql_default(col['dflt_value'], typ)
                if default is not None and not (identity and identity['column_name']==colname):
                    definition += ' DEFAULT '+default
                definitions.append(definition)
            by_name={c['name']:c for c in cols}
            for key in keys:
                if sqltype(db.logical_type(table,key['name'])).endswith('(MAX)'):
                    raise LabError(f'SQL Server cannot create a primary key on MAX column {table}.{key["name"]}.')
            pk_name = brackets('PK_'+table if len('PK_'+table)<=128 else 'PK_'+table[:125])
            pkcols = ', '.join(brackets(c['name']) for c in keys)
            definitions.append(f'    CONSTRAINT {pk_name} PRIMARY KEY ({pkcols})')
            for i, item in enumerate(_indexes(db,table),1):
                if item['origin']=='u':
                    for col_name in item['columns']:
                        if sqltype(db.logical_type(table,col_name)).endswith('(MAX)'):
                            raise LabError(f'SQL Server cannot create UNIQUE on MAX column {table}.{col_name}.')
                        if not (by_name[col_name]['notnull'] or by_name[col_name]['pk']):
                            raise LabError(f'UNIQUE on nullable column {table}.{col_name} has different SQLite/SQL Server semantics. Make it NOT NULL before export.')
                    c_name=brackets(f'UQ_{table[:100]}_{i}')
                    c_cols=', '.join(brackets(c) for c in item['columns'])
                    definitions.append(f'    CONSTRAINT {c_name} UNIQUE ({c_cols})')
            out.extend([f'-- Table: {table}',
                        f'CREATE TABLE {fq(table)} (\n'+',\n'.join(definitions)+'\n);',
                        'GO', ''])
        for table in ordered:
            for item in _indexes(db,table):
                if item['origin']!='c':
                    continue
                for col_name in item['columns']:
                    if sqltype(db.logical_type(table,col_name)).endswith('(MAX)'):
                        raise LabError(f'SQL Server cannot index MAX column {table}.{col_name}.')
                index_kind = 'UNIQUE ' if item['unique'] else ''
                columns = ', '.join(brackets(col) for col in item['columns'])
                out.extend([f'CREATE {index_kind}INDEX {brackets(item["name"])} ON {fq(table)} ({columns});', 'GO', ''])

    if mode in ('data','both'):
        insert_order = _data_order(db,chosen) if mode=='data' else ordered
        for table in insert_order:
            cols = [c['name'] for c in db.columns(table)]
            identity=db.identity_settings(table)
            count=0
            # Stable PK ordering produces reproducible data sequences for teaching.
            keys = [c['name'] for c in sorted(db.columns(table),key=lambda c:c['pk']) if c['pk']]
            order = (' ORDER BY '+', '.join('"'+c+'"' for c in keys)) if keys else ''
            cursor=db.connection.execute('SELECT * FROM "'+table+'"'+order)
            for row in cursor:
                if count==0 and identity:
                    out.append(f'SET IDENTITY_INSERT {fq(table)} ON;')
                out.append(f'INSERT INTO {fq(table)} ('+', '.join(brackets(c) for c in cols)+') VALUES ('+
                           ', '.join(literal(v) for v in row)+');')
                count+=1
            if count and identity:
                out.append(f'SET IDENTITY_INSERT {fq(table)} OFF;')
            out.extend([f'-- {table}: {count} row(s) scripted', 'GO', ''])

    if mode in ('schema','both'):
        # All tables and data exist before CHECKed foreign key creation.
        for child in ordered:
            for ix,group in enumerate(_fk_groups(db,child),1):
                parent=group[0]['table']
                if parent not in chosen:
                    out.append(f'-- FK from {child} to {parent} omitted: parent table was not selected. Select the parent to restore this FK.')
                    continue
                for fk_row in group:
                    local_type=sqltype(db.logical_type(child, fk_row['from']))
                    remote_type=sqltype(db.logical_type(parent, fk_row['to']))
                    if local_type != remote_type:
                        raise LabError(f'FK {child}.{fk_row["from"]} ({local_type}) and {parent}.{fk_row["to"]} ({remote_type}) have incompatible SQL Server types.')
                local=', '.join(brackets(row['from']) for row in group)
                remote=', '.join(brackets(row['to']) for row in group)
                constraint=brackets(f'FK_{child[:45]}_{parent[:45]}_{ix}')
                action_delete=_sql_fk_action(group[0]['on_delete'])
                action_update=_sql_fk_action(group[0]['on_update'])
                fk_sql=(f'ALTER TABLE {fq(child)} WITH CHECK ADD CONSTRAINT {constraint} '
                        f'FOREIGN KEY ({local}) REFERENCES {fq(parent)} ({remote})')
                if action_delete!='NO ACTION':
                    fk_sql += f' ON DELETE {action_delete}'
                if action_update!='NO ACTION':
                    fk_sql += f' ON UPDATE {action_update}'
                out.extend([fk_sql+';', 'GO',
                            f'ALTER TABLE {fq(child)} CHECK CONSTRAINT {constraint};','GO',''])

    out.append('-- End of generated T-SQL script.')
    return '\n'.join(out) + '\n'


def export_script(db:LabDatabase, target:str|Path, tables:list[str], mode='both',
                  version='2022', database_name=None) -> None:
    script=make_script(db,tables,mode,version,database_name)
    dest=Path(target)
    if dest.suffix.lower()!='.sql':
        raise LabError('Export file must have the .sql extension.')
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(script,encoding='utf-8-sig')
