"""Documented educational T-SQL subset on a SQLite-backed desktop lab.

CREATE DATABASE/USE/GO work as local project-file operations. CREATE USER,
GRANT and DENY are explicitly *metadata-only simulations*: they DO NOT
implement SQL Server authentication, authorization or server roles.
Unsupported syntax fails visibly; never claim success for ignored SQL.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from core import LabDatabase, LabError, Column, col_type, identifier
from tsql_modules import (create_module, execute_procedure, drop_module,
                          _MODULE_HEAD, _replace_names_and_nstrings)

_NAME=r'(?:\[[A-Za-z_][\w]*\]|[A-Za-z_][\w]*)'
_SQLNAME=rf'(?:{_NAME}\.)?({_NAME})'


def unquote(name):
    return identifier(name.strip('[]'))


def split_batches(script):
    """Split standalone GO batch lines, but never a GO inside quoted strings/comments."""
    chunks=[];buf=[];quote=None;block=False
    for line in script.splitlines(keepends=True):
        clean=line.strip()
        if quote is None and not block and re.fullmatch(r'GO(?:\s*--.*)?',clean,re.I):
            chunk=''.join(buf).strip()
            if chunk:chunks.append(chunk)
            buf=[]
            continue
        if quote is None and not block and re.fullmatch(r'GO\s+\d+(?:\s*--.*)?',clean,re.I):
            raise LabError('GO with a repeat count is not supported by the teaching simulator.')
        buf.append(line)
        i=0
        while i<len(line):
            char=line[i];nxt=line[i+1] if i+1<len(line) else ''
            if block:
                if char=='*' and nxt=='/':block=False;i+=2;continue
            elif quote is not None:
                if char==quote:
                    if nxt==quote:i+=2;continue
                    quote=None
            elif char=='-' and nxt=='-':break
            elif char=='/' and nxt=='*':block=True;i+=2;continue
            elif char in ("'",'"'):quote=char
            i+=1
    if quote is not None or block:
        raise LabError('Unclosed SQL string or block comment.')
    text=''.join(buf).strip()
    if text:chunks.append(text)
    return chunks


def split_statements(batch):
    """Retain SQLite trigger bodies while allowing multiple SQL statements."""
    pieces=[];buf=''
    for char in batch:
        buf+=char
        if char==';' and sqlite3.complete_statement(buf):
            if buf.strip():pieces.append(buf.strip())
            buf=''
    if buf.strip():pieces.append(buf.strip())
    return pieces


def strip_leading_comments(sql):
    """Recognize command names after legal leading SQL comments and blank lines."""
    result=sql.strip()
    while result:
        if result.startswith('--'):
            _,_,result=result.partition('\n')
        elif result.startswith('/*'):
            end=result.find('*/',2)
            if end<0:raise LabError('Unclosed SQL comment.')
            result=result[end+2:]
        else:
            break
        result=result.strip()
    return result.strip().rstrip(';').strip()



def comma_parts(s):
    parts=[];start=0;depth=0;quoted=None
    for i,ch in enumerate(s):
        if quoted:
            if ch==quoted:quoted=None
        elif ch in ('[',"'",'"'):quoted=']' if ch=='[' else ch
        elif ch=='(':depth+=1
        elif ch==')':depth-=1
        elif ch==',' and depth==0:
            parts.append(s[start:i].strip());start=i+1
    parts.append(s[start:].strip())
    return parts


def _create_table_tsql(db,sql):
    """Subset: column type, NULL/NOT NULL, IDENTITY(seed,increment), single PK."""
    m=re.fullmatch(rf'CREATE\s+TABLE\s+{_SQLNAME}\s*\((.*)\)\s*;?',sql.strip(),re.I|re.S)
    if not m:return None
    name=unquote(m.group(1));definitions=comma_parts(m.group(2))
    primary=[];columns=[]
    for definition in definitions:
        p=re.match(r'^(?:CONSTRAINT\s+'+_NAME+r'\s+)?PRIMARY\s+KEY\s*\((.*?)\)\s*$',definition,re.I|re.S)
        if p:
            primary=[unquote(c.strip()) for c in comma_parts(p.group(1))]
            continue
        c=re.match(rf'^({_NAME})\s+(\[?[A-Z]+\]?(?:\s*\([^()]*\))?)(.*)$',definition,re.I|re.S)
        if not c:
            raise LabError('Unsupported CREATE TABLE column/constraint: '+definition[:140])
        col=unquote(c.group(1));typ=re.sub(r'\s+','',c.group(2)).replace('[','').replace(']','').upper();rest=c.group(3)
        typ=col_type(typ)
        identity=re.search(r'\bIDENTITY\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)',rest,re.I)
        if re.search(r'\b(REFERENCES|FOREIGN|DEFAULT|CHECK|UNIQUE|COLLATE|AS)\b',rest,re.I):
            raise LabError('Use Table Designer for this CREATE TABLE constraint; it is not supported in the T-SQL translator.')
        ispk=bool(re.search(r'\bPRIMARY\s+KEY\b',rest,re.I))
        required=bool(re.search(r'\bNOT\s+NULL\b',rest,re.I))
        columns.append(Column(col,typ,ispk,required,bool(identity),int(identity.group(1)) if identity else 1,int(identity.group(2)) if identity else 1))
    if primary:
        columns=[Column(c.name,c.type,c.primary or c.name in primary,c.required,c.auto,c.seed,c.increment) for c in columns]
    db.create_table(name,columns)
    return f'Created {name} using the supported T-SQL CREATE TABLE subset.'


def _add_foreign_key_tsql(db, sql):
    """Translate common single-column T-SQL ALTER TABLE ... ADD FOREIGN KEY.

    SQL Server supports many more FK options, including composite keys and
    cascades. This intentionally translates only the validated, non-cascading
    educational subset; every unsupported variation must fail visibly.
    """
    match=re.fullmatch(
        rf'ALTER\s+TABLE\s+{_SQLNAME}\s+(?:WITH\s+CHECK\s+)?ADD\s+'
        rf'(?:CONSTRAINT\s+{_NAME}\s+)?FOREIGN\s+KEY\s*'
        rf'\(\s*({_NAME})\s*\)\s+REFERENCES\s+{_SQLNAME}\s*'
        rf'\(\s*({_NAME})\s*\)',
        sql.strip(), re.I|re.S)
    if not match:
        return None
    child, field, parent, ref=(unquote(match.group(i)) for i in range(1,5))
    db._exists(child)
    db._exists(parent)
    pk=db.primary_key(parent)
    if pk['name'].casefold()!=ref.casefold():
        raise LabError('Only foreign keys referencing the parent primary key are supported.')
    cols={c['name'].casefold():c for c in db.columns(child)}
    col=cols.get(field.casefold())
    if col is None:
        raise LabError(f'Child foreign key column {field} does not exist in {child}.')
    relation=('SELF' if child.casefold()==parent.casefold() else
              '1:1' if col['pk'] else '1:N')
    db.connect_fields(parent,ref,child,col['name'],kind=relation,
                      required=bool(col['notnull']))
    return f'Created real {relation} foreign key: {child}.{field} -> {parent}.{ref}.'


def _ensure_security_metadata(db):
    with db.connection:
        db.connection.execute('''CREATE TABLE IF NOT EXISTS __lab_users(
          username TEXT PRIMARY KEY COLLATE NOCASE)''')
        db.connection.execute('''CREATE TABLE IF NOT EXISTS __lab_permissions(
          username TEXT NOT NULL COLLATE NOCASE, object_name TEXT NOT NULL COLLATE NOCASE,
          operation TEXT NOT NULL, decision TEXT NOT NULL,
          PRIMARY KEY(username,object_name,operation))''')


@dataclass
class BatchResult:
    database: LabDatabase | None
    columns: list[str]
    rows: list[tuple]
    messages: str


def run_script(database:LabDatabase|None,script:str,project_dir:str|Path)->BatchResult:
    """Run supported commands; throw precise errors for everything unsupported.

    The caller owns the returned DB connection. CREATE/USE only resolve under
    the active project folder, preventing path traversal or external file access.
    """
    base=Path(database.path.parent if database is not None else project_dir).expanduser().resolve()
    base.mkdir(parents=True,exist_ok=True)
    db=database;names=[];rows=[];messages=[]
    opened=[]
    def checked_path(value):
        return base/(unquote(value)+'.db')
    try:
        for batch in split_batches(script):
            # CREATE VIEW/PROCEDURE/FUNCTION are GO-delimited batch statements
            # in SQL Server. Their bodies may contain semicolons, so do not
            # split them into ordinary SQL statements.
            if _MODULE_HEAD.match(strip_leading_comments(batch)):
                if db is None:
                    raise LabError('No active database. Create or open a database first.')
                names=[];rows=[]
                messages.append(create_module(db,strip_leading_comments(batch)))
                continue
            for statement in split_statements(batch):
                sql=strip_leading_comments(statement)
                if not sql or re.fullmatch(r'(?:--[^\n]*(?:\n|$)|\s+)*',sql):continue
                create_db=re.fullmatch(rf'CREATE\s+DATABASE\s+({_NAME})',sql,re.I)
                use_db=re.fullmatch(rf'USE\s+({_NAME})',sql,re.I)
                if create_db:
                    path=checked_path(create_db.group(1))
                    if path.exists():raise LabError(f'Database {path.stem} already exists at {path}.')
                    newdb=LabDatabase(path);newdb.close()
                    messages.append(f'Created local educational database {path.name}. (SQLite file, not a SQL Server instance)')
                elif use_db:
                    path=checked_path(use_db.group(1))
                    if not path.is_file():raise LabError(f'Database {path.stem} not found in {base}. CREATE DATABASE first.')
                    if db is None or db.path!=path:
                        other=LabDatabase(path)
                        opened.append(other)
                        db=other
                    messages.append(f'Active local database: {path.stem}.')
                    names=[];rows=[]
                else:
                    if db is None:raise LabError('No active database. Run CREATE DATABASE and USE, or open one from File.')
                    user=re.fullmatch(rf'CREATE\s+USER\s+({_NAME})(?:\s+WITHOUT\s+LOGIN)?',sql,re.I)
                    permission=re.fullmatch(rf'(GRANT|DENY)\s+([A-Z,\s]+)\s+ON\s+{_SQLNAME}\s+TO\s+({_NAME})',sql,re.I)
                    if user:
                        _ensure_security_metadata(db)
                        username=unquote(user.group(1))
                        try:
                            with db.connection:db.connection.execute('INSERT INTO __lab_users VALUES(?)',(username,))
                        except sqlite3.IntegrityError as exc:raise LabError('User already exists in the educational metadata catalog.') from exc
                        messages.append(f'SIMULATED CREATE USER {username}: metadata only. No authentication or real SQL Server login.')
                        names=[];rows=[]
                    elif permission:
                        operation=permission.group(1).upper();rights=[part.strip().upper() for part in permission.group(2).split(',')]
                        allowed={'SELECT','INSERT','UPDATE','DELETE','REFERENCES'}
                        if not rights or any(right not in allowed for right in rights):
                            raise LabError('Only SELECT, INSERT, UPDATE, DELETE, REFERENCES are supported as educational permission metadata.')
                        table=unquote(permission.group(3));username=unquote(permission.group(4))
                        db._exists(table);_ensure_security_metadata(db)
                        if not db.connection.execute('SELECT 1 FROM __lab_users WHERE username=?',(username,)).fetchone():
                            raise LabError(f'User {username} is not in the simulated user catalog. CREATE USER first.')
                        with db.connection:
                            for right in rights:
                                db.connection.execute('''INSERT INTO __lab_permissions VALUES(?,?,?,?)
                                       ON CONFLICT(username,object_name,operation)
                                       DO UPDATE SET decision=excluded.decision''',(username,table,right,operation))
                        messages.append(f'SIMULATED {operation} '+', '.join(rights)+f' ON {table} TO {username}: NOT ENFORCED by SQLite.')
                        names=[];rows=[]
                    elif re.match(r'^DROP\s+(?:VIEW|PROC(?:EDURE)?|FUNCTION)\b',sql,re.I):
                        messages.append(drop_module(db,sql))
                        names=[];rows=[]
                    elif re.match(r'^(?:EXEC|EXECUTE)\s+',sql,re.I):
                        names,rows,message=execute_procedure(db,sql)
                        messages.append(message)
                    elif re.fullmatch(rf'DROP\s+TABLE\s+{_SQLNAME}',sql,re.I):
                        match=re.fullmatch(rf'DROP\s+TABLE\s+{_SQLNAME}',sql,re.I)
                        messages.append(db.drop_table(unquote(match.group(1))))
                        names=[];rows=[]
                    elif re.fullmatch(rf'ALTER\s+TABLE\s+{_SQLNAME}\s+DROP\s+COLUMN\s+({_NAME})',sql,re.I):
                        match=re.fullmatch(rf'ALTER\s+TABLE\s+{_SQLNAME}\s+DROP\s+COLUMN\s+({_NAME})',sql,re.I)
                        messages.append(db.drop_column(unquote(match.group(1)),unquote(match.group(2))))
                        names=[];rows=[]
                    elif re.match(r'^ALTER\s+TABLE\b',sql,re.I) and re.search(r'\bFOREIGN\s+KEY\b',sql,re.I):
                        message=_add_foreign_key_tsql(db,sql)
                        if message is None:
                            raise LabError('Unsupported ALTER TABLE foreign key syntax. Single-column, non-cascading FK to a PRIMARY KEY is supported.')
                        messages.append(message)
                        names=[];rows=[]
                    elif re.match(r'^\s*CREATE\s+TABLE\b',sql,re.I) and ('IDENTITY(' in sql.upper() or '[DBO].' in sql.upper() or 'DBO.' in sql.upper()):
                        message=_create_table_tsql(db,sql)
                        if message is None:raise LabError('Unsupported SQL Server CREATE TABLE syntax; use Table Designer.')
                        names=[];rows=[];messages.append(message)
                    else:
                        # Reject unsupported security/server commands explicitly.
                        if re.match(r'^(?:CREATE\s+LOGIN|ALTER\s+USER|EXECUTE\s+AS|REVOKE|BACKUP\s+DATABASE)\b',sql,re.I):
                            raise LabError('This SQL Server server/security command is not implemented. No changes were made for this statement.')
                        translated=_replace_names_and_nstrings(statement)
                        names,rows,message=db.execute(translated)
                        messages.append(message)
    except Exception:
        for extra in opened:
            extra.close()
        raise
    for extra in opened:
        if extra is not db:extra.close()
    return BatchResult(db,names,rows,'\n'.join(messages) if messages else 'No SQL statement entered.')
