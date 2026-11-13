"""SQL Server Simulator - educational SQLite engine.
Developer: Ali Sayyadi. This is not Microsoft SQL Server.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Iterable


class LabError(ValueError):
    """A human-readable design validation failure."""


IDENT = re.compile(r"^[^\W\d]\w*$", re.UNICODE)
TYPE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:\((?:\d+(?:,\s*\d+)?|MAX)\))?$", re.I)


def identifier(value: str) -> str:
    value = (value or "").strip()
    if not IDENT.fullmatch(value) or value.lower().startswith(('sqlite_', '__lab_')):
        raise LabError(f"Invalid identifier: {value!r}. Use letters, digits or underscores; do not start with a digit.")
    return value


def q(value: str) -> str:
    return '"' + identifier(value).replace('"', '""') + '"'


def storage_type(value: str, identity: bool = False) -> str:
    """Preserve SQL Server-oriented logical types in metadata; use safe SQLite storage."""
    typ = col_type(value)
    if identity:
        return 'INTEGER'  # SQLite rowid alias, independent of the displayed SQL type.
    if typ.endswith('(MAX)'):
        if typ.startswith(('NVARCHAR', 'VARCHAR', 'NCHAR', 'CHAR')):
            return 'TEXT'
        if typ.startswith(('VARBINARY', 'BINARY')):
            return 'BLOB'
    if typ in ('BIT', 'BOOLEAN', 'TINYINT'):
        return 'INTEGER'
    if typ in ('UNIQUEIDENTIFIER', 'DATE', 'DATETIME', 'SMALLDATETIME', 'DATETIME2', 'TIME') or typ.startswith(('DATETIME2(', 'TIME(')):
        return 'TEXT'
    if typ in ('MONEY', 'SMALLMONEY'):
        return 'NUMERIC'
    if typ in ('VARBINARY', 'BINARY') or typ.startswith(('VARBINARY(', 'BINARY(')):
        return 'BLOB'
    if typ in ('REAL', 'FLOAT'):
        return 'REAL'
    return typ


def col_type(value: str) -> str:
    value = (value or "").strip().upper()
    if not TYPE.fullmatch(value):
        raise LabError(f"Invalid data type: {value!r}")
    precision = re.fullmatch(r'(?:DECIMAL|NUMERIC)\((\d+)(?:,\s*(\d+))?\)',value)
    if precision:
        p,scale=int(precision.group(1)),int(precision.group(2) or 0)
        if p<1 or p>38 or scale>p:
            raise LabError('SQL Server DECIMAL/NUMERIC precision must be 1..38 and scale 0..precision.')
    sized = re.fullmatch(r'(N?VARCHAR|N?CHAR|VARBINARY|BINARY)\((\d+)\)',value)
    if sized:
        limit=4000 if sized.group(1) in ('NVARCHAR','NCHAR') else 8000
        if not 1<=int(sized.group(2))<=limit:
            raise LabError(f'{sized.group(1)} length must be between 1 and {limit}.')
    return value


@dataclass(frozen=True)
class Column:
    name: str
    type: str = 'TEXT'
    primary: bool = False
    required: bool = False
    auto: bool = False
    seed: int = 1
    increment: int = 1


class LabDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute('PRAGMA foreign_keys=ON')
        self._metadata()

    def close(self):
        self.connection.close()

    def _metadata(self):
        self.connection.execute('''CREATE TABLE IF NOT EXISTS __lab_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL, parent TEXT NOT NULL, child TEXT NOT NULL,
            fk_column TEXT NOT NULL, bridge TEXT NOT NULL DEFAULT ''
        )''')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS __lab_positions (
            table_name TEXT PRIMARY KEY, x INTEGER NOT NULL, y INTEGER NOT NULL
        )''')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS __lab_identity (
            table_name TEXT PRIMARY KEY, column_name TEXT NOT NULL,
            seed INTEGER NOT NULL, increment INTEGER NOT NULL, next_value INTEGER NOT NULL
        )''')
        self.connection.execute('''CREATE TABLE IF NOT EXISTS __lab_column_types (
            table_name TEXT NOT NULL, column_name TEXT NOT NULL, sql_type TEXT NOT NULL,
            PRIMARY KEY(table_name,column_name)
        )''')
        self.connection.commit()

    def logical_type(self, table: str, column: str) -> str:
        row = self.connection.execute(
            'SELECT sql_type FROM __lab_column_types WHERE table_name=? AND column_name=?',
            (table, column)).fetchone()
        if row:
            return row[0]
        return next((c['type'] for c in self.columns(table) if c['name']==column), 'TEXT')

    def identity_settings(self, table: str):
        row = self.connection.execute('SELECT * FROM __lab_identity WHERE table_name=?',(table,)).fetchone()
        if row:
            return dict(row)
        # Legacy v0.2 tables have real SQLite-generated identity, default (1,1).
        from model_ext import is_identity
        for c in self.columns(table):
            if is_identity(self,table,c['name']):
                return {'table_name':table,'column_name':c['name'],'seed':1,'increment':1,'next_value':None}
        return None

    def _install_identity_trigger(self, table: str):
        """Database-owned trigger for non-default IDENTITY seed/increment."""
        row = self.connection.execute('SELECT * FROM __lab_identity WHERE table_name=?',(table,)).fetchone()
        if not row or (row['seed']==1 and row['increment']==1):
            return
        column = row['column_name']
        trigger = '"__lab_identity_trigger_'+table+'"'
        # SQLite triggers are run in the same transaction as the INSERT.
        self.connection.execute(f'''CREATE TRIGGER {trigger} AFTER INSERT ON {q(table)} BEGIN
            UPDATE {q(table)} SET {q(column)} =
                (SELECT next_value FROM __lab_identity WHERE table_name='{table}')
                WHERE rowid = NEW.rowid;
            UPDATE __lab_identity SET next_value=next_value+increment WHERE table_name='{table}';
        END''')

    def tables(self) -> list[str]:
        return [r[0] for r in self.connection.execute("""SELECT name FROM sqlite_master
          WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '__lab_%'
          ORDER BY name COLLATE NOCASE""")]

    def columns(self, table: str) -> list[dict]:
        identifier(table)
        return [dict(r) for r in self.connection.execute(f'PRAGMA table_info({q(table)})')]

    def foreign_keys(self, table: str) -> list[dict]:
        return [dict(r) for r in self.connection.execute(f'PRAGMA foreign_key_list({q(table)})')]

    def _exists(self, table: str):
        if table not in self.tables():
            raise LabError(f'Table {table!r} does not exist.')

    def primary_key(self, table: str) -> dict:
        self._exists(table)
        keys = sorted((c for c in self.columns(table) if c['pk']), key=lambda c: c['pk'])
        if len(keys) != 1:
            raise LabError(f'Table {table!r} must have exactly one primary key column for this relationship.')
        return keys[0]

    def create_table(self, name: str, cols: Iterable[Column]):
        name = identifier(name)
        cols = list(cols)
        if not cols:
            raise LabError('At least one column is required.')
        names = [identifier(c.name).lower() for c in cols]
        if len(set(names)) != len(names):
            raise LabError('Duplicate column names are not allowed.')
        keys = [c for c in cols if c.primary]
        if not keys:
            raise LabError('Choose at least one primary key column.')
        autos = [c for c in cols if c.auto]
        integer_types = {'INTEGER','INT','BIGINT','SMALLINT','TINYINT'}
        if len(autos)>1 or any(not c.primary or col_type(c.type) not in integer_types for c in autos):
            raise LabError('Identity requires one integer primary key (INT, BIGINT, SMALLINT or TINYINT).')
        if autos and len(keys)>1:
            raise LabError('Identity is incompatible with a composite primary key.')
        if autos and (autos[0].increment==0 or abs(autos[0].seed)>10**12 or abs(autos[0].increment)>10**9):
            raise LabError('Identity increment must be non-zero; seed/increment must fit the simulator safety limits.')
        sqlcols = []
        for c in cols:
            typ = col_type(c.type)
            definition = f'{q(c.name)} {storage_type(typ,c.auto)}'
            if c.auto:
                definition += ' PRIMARY KEY AUTOINCREMENT'
            elif len(keys)==1 and c.primary:
                definition += ' PRIMARY KEY'
                if storage_type(typ)!='INTEGER':
                    definition += ' NOT NULL'
            elif c.primary or c.required:
                definition += ' NOT NULL'
            # SQLite does not enforce length declared in VARCHAR(n)/NVARCHAR(n).
            match = re.fullmatch(r'(N?VARCHAR|N?CHAR)\((\d+)\)', typ)
            if match:
                n=int(match.group(2))
                if n<1 or n>4000:
                    raise LabError('String length must be 1..4000. Use NVARCHAR(MAX) for longer text.')
                definition += f' CHECK ({q(c.name)} IS NULL OR length({q(c.name)})<={n})'
            sqlcols.append(definition)
        if len(keys)>1:
            sqlcols.append('PRIMARY KEY ('+', '.join(q(c.name) for c in keys)+')')
        try:
            with self.connection:
                self.connection.execute(f'CREATE TABLE {q(name)} ('+', '.join(sqlcols)+')')
                for c in cols:
                    self.connection.execute('INSERT INTO __lab_column_types VALUES(?,?,?)',
                                            (name,c.name,col_type(c.type)))
                if autos:
                    a=autos[0]
                    self.connection.execute('INSERT INTO __lab_identity VALUES(?,?,?,?,?)',
                                            (name,a.name,int(a.seed),int(a.increment),int(a.seed)))
                    self._install_identity_trigger(name)
        except sqlite3.Error as exc:
            raise LabError(f'Table creation failed: {exc}') from exc

    def _add_fk_to_existing(self, parent: str, child: str, child_col: str,
                            *, required: bool, one_to_one: bool):
        """Rebuild a child table atomically, preserving its records when safe.

        Refuse custom indexes/triggers and incoming foreign keys instead of risking data loss.
        Validate existing rows against the new FK before committing the migration.
        """
        self._exists(parent)
        self._exists(child)
        if parent == child:
            raise LabError('Self-referencing relationships are not supported by the initial visual wizard.')
        pk = self.primary_key(parent)
        child_col = identifier(child_col)
        entries = self.columns(child)
        sql_row = self.connection.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name=?', (child,)).fetchone()
        ddl = (sql_row[0] if sql_row else '') or ''
        # Preserve our own generated NVARCHAR/VARCHAR length checks during the rebuild.
        own_check = r'CHECK\s*\(\s*"[A-Za-z_][A-Za-z0-9_]*"\s+IS\s+NULL\s+OR\s+length\("[A-Za-z_][A-Za-z0-9_]*"\)\s*<=\s*\d+\s*\)'
        remainder = re.sub(own_check, '', ddl, flags=re.I)
        if re.search(r'\b(CHECK|UNIQUE|GENERATED|COLLATE|WITHOUT\s+ROWID)\b', remainder, re.I):
            raise LabError('Advanced table constraints found; visual FK migration is not supported for this schema.')
        associated = self.connection.execute("""SELECT name FROM sqlite_master
            WHERE tbl_name=? AND type IN ('trigger','index') AND sql IS NOT NULL""", (child,)).fetchall()
        if any(not r['name'].startswith('__lab_identity_trigger_') for r in associated):
            raise LabError('Custom indexes or triggers exist. Automatic table rebuild is disabled to avoid data loss.')
        populated=bool(self.connection.execute(f'SELECT EXISTS(SELECT 1 FROM {q(child)} LIMIT 1)').fetchone()[0])
        # Dropping a table referenced by another table can cause destructive cascades.
        incoming=[other for other in self.tables() if other!=child
                  and any(fk['table'].casefold()==child.casefold() for fk in self.foreign_keys(other))]
        if any(self.connection.execute(f'SELECT EXISTS(SELECT 1 FROM {q(other)} LIMIT 1)').fetchone()[0]
               for other in incoming):
            raise LabError('This child table is already referenced by populated tables; automatic FK migration is disabled for safety.')
        existing = {c['name'].lower(): c for c in entries}
        if one_to_one:
            cpk = self.primary_key(child)
            if cpk['name'].lower() != child_col.lower():
                raise LabError('For shared-key 1:1, the child FK must also be its primary key.')
            if 'AUTOINCREMENT' in ddl.upper():
                raise LabError('For shared-key 1:1, define the child primary key WITHOUT auto increment.')
            if self.logical_type(child,cpk['name']).replace('INTEGER','INT') != self.logical_type(parent,pk['name']).replace('INTEGER','INT'):
                raise LabError('The parent and child primary key types must match.')
        elif child_col.lower() in existing and self.logical_type(child,existing[child_col.lower()]['name']).replace('INTEGER','INT') != self.logical_type(parent,pk['name']).replace('INTEGER','INT'):
            raise LabError('The foreign key data type must match the parent primary key type.')
        if populated and not one_to_one and child_col.lower() not in existing and required:
            raise LabError('Existing child rows cannot be assigned a required new FK automatically. Add a nullable FK, or populate matching FK values before making the relationship required.')
        if any(fk['from'].lower() == child_col.lower() for fk in self.foreign_keys(child)):
            raise LabError('This column is already used as a foreign key.')

        # Preserve previously defined foreign keys through the rebuild.
        old_fk = self.foreign_keys(child)
        groups: dict[int, list[dict]] = {}
        for f in old_fk:
            groups.setdefault(f['id'], []).append(f)
        constraints = []
        for rows in groups.values():
            rows.sort(key=lambda r: r['seq'])
            if any(r['on_update'] != 'NO ACTION' or r['on_delete'] != 'NO ACTION' for r in rows):
                raise LabError('Relationships with custom referential actions cannot be reconstructed in this version.')
            constraints.append('FOREIGN KEY (' + ', '.join(q(r['from']) for r in rows) +
                               ') REFERENCES ' + q(rows[0]['table']) + ' (' +
                               ', '.join(q(r['to']) for r in rows) + ')')
        definitions = []
        all_cols = list(entries)
        if not one_to_one and child_col.lower() not in existing:
            all_cols.append({'name': child_col, 'type': pk['type'], 'notnull': int(required),
                             'dflt_value': None, 'pk': 0})
        pks = sorted((c for c in all_cols if c['pk']), key=lambda c: c['pk'])
        ai = 'AUTOINCREMENT' in ddl.upper() and len(pks) == 1
        for c in all_cols:
            typ = col_type(c['type'] or 'TEXT')
            definition = f"{q(c['name'])} {typ}"
            if len(pks) == 1 and c['pk']:
                definition += ' PRIMARY KEY'
                if ai:
                    definition += ' AUTOINCREMENT'
                elif typ != 'INTEGER':
                    definition += ' NOT NULL'
            elif c['notnull'] or c['pk'] or (c['name'].lower() == child_col.lower() and required):
                definition += ' NOT NULL'
            if c['dflt_value'] is not None:
                definition += ' DEFAULT ' + str(c['dflt_value'])
            logical = self.logical_type(child,c['name'])
            match = re.fullmatch(r'(N?VARCHAR|N?CHAR)\((\d+)\)', logical)
            if match:
                definition += f' CHECK ({q(c["name"])} IS NULL OR length({q(c["name"])})<={int(match.group(2))})'
            definitions.append(definition)
        if len(pks) > 1:
            definitions.append('PRIMARY KEY (' + ', '.join(q(c['name']) for c in pks) + ')')
        constraints.append(f'FOREIGN KEY ({q(child_col)}) REFERENCES {q(parent)} ({q(pk["name"])})')
        defs = ', '.join(definitions + constraints)
        temp = '__lab_temp_rebuild'
        if self.connection.execute("SELECT 1 FROM sqlite_master WHERE name=?",(temp,)).fetchone():
            raise LabError('An internal temporary table is present; migration cancelled safely.')
        sequence=None
        if ai:
            row=self.connection.execute('SELECT seq FROM sqlite_sequence WHERE name=?',(child,)).fetchone()
            if row:sequence=row[0]
        try:
            with self.connection:
                self.connection.execute(f'CREATE TABLE "{temp}" ({defs})')
                # Preserve all original rows and column values. New nullable FKs remain NULL.
                colnames=', '.join(q(c['name']) for c in entries)
                self.connection.execute(f'INSERT INTO "{temp}" ({colnames}) SELECT {colnames} FROM {q(child)}')
                self.connection.execute(f'DROP TABLE {q(child)}')
                self.connection.execute(f'ALTER TABLE "{temp}" RENAME TO {q(child)}')
                if ai and sequence is not None:
                    # Preserve the high-water mark even when earlier IDs were deleted.
                    self.connection.execute('UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name=?',(sequence,child))
                self._install_identity_trigger(child)
                if self.connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
                    raise LabError('Existing rows violate foreign keys. Nothing has been changed.')
        except (sqlite3.Error,LabError) as exc:
            raise LabError(f'Failed to create a foreign key constraint safely: {exc}') from exc

    def validate_field_link(self, parent: str, parent_field: str, child: str,
                            child_field: str, kind: str = '1:N', required: bool = False):
        """Validate a visual *column-to-column* link before changing anything.

        The teaching designer intentionally references a single-column PRIMARY KEY,
        rather than claiming that arbitrary matching field names make a relationship.
        Existing orphan values and incompatible types are rejected early.
        """
        parent, child = identifier(parent), identifier(child)
        parent_field, child_field = identifier(parent_field), identifier(child_field)
        self._exists(parent); self._exists(child)
        if kind not in ('1:N', '1:1', 'SELF', 'N:M'):
            raise LabError('Unsupported relationship type.')
        pk = self.primary_key(parent)
        if pk['name'].casefold() != parent_field.casefold():
            raise LabError(f'The referenced field must be the primary key: {parent}.{pk["name"]}.')
        children = {c['name'].casefold(): c for c in self.columns(child)}
        if kind == 'N:M':
            if parent == child:
                raise LabError('Use a self-referencing relationship for one table.')
            cp = self.primary_key(child)
            if child_field.casefold() != cp['name'].casefold():
                raise LabError(f'For N:M, select the primary key on both sides ({child}.{cp["name"]}).')
            return
        if (parent == child) != (kind == 'SELF'):
            raise LabError('Use Self-referencing (SELF) only when both fields belong to the same table.')
        if kind == '1:1':
            cp = self.primary_key(child)
            if child_field.casefold() != cp['name'].casefold():
                raise LabError('Shared-key 1:1 requires the child field to be its own primary key.')
            if self.identity_settings(child) and self.identity_settings(child)['column_name'].casefold() == child_field.casefold():
                raise LabError('Shared-key 1:1 child PK/FK cannot auto-generate its identity. Turn off Identity in Design Table.')
        else:
            if child_field.casefold() == parent_field.casefold() and parent == child:
                raise LabError('A hierarchy needs a separate FK field, not a PK referencing itself.')
            if child_field.casefold() in {c['name'].casefold() for c in self.columns(child) if c['pk']}:
                raise LabError('A 1:N / self-reference FK cannot be the child primary key. Use 1:1 for shared keys.')
        existing = children.get(child_field.casefold())
        if existing:
            pt = self.logical_type(parent, pk['name']).replace('INTEGER','INT')
            ct = self.logical_type(child, existing['name']).replace('INTEGER','INT')
            if pt != ct:
                raise LabError(f'Data type mismatch: {parent}.{pk["name"]} ({pt}) and {child}.{existing["name"]} ({ct}).')
            if any(f['from'].casefold() == child_field.casefold() for f in self.foreign_keys(child)):
                raise LabError(f'{child}.{child_field} is already used as a foreign key.')
            # NULL FKs are legal when optional. A required FK must be fully populated.
            if required and self.connection.execute(
                f'SELECT 1 FROM {q(child)} WHERE {q(child_field)} IS NULL LIMIT 1').fetchone():
                raise LabError('Required foreign key contains NULL. Fill or correct existing rows before connecting.')
            if self.connection.execute(
                f"""SELECT 1 FROM {q(child)} AS c WHERE c.{q(child_field)} IS NOT NULL
                    AND NOT EXISTS (SELECT 1 FROM {q(parent)} AS p
                                    WHERE p.{q(pk['name'])}=c.{q(child_field)}) LIMIT 1""").fetchone():
                raise LabError('Referential integrity violation: a child FK value has no matching parent primary key.')
        elif required and self.connection.execute(f'SELECT 1 FROM {q(child)} LIMIT 1').fetchone():
            raise LabError('Cannot add a new required FK to a populated table. Select optional or fill a matching field first.')

    def connect_fields(self, parent: str, parent_field: str, child: str, child_field: str,
                       kind: str = '1:N', required: bool = False,
                       bridge: str | None = None, strategy: str = 'composite'):
        """Persist a validated visual link as a REAL database constraint."""
        self.validate_field_link(parent,parent_field,child,child_field,kind,required)
        if kind == '1:1':
            return self.one_to_one(parent,child)
        if kind == 'SELF':
            return self.self_reference(parent,child_field,required)
        if kind == 'N:M':
            return self.many_to_many(parent,child,bridge or f'{parent}_{child}_Link',strategy)
        return self.one_to_many(parent,child,child_field,required)

    def one_to_many(self, parent: str, child: str, fk_col: str, required: bool = True):
        parent, child = identifier(parent), identifier(child)
        pk = self.primary_key(parent)
        child_keys=[c['name'].casefold() for c in self.columns(child) if c['pk']]
        if identifier(fk_col).casefold() in child_keys:
            raise LabError('A 1:N foreign key must not be the child primary key. Choose a separate FK column, or use the 1:1 wizard.')
        self._add_fk_to_existing(parent, child, fk_col, required=required, one_to_one=False)
        self.connection.execute('INSERT OR IGNORE INTO __lab_column_types VALUES (?,?,?)', (child, fk_col, self.logical_type(parent, pk['name'])))
        self.connection.execute('INSERT INTO __lab_relationships(kind,parent,child,fk_column,bridge) VALUES(?,?,?,?,?)',
                                ('1:N', parent, child, fk_col, ''))
        self.connection.commit()
        return f'{parent}.{pk["name"]} (1) → {child}.{fk_col} (N)'

    def one_to_one(self, parent: str, child: str):
        parent, child = identifier(parent), identifier(child)
        child_pk = self.primary_key(child)
        self._add_fk_to_existing(parent, child, child_pk['name'], required=True, one_to_one=True)
        self.connection.execute('INSERT INTO __lab_relationships(kind,parent,child,fk_column,bridge) VALUES(?,?,?,?,?)',
                                ('1:1', parent, child, child_pk['name'], ''))
        self.connection.commit()
        return f'{parent} (PK) ↔ {child} (PK/FK)'

    def many_to_many(self, left: str, right: str, bridge: str, strategy: str = 'composite'):
        left, right, bridge = identifier(left), identifier(right), identifier(bridge)
        if left == right or bridge in (left, right):
            raise LabError('The junction table must be distinct from two different endpoint tables.')
        if bridge in self.tables():
            raise LabError('The junction table already exists.')
        lp, rp = self.primary_key(left), self.primary_key(right)
        lc, rc = identifier(f'{left}_{lp["name"]}'), identifier(f'{right}_{rp["name"]}')
        if len({lc.lower(), rc.lower()}) < 2:
            raise LabError('Junction foreign key names would collide.')
        if strategy not in ('composite', 'surrogate'):
            raise LabError('Invalid junction primary key strategy.')
        coldefs = []
        if strategy == 'surrogate':
            coldefs.append('"JunctionID" INTEGER PRIMARY KEY AUTOINCREMENT')
        coldefs += [f'{q(lc)} {col_type(lp["type"])} NOT NULL',
                    f'{q(rc)} {col_type(rp["type"])} NOT NULL']
        coldefs.append(f'FOREIGN KEY ({q(lc)}) REFERENCES {q(left)} ({q(lp["name"])})')
        coldefs.append(f'FOREIGN KEY ({q(rc)}) REFERENCES {q(right)} ({q(rp["name"])})')
        pair = f'{q(lc)}, {q(rc)}'
        coldefs.append(f'UNIQUE ({pair})' if strategy == 'surrogate' else f'PRIMARY KEY ({pair})')
        with self.connection:
            self.connection.execute(f'CREATE TABLE {q(bridge)} (' + ', '.join(coldefs) + ')')
            for source,col,fk in ((left,lp,lc),(right,rp,rc)):
                self.connection.execute('INSERT INTO __lab_column_types VALUES(?,?,?)', (bridge,fk,self.logical_type(source,col['name'])))
            if strategy=='surrogate':
                self.connection.execute('INSERT INTO __lab_column_types VALUES(?,?,?)',(bridge,'JunctionID','INT'))
                self.connection.execute('INSERT INTO __lab_identity VALUES(?,?,?,?,?)',(bridge,'JunctionID',1,1,1))
            for parent, fk in ((left, lc), (right, rc)):
                self.connection.execute('INSERT INTO __lab_relationships(kind,parent,child,fk_column,bridge) VALUES(?,?,?,?,?)',
                                        ('N:M', parent, bridge, fk, bridge))
        return f'{left} (1) ← {bridge} → (1) {right}; PK: {strategy}'

    def design_columns(self, table: str) -> list[Column]:
        """Load editable column specifications from an existing table."""
        self._exists(table)
        identity = self.identity_settings(table)
        result=[]
        for c in self.columns(table):
            ai = bool(identity and identity['column_name'].casefold() == c['name'].casefold())
            result.append(Column(c['name'], self.logical_type(table,c['name']), bool(c['pk']),
                                 bool(c['notnull'] or c['pk']),ai,
                                 int(identity['seed']) if ai else 1,
                                 int(identity['increment']) if ai else 1))
        return result

    def edit_table(self, table: str, columns: Iterable[Column], original_names: dict[str,str|None]|None=None,
                   *, extra_foreign_keys: list[tuple[str,str,str]]|None=None,
                   remove_fk_ids: set[int]|None=None):
        """Transactionally rebuild a table without losing rows or referential integrity.

        original_names maps NEW column names to OLD names; columns not in old schema are new.
        Other tables' foreign keys are kept valid. Changes to referenced PKs are blocked.
        Advanced custom SQL objects are refused instead of silently discarded.
        """
        self._exists(table)
        columns=list(columns)
        if not columns:
            raise LabError('A table must have at least one column.')
        if len({identifier(c.name).casefold() for c in columns})!=len(columns):
            raise LabError('Duplicate column names are not allowed.')
        original=self.columns(table)
        oldmap={c['name'].casefold():c for c in original}
        if original_names is None:
            original_names={c.name:(c.name if c.name.casefold() in oldmap else None) for c in columns}
        mappings={c.name:original_names.get(c.name) for c in columns}
        old_used=[v.casefold() for v in mappings.values() if v]
        if len(set(old_used))!=len(old_used) or any(name not in oldmap for name in old_used):
            raise LabError('Invalid original column mapping. Reload the table designer.')
        old_to_new={v.casefold():k for k,v in mappings.items() if v}
        pk_cols=[c for c in columns if c.primary]
        if not pk_cols:
            raise LabError('Choose a primary key before saving the table.')
        auto=[c for c in columns if c.auto]
        if len(auto)>1 or (auto and (len(pk_cols)!=1 or not auto[0].primary or col_type(auto[0].type) not in
                                   ('INT','INTEGER','BIGINT','SMALLINT','TINYINT'))):
            raise LabError('IDENTITY requires a single integer primary key.')
        if auto and (auto[0].increment==0 or abs(auto[0].seed)>10**12 or abs(auto[0].increment)>10**9):
            raise LabError('Invalid IDENTITY seed or increment.')

        source_sql=self.connection.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name=?',(table,)).fetchone()[0] or ''
        # Generated length checks and UNIQUE constraints are rebuilt; arbitrary CHECKs/defaults/views
        # can be significant, so changing tables containing these is deliberately not implicit.
        generated_check=r'CHECK\s*\(\s*"[^"]+"\s+IS\s+NULL\s+OR\s+length\("[^"]+"\)\s*<=\s*\d+\s*\)'
        stripped=re.sub(generated_check,'',source_sql,flags=re.I)
        if re.search(r'\b(CHECK|GENERATED|COLLATE|WITHOUT\s+ROWID)\b',stripped,re.I):
            raise LabError('A custom constraint exists. Use SQL to modify this advanced table; no automatic changes were made.')
        if any(c['dflt_value'] is not None for c in original):
            raise LabError('This table contains SQL default expressions. Visual redesign is disabled to preserve them safely.')
        custom=self.connection.execute('SELECT name,type FROM sqlite_master WHERE tbl_name=? AND type IN ("index","trigger") AND sql IS NOT NULL',(table,)).fetchall()
        if any(not r['name'].startswith('__lab_identity_trigger_') for r in custom):
            raise LabError('Custom indexes or triggers exist. Visual redesign is disabled to prevent losing them.')

        oldpk={c['name'].casefold() for c in original if c['pk']}
        newpk={mappings[c.name].casefold() for c in pk_cols if mappings[c.name]}
        incoming=[(other,fk) for other in self.tables() for fk in self.foreign_keys(other)
                  if fk['table'].casefold()==table.casefold() and other!=table]
        if incoming:
            for old in oldpk:
                dest=old_to_new.get(old)
                if old not in newpk or not dest or dest.casefold()!=old:
                    raise LabError('This primary key is referenced by another table. It cannot be renamed or removed in Design mode.')
            for c in pk_cols:
                if mappings[c.name] and col_type(c.type)!=self.logical_type(table,mappings[c.name]):
                    raise LabError('Do not change the type of a referenced primary key.')

        prior_identity=self.identity_settings(table)
        if any(c.auto and not mappings[c.name] for c in columns):
            if self.connection.execute(f'SELECT EXISTS(SELECT 1 FROM {q(table)})').fetchone()[0]:
                raise LabError('Cannot add an IDENTITY column to a populated table in the visual designer.')
        old_fk=self.foreign_keys(table)
        removal_ids=set(remove_fk_ids or ())
        actual_ids={int(f['id']) for f in old_fk}
        if not removal_ids.issubset(actual_ids):
            raise LabError('Selected relationship no longer exists. Refresh the diagram.')
        # A whole (possibly composite) FK constraint is removed, never one of its
        # constituent columns. Other FKs must survive the table reconstruction.
        removed_fk=[f for f in old_fk if int(f['id']) in removal_ids]
        retained_fk=[f for f in old_fk if int(f['id']) not in removal_ids]
        new_types={c.name.casefold():col_type(c.type).replace('INTEGER','INT') for c in columns}
        for oldfk in retained_fk:
            newcol=old_to_new.get(oldfk['from'].casefold())
            if newcol:
                target=oldfk['table']
                reference=(old_to_new.get(oldfk['to'].casefold(),oldfk['to'])
                           if target.casefold()==table.casefold() else oldfk['to'])
                if target==table:
                    parent_type=new_types.get(reference.casefold())
                else:
                    parent_type=self.logical_type(target,reference).replace('INTEGER','INT')
                if parent_type and new_types[newcol.casefold()]!=parent_type:
                    raise LabError(f'{newcol} must retain the same SQL type as {target}.{reference} to be a valid foreign key.')
        constraints=[]
        groups={}
        for fk in retained_fk:groups.setdefault(fk['id'],[]).append(fk)
        for rows in groups.values():
            rows.sort(key=lambda r:r['seq'])
            if any(r['on_update']!='NO ACTION' or r['on_delete']!='NO ACTION' for r in rows):
                raise LabError('Custom ON DELETE/ON UPDATE rules cannot be silently altered by the visual designer.')
            local=[]
            for row in rows:
                mapped=old_to_new.get(row['from'].casefold())
                if mapped is None:
                    raise LabError(f'Column {row["from"]} is a foreign key. Remove the relationship before deleting it.')
                local.append(q(mapped))
            target=rows[0]['table']
            if target.casefold()==table.casefold():
                remote=[]
                for row in rows:
                    mapped=old_to_new.get(row['to'].casefold())
                    if mapped is None:raise LabError('A self-reference uses a removed parent column.')
                    remote.append(q(mapped))
            else:remote=[q(row['to']) for row in rows]
            constraints.append('FOREIGN KEY ('+', '.join(local)+') REFERENCES '+q(target)+
                               ' ('+', '.join(remote)+')')
        for local,parent,remote in (extra_foreign_keys or []):
            if local.casefold() not in {c.name.casefold() for c in columns}:
                raise LabError('Foreign key column missing from new design.')
            constraints.append('FOREIGN KEY ('+q(local)+') REFERENCES '+q(parent)+' ('+q(remote)+')')
        # Preserve UNIQUE constraints (including surrogate-key bridge pair uniqueness).
        for idx in self.connection.execute(f'PRAGMA index_list({q(table)})'):
            if idx['origin']=='u':
                idx_columns=[r['name'] for r in self.connection.execute('PRAGMA index_info('+chr(34)+idx['name'].replace(chr(34),chr(34)*2)+chr(34)+')')]
                if not all(n and n.casefold() in old_to_new for n in idx_columns):
                    raise LabError('A UNIQUE constraint uses a deleted column.')
                constraints.append('UNIQUE ('+', '.join(q(old_to_new[n.casefold()]) for n in idx_columns)+')')
        existing_count=self.connection.execute(f'SELECT COUNT(*) FROM {q(table)}').fetchone()[0]
        definitions=[]
        for c in columns:
            logical=col_type(c.type)
            st=storage_type(logical,c.auto)
            col_sql=q(c.name)+' '+st
            if c.auto:
                col_sql+=' PRIMARY KEY AUTOINCREMENT'
            elif len(pk_cols)==1 and c.primary:
                col_sql+=' PRIMARY KEY'
                if st!='INTEGER':col_sql+=' NOT NULL'
            elif c.primary or c.required:col_sql+=' NOT NULL'
            if not mappings[c.name] and existing_count and (c.primary or c.required):
                raise LabError('A new required/primary column cannot be added to a table containing rows without supplying values.')
            size=re.fullmatch(r'(N?VARCHAR|N?CHAR)\((\d+)\)',logical)
            if size:col_sql+=f' CHECK ({q(c.name)} IS NULL OR length({q(c.name)})<={int(size.group(2))})'
            definitions.append(col_sql)
        if len(pk_cols)>1:
            constraints.append('PRIMARY KEY ('+', '.join(q(c.name) for c in pk_cols)+')')
        tmp='__lab_design_rebuild'
        if self.connection.execute('SELECT 1 FROM sqlite_master WHERE name=?',(tmp,)).fetchone():
            raise LabError('Temporary migration table already exists; no changes made.')
        old_seq=None
        if prior_identity:
            try:
                seq=self.connection.execute('SELECT seq FROM sqlite_sequence WHERE name=?',(table,)).fetchone()
                if seq:old_seq=seq[0]
            except sqlite3.OperationalError:pass

        # SQLite documented generalized ALTER TABLE procedure: switch FK checks off *outside*
        # a transaction, rebuild atomically, validate, then restore enforcement in finally.
        self.connection.commit()
        self.connection.execute('PRAGMA foreign_keys=OFF')
        try:
            with self.connection:
                self.connection.execute(f'CREATE TABLE "{tmp}" ('+', '.join(definitions+constraints)+')')
                carry=[(c.name,mappings[c.name]) for c in columns if mappings[c.name]]
                if carry:
                    dest=', '.join(q(n) for n,_ in carry)
                    src=', '.join(q(o) for _,o in carry)
                    self.connection.execute(f'INSERT INTO "{tmp}" ({dest}) SELECT {src} FROM {q(table)}')
                elif existing_count:
                    raise LabError('All original columns were removed; data would be lost.')
                self.connection.execute(f'DROP TABLE {q(table)}')
                self.connection.execute(f'ALTER TABLE "{tmp}" RENAME TO {q(table)}')
                self.connection.execute('DELETE FROM __lab_column_types WHERE table_name=?',(table,))
                self.connection.executemany('INSERT INTO __lab_column_types VALUES(?,?,?)',
                                            [(table,c.name,col_type(c.type)) for c in columns])
                self.connection.execute('DELETE FROM __lab_identity WHERE table_name=?',(table,))
                if auto:
                    c=auto[0]
                    same=(prior_identity and mappings[c.name] and
                          prior_identity['column_name'].casefold()==mappings[c.name].casefold() and
                          prior_identity['seed']==c.seed and prior_identity['increment']==c.increment)
                    next_id=int(prior_identity['next_value']) if same and prior_identity['next_value'] is not None else int(c.seed)
                    self.connection.execute('INSERT INTO __lab_identity VALUES(?,?,?,?,?)',
                                            (table,c.name,int(c.seed),int(c.increment),next_id))
                    self._install_identity_trigger(table)
                    if old_seq is not None and c.seed==1 and c.increment==1:
                        self.connection.execute('UPDATE sqlite_sequence SET seq=MAX(seq,?) WHERE name=?',(old_seq,table))
                for removed in removed_fk:
                    self.connection.execute(
                        'DELETE FROM __lab_relationships WHERE child=? AND parent=? AND lower(fk_column)=lower(?)',
                        (table,removed['table'],removed['from']))
                for old_name,new_name in old_to_new.items():
                    if old_name!=new_name.casefold():
                        self.connection.execute('UPDATE __lab_relationships SET fk_column=? WHERE child=? AND lower(fk_column)=?',
                                                (new_name,table,old_name))
                invalid=self.connection.execute('PRAGMA foreign_key_check').fetchall()
                if invalid:
                    raise LabError('Referential integrity would be violated. The table redesign has been rolled back.')
        except (sqlite3.Error,LabError) as exc:
            raise LabError(f'Table design not saved: {exc}') from exc
        finally:
            self.connection.execute('PRAGMA foreign_keys=ON')
        return f'Table {table} updated; existing data and relationships preserved.'

    def remove_relationship(self, child: str, fk_id: int):
        """Remove one *physical* FK, not its columns or data.

        Uses the tested transactional designer so the remaining constraints,
        identity settings and data remain intact. Incoming references stay valid.
        """
        child=identifier(child)
        self._exists(child)
        group=[fk for fk in self.foreign_keys(child) if int(fk['id'])==int(fk_id)]
        if not group:
            raise LabError('Relationship was not found; refresh the diagram.')
        self.edit_table(child,self.design_columns(child),remove_fk_ids={int(fk_id)})
        return f'Removed relationship from {child} to {group[0]["table"]}; all columns and data retained.'

    def remove_many_to_many_link(self, bridge: str):
        """Remove the two FK constraints composing a modeled N:M annotation.

        Keep the junction table and all of its records. The operation uses a
        *single* table rebuild, so either both FKs are removed or neither is.
        """
        bridge=identifier(bridge)
        self._exists(bridge)
        endpoints={r['parent'] for r in self.connection.execute(
            'SELECT parent FROM __lab_relationships WHERE kind=? AND bridge=? AND child=?',
            ('N:M',bridge,bridge))}
        if len(endpoints)!=2:
            raise LabError('The selected N:M relationship is no longer available.')
        ids={int(fk['id']) for fk in self.foreign_keys(bridge) if fk['table'] in endpoints}
        if len(ids)!=2:
            raise LabError('Expected two foreign keys in the junction. Refresh the diagram.')
        self.edit_table(bridge,self.design_columns(bridge),remove_fk_ids=ids)
        return f'Removed both N:M foreign keys from {bridge}. Junction table and rows were kept.'

    def self_reference(self, table: str, fk_col: str, required: bool = False):
        """Create hierarchical 1:N relationship within the SAME table.
        NULL is recommended so root records can exist without a parent.
        """
        self._exists(table)
        fk_col=identifier(fk_col)
        pk=self.primary_key(table)
        if fk_col.casefold()==pk['name'].casefold():
            raise LabError('A hierarchy needs a separate foreign-key column, not the primary key itself.')
        if any(row['from'].casefold()==fk_col.casefold() for row in self.foreign_keys(table)):
            raise LabError('This field is already a foreign key.')
        current=self.design_columns(table)
        found=next((c for c in current if c.name.casefold()==fk_col.casefold()),None)
        if found:
            if col_type(found.type).replace('INTEGER','INT')!=self.logical_type(table,pk['name']).replace('INTEGER','INT'):
                raise LabError('Self-referencing FK type must match the primary-key type.')
            if required and not found.required:
                current=[Column(c.name,c.type,c.primary,(True if c.name==found.name else c.required),c.auto,c.seed,c.increment) for c in current]
        else:
            current.append(Column(fk_col,self.logical_type(table,pk['name']),False,required))
        self.edit_table(table,current,extra_foreign_keys=[(fk_col,table,pk['name'])])
        with self.connection:
            self.connection.execute('INSERT INTO __lab_relationships(kind,parent,child,fk_column,bridge) VALUES(?,?,?,?,?)',
                                    ('SELF',table,table,fk_col,''))
        return f'{table}.{fk_col} → {table}.{pk["name"]} (self-referencing hierarchy)'

    def links(self) -> list[dict]:
        links = []
        for child in self.tables():
            cpk = {c['name'] for c in self.columns(child) if c['pk']}
            groups = {}
            for row in self.foreign_keys(child):
                groups.setdefault(row['id'], []).append(row)
            for group in groups.values():
                group.sort(key=lambda v: v['seq'])
                parent = group[0]['table']
                if parent not in self.tables():
                    continue
                cols = [r['from'] for r in group]
                shared = len(cols) == 1 and cpk == set(cols)
                kind = 'SELF' if parent == child and not shared else ('1:1' if shared else '1:N')
                links.append({'parent': parent, 'child': child, 'kind': kind,
                              'fk': ', '.join(cols), 'fk_id': int(group[0]['id']),
                              'parent_field':group[0]['to'],'child_field':group[0]['from']})
        # The physical 1:N bridge constraints remain visible. This annotation makes
        # the original N:M conceptual relationship explicit to students as well.
        grouped={}
        for row in self.connection.execute('SELECT bridge,parent,child FROM __lab_relationships WHERE kind="N:M" AND bridge!=""'):
            grouped.setdefault(row['bridge'],set()).add(row['parent'])
        for bridge,endpoints in grouped.items():
            if len(endpoints)==2 and bridge in self.tables():
                physical_parents={fk['table'] for fk in self.foreign_keys(bridge)}
                if not endpoints.issubset(physical_parents):
                    continue
                left,right=sorted(endpoints)
                links.append({'parent':left,'child':right,'kind':'N:M',
                              'fk':f'via {bridge}','semantic':True,'bridge':bridge})
        return links

    def positions(self) -> dict[str, tuple[int, int]]:
        return {r['table_name']: (r['x'], r['y']) for r in self.connection.execute('SELECT * FROM __lab_positions')}

    def save_position(self, table: str, x: int, y: int):
        self.connection.execute('INSERT INTO __lab_positions(table_name,x,y) VALUES(?,?,?) '
                                'ON CONFLICT(table_name) DO UPDATE SET x=excluded.x,y=excluded.y',
                                (table, x, y))
        self.connection.commit()

    def check_integrity(self) -> list[dict]:
        """Return foreign-key violations; none means all non-NULL references are valid."""
        if not self.connection.execute('PRAGMA foreign_keys').fetchone()[0]:
            raise LabError('Foreign key enforcement is disabled. Restart/open the database safely.')
        return [dict(zip(('table','rowid','parent','fkid'),tuple(row)))
                for row in self.connection.execute('PRAGMA foreign_key_check')]

    def execute(self, statement: str, limit: int = 500) -> tuple[list[str], list[tuple], str]:
        statement = statement.strip()
        if not statement:
            return [], [], 'No SQL statement entered.'
        # Never allow the educational SQL editor to silently disable FK enforcement.
        if re.search(r'\bPRAGMA\s+(?:foreign_keys|ignore_check_constraints)\s*(?:\(|=)',statement,re.I):
            raise LabError('Integrity pragmas cannot be modified in the teaching Query Editor. Foreign-key checks stay enabled.')
        if re.search(r'^\s*(CREATE\s+DATABASE|USE\s+|GO\s*$)', statement, re.I | re.M):
            raise LabError('CREATE DATABASE, USE and GO are SQL Server commands. Use File > New/Open Database in this SQLite-backed teaching simulator.')
        statements = []
        buf = ''
        for ch in statement:
            buf += ch
            if ch == ';' and sqlite3.complete_statement(buf):
                if buf.strip():
                    statements.append(buf.strip())
                buf = ''
        if buf.strip():
            statements.append(buf.strip())
        names, rows, msg = [], [], ''
        try:
            for part in statements:
                cursor = self.connection.execute(part)
                if cursor.description:
                    names = [x[0] for x in cursor.description]
                    data = cursor.fetchmany(limit + 1)
                    rows = [tuple(x) for x in data[:limit]]
                    msg = f'{len(rows)} row(s) returned' + (' (more rows exist)' if len(data) > limit else '')
                else:
                    names, rows = [], []
                    msg = f'Statement completed. Rows affected: {max(cursor.rowcount, 0)}'
            self.connection.commit()
            return names, rows, msg
        except sqlite3.Error as exc:
            self.connection.rollback()
            raise LabError(f'SQL error: {exc}') from exc

    def backup(self, target: str | Path):
        dest = sqlite3.connect(str(target))
        try:
            self.connection.backup(dest)
        finally:
            dest.close()

    def export_sql(self, target: str | Path):
        Path(target).write_text('\n'.join(self.connection.iterdump()), encoding='utf-8')

    def demo(self):
        if self.tables():
            raise LabError('The teaching sample can only be created in an empty database.')
        self.create_table('Student', [Column('StudentID', 'INTEGER', True, True, True), Column('FullName', 'TEXT', required=True)])
        self.create_table('Profile', [Column('StudentID', 'INTEGER', True, True), Column('Phone', 'TEXT')])
        self.create_table('Department', [Column('DepartmentID', 'INTEGER', True, True, True), Column('Title', 'TEXT', required=True)])
        self.create_table('Course', [Column('CourseID', 'INTEGER', True, True, True), Column('CourseName', 'TEXT', required=True)])
        self.one_to_one('Student', 'Profile')
        self.one_to_many('Department', 'Student', 'DepartmentID', required=False)
        self.many_to_many('Student', 'Course', 'Enrollment', 'composite')
        self.self_reference('Student','MentorID',False)
