"""Small, explicit educational T-SQL module compatibility layer.

Views are real SQLite views. Procedures are persisted definitions whose supported
DML/SELECT bodies run transactionally with bound input parameters. Scalar UDFs
are SQLite registered functions, with one read-only, parameterized expression.
This is NOT the SQL Server T-SQL runtime or security sandbox.
"""
from __future__ import annotations

import json
import re
import sqlite3
from core import LabError, identifier, col_type, q

_NAME = r'(?:\[[A-Za-z_]\w*\]|[A-Za-z_]\w*)'
_QUALIFIED = rf'(?:{_NAME}\s*\.\s*)?{_NAME}'
_MODULE_HEAD = re.compile(r'^CREATE\s+(?:OR\s+ALTER\s+)?(?:VIEW|PROC(?:EDURE)?|FUNCTION)\b', re.I)


def object_name(token: str) -> str:
    parts = re.split(r'\s*\.\s*', token.strip())
    if len(parts) == 2:
        if parts[0].strip('[]').lower() != 'dbo':
            raise LabError('Only the dbo schema is supported in the teaching simulator.')
        token = parts[1]
    elif len(parts) != 1:
        raise LabError('Only a single dbo-qualified object name is supported.')
    return identifier(token.strip('[]'))


def _csv(source: str) -> list[str]:
    """Split SQL comma lists respecting parentheses, brackets and doubled quotes."""
    if not source.strip():
        return []
    result, start, depth, quote = [], 0, 0, None
    i = 0
    while i < len(source):
        ch = source[i]
        if quote:
            if ch == quote:
                if ch in "'\"" and i + 1 < len(source) and source[i+1] == quote:
                    i += 2; continue
                quote = None
        elif ch in "'\"[":
            quote = ']' if ch == '[' else ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0: raise LabError('Unbalanced parentheses in SQL object definition.')
        elif ch == ',' and depth == 0:
            result.append(source[start:i].strip()); start = i+1
        i += 1
    if quote or depth != 0:
        raise LabError('Unclosed string/parentheses in SQL object definition.')
    result.append(source[start:].strip())
    return result


def _balanced(source: str) -> tuple[str, str]:
    if not source.lstrip().startswith('('):
        raise LabError('Expected an opening parenthesis.')
    source = source.lstrip()
    depth, quote = 0, None
    for i, ch in enumerate(source):
        if quote:
            if ch == quote: quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return source[1:i], source[i+1:].strip()
    raise LabError('Unclosed parenthesis in CREATE FUNCTION / PROCEDURE.')


def _params(source: str) -> list[dict]:
    params, seen = [], set()
    for part in _csv(source):
        match = re.fullmatch(r'@([A-Za-z_]\w*)\s+(?:AS\s+)?([A-Za-z_]\w*(?:\(\s*(?:MAX|\d+(?:\s*,\s*\d+)?)\s*\))?)\s*(?:=\s*(.+))?', part, re.I|re.S)
        if not match:
            raise LabError(f'Unsupported parameter declaration: {part}. Use @Name INT or @Name NVARCHAR(50).')
        name = identifier(match.group(1))
        typ = col_type(re.sub(r'\s+', '', match.group(2)))
        if name.casefold() in seen:
            raise LabError('Duplicate routine parameter name: '+name)
        seen.add(name.casefold())
        default = _literal(match.group(3)) if match.group(3) is not None else None
        params.append({'name':name, 'type':typ, 'has_default':match.group(3) is not None, 'default':default})
    if len(params) > 32:
        raise LabError('The teaching simulator supports at most 32 input parameters per routine.')
    return params


def _literal(token: str):
    token = (token or '').strip()
    if re.fullmatch('NULL', token, re.I): return None
    if re.fullmatch(r'[+-]?\d+', token): return int(token)
    if re.fullmatch(r'[+-]?(?:\d+\.\d*|\.\d+)(?:[Ee][+-]?\d+)?', token): return float(token)
    if re.fullmatch(r"N?'(?:''|[^'])*'", token, re.I|re.S):
        return token[token.find("'")+1:-1].replace("''", "'")
    raise LabError('Routine arguments must be literals: numbers, N\'text\', or NULL. Expressions are not yet supported.')


def _replace_names_and_nstrings(sql: str) -> str:
    """Translate dbo-qualified objects and N-literals without touching quoted data."""
    string_re = re.compile(r"N?'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", re.I|re.S)
    def identifiers(part):
        part=re.sub(r'\[dbo\]\s*\.\s*\[([A-Za-z_]\w*)\]', r'"\1"', part, flags=re.I)
        part=re.sub(r'\b\[dbo\]\s*\.\s*([A-Za-z_]\w*)', r'"\1"', part, flags=re.I)
        part=re.sub(r'\bdbo\s*\.\s*\[([A-Za-z_]\w*)\]', r'"\1"', part, flags=re.I)
        part=re.sub(r'\bdbo\s*\.\s*([A-Za-z_]\w*)', r'"\1"', part, flags=re.I)
        part=re.sub(r'\bISNULL\s*\(', 'IFNULL(', part, flags=re.I)
        part=re.sub(r'\bLEN\s*\(', 'LENGTH(', part, flags=re.I)
        return part
    pieces=[]; offset=0
    for m in string_re.finditer(sql):
        pieces.append(identifiers(sql[offset:m.start()]))
        literal=m.group(0)
        pieces.append(literal[1:] if literal[:2].upper()=="N'" else literal)
        offset=m.end()
    pieces.append(identifiers(sql[offset:]))
    return ''.join(pieces)


def _bind_params(sql: str, params: list[dict]) -> str:
    """Safe SQLite named placeholders, ignoring literals and comments."""
    allowed = {p['name'].casefold():p['name'] for p in params}
    output=[]; i=0; quote=None
    while i < len(sql):
        c=sql[i]; nxt=sql[i+1] if i+1<len(sql) else ''
        if quote:
            output.append(c)
            if c==quote:
                if quote in "'\"" and nxt==quote:
                    output.append(nxt); i+=2; continue
                quote=None
            i+=1; continue
        if c in ("'",'"','['):
            quote=']' if c=='[' else c
            output.append(c);i+=1;continue
        if c=='-' and nxt=='-' or c=='/' and nxt=='*':
            raise LabError('Comments inside procedure/function bodies are not supported in this limited translator.')
        if c=='@' and i+1<len(sql) and re.match(r'[A-Za-z_]',sql[i+1]):
            m=re.match(r'@([A-Za-z_]\w*)',sql[i:]); name=m.group(1)
            if name.casefold() not in allowed:
                raise LabError('Undeclared routine parameter: @'+name)
            output.append(':'+allowed[name.casefold()]); i+=len(m.group(0));continue
        output.append(c);i+=1
    if quote:
        raise LabError('Unclosed quoted literal in routine body.')
    return ''.join(output)


def _body_statements(body: str) -> list[str]:
    body=body.strip().rstrip(';').strip()
    if re.match(r'^BEGIN\b',body,re.I):
        body=re.sub(r'^BEGIN\b','',body,flags=re.I).strip()
        if not re.search(r'\bEND\s*$',body,re.I):
            raise LabError('CREATE PROCEDURE body needs a matching END.')
        body=re.sub(r'\bEND\s*$','',body,flags=re.I).strip()
    # Only a deliberately small DML subset is supported, not general T-SQL control flow.
    pieces=[]; buf=''
    for ch in body:
        buf+=ch
        if ch==';' and sqlite3.complete_statement(buf):
            if buf.strip(): pieces.append(buf.strip())
            buf=''
    if buf.strip():pieces.append(buf.strip())
    return [p.rstrip(';').strip() for p in pieces if p.strip()]


def _catalog(db):
    with db.connection:
        db.connection.execute('''CREATE TABLE IF NOT EXISTS __lab_modules (
             kind TEXT NOT NULL, name TEXT NOT NULL COLLATE NOCASE,
             definition TEXT NOT NULL, params_json TEXT NOT NULL,
             payload TEXT NOT NULL, PRIMARY KEY(kind,name))''')


def list_modules(db, kind: str) -> list[str]:
    _catalog(db)
    return [r[0] for r in db.connection.execute('SELECT name FROM __lab_modules WHERE kind=? ORDER BY name COLLATE NOCASE',(kind,))]


def views(db) -> list[str]:
    return [r[0] for r in db.connection.execute("SELECT name FROM sqlite_master WHERE type='view' AND name NOT LIKE '__lab_%' ORDER BY name COLLATE NOCASE")]


def create_module(db, text: str) -> str:
    """CREATE VIEW, CREATE PROC/PROCEDURE or scalar FUNCTION in a GO-delimited batch."""
    text=text.strip().rstrip(';').strip()
    alter=bool(re.match(r'^CREATE\s+OR\s+ALTER\b',text,re.I))
    m=re.match(r'^CREATE\s+(?:OR\s+ALTER\s+)?(VIEW|PROC(?:EDURE)?|FUNCTION)\s+('+_QUALIFIED+r')(?=\s|$|\()', text,re.I|re.S)
    if not m:
        raise LabError('Unsupported CREATE routine syntax. Expected CREATE VIEW, PROCEDURE/PROC or FUNCTION.')
    kind=m.group(1).upper();name=object_name(m.group(2));tail=text[m.end():].strip()
    if kind=='VIEW':
        vm=re.fullmatch(r'AS\s+((?:SELECT|WITH)\b.+)',tail,re.I|re.S)
        if not vm:
            raise LabError('Supported CREATE VIEW syntax: CREATE VIEW dbo.Name AS SELECT ...; (use GO after the definition).')
        select=_replace_names_and_nstrings(vm.group(1)).strip().rstrip(';')
        if re.search(r'\b(TOP\s*\(|WITH\s+CHECK\s+OPTION|SCHEMABINDING|INTO\b|PRAGMA\b|ATTACH\b)\b',select,re.I):
            raise LabError('This CREATE VIEW feature is not supported. Use a simple SQLite-compatible SELECT.')
        # SQLite DDL is autocommitted without an explicit transaction. A
        # SAVEPOINT ensures an invalid view (or failed OR ALTER) never leaks.
        db.connection.execute('SAVEPOINT __lab_create_view')
        try:
            if alter and name in views(db):
                db.connection.execute(f'DROP VIEW {q(name)}')
            db.connection.execute(f'CREATE VIEW {q(name)} AS {select}')
            # SQLite accepts missing source tables at CREATE time.
            db.connection.execute(f'SELECT * FROM {q(name)} LIMIT 0')
            db.connection.execute('RELEASE SAVEPOINT __lab_create_view')
        except sqlite3.Error as exc:
            db.connection.execute('ROLLBACK TO SAVEPOINT __lab_create_view')
            db.connection.execute('RELEASE SAVEPOINT __lab_create_view')
            raise LabError(f'CREATE VIEW {name} failed: {exc}') from exc
        return f'Created executable SQLite view {name} (educational T-SQL subset).'
    if kind.startswith('PROC'):
        match=re.search(r'\bAS\b',tail,re.I)
        if match is None:
            raise LabError('CREATE PROCEDURE requires AS followed by SELECT/INSERT/UPDATE/DELETE.')
        decl=tail[:match.start()].strip();body=tail[match.end():].strip()
        if decl.startswith('('):
            decl,extra=_balanced(decl)
            if extra:raise LabError('Unsupported procedure options after parameters.')
        params=_params(decl)
        statements=_body_statements(body)
        if not statements:raise LabError('Procedure body cannot be empty.')
        compiled=[]
        for stmt in statements:
            if re.fullmatch(r'SET\s+NOCOUNT\s+ON',stmt,re.I): continue
            if not re.match(r'^(SELECT|INSERT|UPDATE|DELETE)\b',stmt,re.I):
                raise LabError('Only SELECT, INSERT, UPDATE, DELETE and SET NOCOUNT ON are supported inside procedures. IF/WHILE/TRY/CATCH/dynamic SQL are not supported.')
            compiled.append(_bind_params(_replace_names_and_nstrings(stmt),params))
        if not compiled:
            raise LabError('Procedure needs at least one SQL statement.')
        _catalog(db)
        if not alter and name in list_modules(db,'PROCEDURE'):
            raise LabError(f'Procedure {name} already exists. Use CREATE OR ALTER PROCEDURE.')
        with db.connection:
            db.connection.execute('INSERT OR REPLACE INTO __lab_modules VALUES(?,?,?,?,?)',
                                  ('PROCEDURE',name,text,json.dumps(params),json.dumps(compiled)))
        return f'Stored educational procedure {name}. Use EXEC {name} with bound input parameters; only a limited DML subset runs.'
    # FUNCTION: only a single scalar RETURN expression, no table-valued functions.
    if not tail.startswith('('):
        raise LabError('Scalar CREATE FUNCTION needs parameters in parentheses, including () when empty.')
    declaration,tail=_balanced(tail)
    params=_params(declaration)
    ret=re.fullmatch(r'RETURNS\s+([A-Za-z_]\w*(?:\([^()]*\))?)\s+AS\s+(.+)',tail,re.I|re.S)
    if not ret:
        raise LabError('Supported scalar FUNCTION syntax: RETURNS INT AS BEGIN RETURN @x + 1; END. Table-valued functions are not yet supported.')
    result_type=col_type(re.sub(r'\s+', '', ret.group(1)))
    body=ret.group(2).strip()
    if re.match(r'^BEGIN\b',body,re.I):
        body=re.sub(r'^BEGIN\b','',body,flags=re.I).strip()
        if not re.search(r'\bEND\s*;?\s*$',body,re.I):
            raise LabError('Function body is missing END.')
        body=re.sub(r'\bEND\s*;?\s*$','',body,flags=re.I).strip()
    expr=re.fullmatch(r'RETURN\s+(.+?)\s*;?',body,re.I|re.S)
    if expr is None:
        raise LabError('Only scalar functions with one RETURN expression are supported; DECLARE/SET/BEGIN nesting are not supported.')
    expr=expr.group(1).strip().rstrip(';')
    if re.search(r';|--|/\*|\b(?:SELECT|FROM|PRAGMA|ATTACH|DETACH|LOAD_EXTENSION|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b',expr,re.I):
        raise LabError('The function RETURN must be one read-only scalar expression without queries or side effects.')
    compiled=_bind_params(_replace_names_and_nstrings(expr),params)
    # Validate syntax and all bindings in a fresh isolated in-memory connection.
    try:
        with sqlite3.connect(':memory:') as check:
            check.execute('SELECT '+compiled,{p['name']:p['default'] if p['has_default'] else 1 for p in params}).fetchone()
    except sqlite3.Error as exc:
        raise LabError(f'Unsupported scalar function expression: {exc}') from exc
    _catalog(db)
    if not alter and name in list_modules(db,'FUNCTION'):
        raise LabError(f'Function {name} already exists. Use CREATE OR ALTER FUNCTION.')
    old=db.connection.execute('SELECT params_json FROM __lab_modules WHERE kind=? AND name=?',('FUNCTION',name)).fetchone()
    with db.connection:
        db.connection.execute('INSERT OR REPLACE INTO __lab_modules VALUES(?,?,?,?,?)',
                              ('FUNCTION',name,text,json.dumps(params),json.dumps({'return_type':result_type,'expr':compiled})))
    if old is not None:
        db.connection.create_function(name,len(json.loads(old[0])),None)
    register_functions(db)
    return f'Created callable scalar function {name}. Use SELECT dbo.{name}(...) (SQLite-registered expression; limited T-SQL subset).'


def _arguments(raw: str, params: list[dict]) -> dict:
    parts=_csv(raw)
    values={p['name']:p['default'] for p in params if p['has_default']}
    indexes={p['name'].casefold():p['name'] for p in params}
    positional_index=0;named=False;provided=set()
    for part in parts:
        match=re.fullmatch(r'@([A-Za-z_]\w*)\s*=\s*(.+)',part,re.I|re.S)
        if match:
            named=True;key=indexes.get(match.group(1).casefold())
            if key is None:raise LabError('Unknown procedure argument: '+match.group(1))
            if key in provided:
                raise LabError('Repeated argument: '+key)
            provided.add(key)
            values[key]=_literal(match.group(2))
        else:
            if named:raise LabError('Positional arguments must precede named arguments.')
            if positional_index>=len(params):raise LabError('Too many procedure input arguments.')
            key=params[positional_index]['name'];provided.add(key)
            values[key]=_literal(part);positional_index+=1
    missing=[p['name'] for p in params if p['name'] not in values]
    if missing:raise LabError('Missing procedure input argument(s): '+', '.join('@'+p for p in missing))
    return values


def execute_procedure(db,sql: str) -> tuple[list[str],list[tuple],str]:
    m=re.fullmatch(r'(?:EXEC(?:UTE)?)\s+('+_QUALIFIED+r')\s*(.*)',sql.strip().rstrip(';'),re.I|re.S)
    if m is None:raise LabError('Supported call: EXEC dbo.ProcedureName @Name=N\'Ali\', @ID=1;')
    name=object_name(m.group(1));rest=m.group(2).strip()
    _catalog(db)
    row=db.connection.execute('SELECT params_json,payload FROM __lab_modules WHERE kind=? AND name=?',('PROCEDURE',name)).fetchone()
    if row is None:raise LabError(f'Procedure {name} was not found. Run CREATE PROCEDURE first.')
    params=json.loads(row[0]);statements=json.loads(row[1]);args=_arguments(rest,params)
    columns=[];rows=[];affected=0
    try:
        with db.connection:
            for statement in statements:
                cursor=db.connection.execute(statement,args)
                if cursor.description:
                    columns=[x[0] for x in cursor.description]
                    data=cursor.fetchmany(501)
                    rows=[tuple(r) for r in data[:500]]
                else:
                    affected+=max(0,cursor.rowcount)
    except sqlite3.Error as exc:
        raise LabError(f'Procedure {name} failed and its changes were rolled back: {exc}') from exc
    return columns,rows,(f'EXEC {name}: {affected} row(s) modified; {len(rows)} result row(s). '
                         'Educational subset, not the SQL Server stored procedure engine.')


def drop_module(db,sql:str)->str:
    m=re.fullmatch(r'DROP\s+(VIEW|PROC(?:EDURE)?|FUNCTION)\s+('+_QUALIFIED+r')',sql.strip().rstrip(';'),re.I)
    if m is None:raise LabError('Unsupported DROP routine syntax.')
    kind=m.group(1).upper();name=object_name(m.group(2))
    if kind=='VIEW':
        try:
            with db.connection: db.connection.execute(f'DROP VIEW {q(name)}')
        except sqlite3.Error as exc:raise LabError(f'Unable to drop view {name}: {exc}') from exc
        return f'Dropped SQLite view {name}.'
    kind='PROCEDURE' if kind.startswith('PROC') else 'FUNCTION'
    _catalog(db)
    original=db.connection.execute('SELECT params_json FROM __lab_modules WHERE kind=? AND name=?',(kind,name)).fetchone()
    if original is None:
        raise LabError(f'{kind.title()} {name} does not exist.')
    with db.connection:
        db.connection.execute('DELETE FROM __lab_modules WHERE kind=? AND name=?',(kind,name))
    if kind=='FUNCTION':
        # Explicitly unregister the old callable on the active connection.
        db.connection.create_function(name,len(json.loads(original[0])),None)
    return f'Dropped educational {kind.lower()} {name}.'


def register_functions(db):
    """Rehydrate persisted educational scalar functions when reopening a DB."""
    existing=db.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='__lab_modules'").fetchone()
    if not existing:return
    for name,params_json,payload in db.connection.execute('SELECT name,params_json,payload FROM __lab_modules WHERE kind=?',('FUNCTION',)):
        params=json.loads(params_json);expression=json.loads(payload)['expr']
        keys=[p['name'] for p in params]
        def callback(*args,_keys=keys,_expression=expression):
            # Each callback is a single scalar SELECT; SQL queries and writes are disallowed.
            return db.connection.execute('SELECT '+_expression,dict(zip(_keys,args))).fetchone()[0]
        db.connection.create_function(name,len(params),callback,deterministic=True)
