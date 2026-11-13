"""SQL Server-compatible teaching export. NOT a native .bak file.

Converts a supported subset of SQLite project schema/data to T-SQL. User-selected
server version is informational: all emitted syntax deliberately targets 2012+.
This is not a substitute for testing the result in the chosen SQL Server instance.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import math
import re
from core import LabDatabase, LabError, identifier

TARGET_VERSIONS = ('2012','2014','2016','2017','2019','2022','2025')
EXPORT_MODES = ('schema', 'data', 'both')

def brackets(name: str) -> str:
    return '[' + identifier(name).replace(']', ']]') + ']'

def fq(name: str) -> str:
    return '[dbo].'+brackets(name)

def sqltype(logical: str) -> str:
    typ = logical.strip().upper()
    equivalents = {
        'INTEGER':'INT', 'TEXT':'NVARCHAR(MAX)', 'BOOLEAN':'BIT',
        'BLOB':'VARBINARY(MAX)', 'NUMERIC':'DECIMAL(18,4)',
        'DATE':'DATE', 'DATETIME':'DATETIME2', 'REAL':'REAL',
        'DOUBLE':'FLOAT', 'TINYINT':'TINYINT', 'INT':'INT', 'BIGINT':'BIGINT',
        'SMALLINT':'SMALLINT', 'FLOAT':'FLOAT', 'BIT':'BIT',
        'UNIQUEIDENTIFIER':'UNIQUEIDENTIFIER', 'MONEY':'MONEY',
        'SMALLMONEY':'SMALLMONEY', 'SMALLDATETIME':'SMALLDATETIME',
    }
    if typ in equivalents:
        return equivalents[typ]
    if re.fullmatch(r'(N?VARCHAR|N?CHAR)\((?:\d+|MAX)\)',typ):
        return typ
    if re.fullmatch(r'(VARBINARY|BINARY)\((?:\d+|MAX)\)',typ):
        return typ
    if re.fullmatch(r'(DECIMAL|NUMERIC)\(\d+(?:,\s*\d+)?\)',typ):
        return typ
    if re.fullmatch(r'(DATETIME2|TIME)\(\d\)',typ):
        return typ
    raise LabError(f'Cannot export SQL type {typ!r} to SQL Server. Choose a supported SQL type.')

def literal(value) -> str:
    if value is None:
        return 'NULL'
    if isinstance(value, (bytes,bytearray,memoryview)):
        return '0x'+bytes(value).hex().upper()
    if isinstance(value,bool):
        return '1' if value else '0'
    if isinstance(value,int):
        return str(value)
    if isinstance(value,float):
        if not math.isfinite(value):
            raise LabError('NaN/Infinity cannot be scripted to SQL Server safely.')
        return repr(value)
    return "N'"+str(value).replace("'","''")+"'"

def _fk_groups(db:LabDatabase, child:str):
    groups={}
    for r in db.foreign_keys(child):
        groups.setdefault(r['id'],[]).append(r)
    return [sorted(rows,key=lambda x:x['seq']) for rows in groups.values()]

def make_script(db:LabDatabase,tables:list[str],mode:str='both',version:str='2022',
                database_name:str|None=None) -> str:
    if mode not in EXPORT_MODES:
        raise LabError('Choose Schema, Data, or Schema and Data.')
    if version not in TARGET_VERSIONS:
        raise LabError('Unsupported target SQL Server version.')
    known=set(db.tables())
    if not tables or len(tables)!=len(set(tables)) or any(t not in known for t in tables):
        raise LabError('Select one or more valid, unique tables.')
    if database_name is not None:
        identifier(database_name)
    selection=set(tables)
    ordered=sorted(selection,key=str.casefold)
    generated=datetime.now().strftime('%Y-%m-%d %H:%M')
    out=[f'-- SQL Server Simulator v0.4 | Designed and developed by Ali Sayyadi',
         f'-- Exported: {generated} | Target SQL Server: {version} | Scope: {mode}',
         '-- Educational T-SQL script export, NOT a SQL Server .bak backup.',
         '-- Review and test on a non-production SQL Server instance before deployment.',
         '-- Only supported table columns, primary keys, foreign keys and data are exported.',
         '-- User-created triggers, views, procedures, indexes, collations and permissions are NOT exported.',
         'SET NOCOUNT ON;', 'GO', '']
    if database_name and mode!='data':
        out.extend([f'IF DB_ID(N{literal(database_name)[1:]}) IS NULL',
                    f'    EXEC(N\'CREATE DATABASE {brackets(database_name)}\');','GO',
                    f'USE {brackets(database_name)};', 'GO', ''])
    elif database_name:
        out.extend([f'USE {brackets(database_name)};', 'GO', ''])
    if mode in ('schema','both'):
        for table in ordered:
            cols=db.columns(table)
            keys=sorted((c for c in cols if c['pk']),key=lambda c:c['pk'])
            ident=db.identity_settings(table)
            definitions=[]
            for c in cols:
                typ=sqltype(db.logical_type(table,c['name']))
                column=brackets(c['name'])+' '+typ
                if ident and ident['column_name']==c['name']:
                    column+=f" IDENTITY({ident['seed']},{ident['increment']})"
                column+=' NOT NULL' if c['notnull'] or c['pk'] else ' NULL'
                # Only simple literal defaults are supported, not SQLite functions.
                default=c['dflt_value']
                if default is not None and not (ident and ident['column_name']==c['name']):
                    if re.fullmatch(r"(?:NULL|-?\d+(?:\.\d+)?|'(?:[^']|'')*')",str(default),re.I):
                        column+=' DEFAULT '+str(default)
                    else:
                        out.append(f'-- NOTICE: Unsupported default on {table}.{c["name"]} omitted: {default}')
                definitions.append('    '+column)
            if keys:
                pkcols=', '.join(brackets(c['name']) for c in keys)
                definitions.append(f'    CONSTRAINT {brackets("PK_"+table)} PRIMARY KEY ({pkcols})')
            out.append(f'CREATE TABLE {fq(table)} (\n'+',\n'.join(definitions)+'\n);')
            out.extend(['GO',''])
    if mode in ('data','both'):
        for table in ordered:
            cols=[c['name'] for c in db.columns(table)]
            ident=db.identity_settings(table)
            cursor=db.connection.execute('SELECT * FROM "'+table+'"')
            count=0
            for row in cursor:
                if count==0 and ident:
                    out.append(f'SET IDENTITY_INSERT {fq(table)} ON;')
                out.append('INSERT INTO '+fq(table)+' ('+', '.join(brackets(c) for c in cols)+') VALUES ('+
                           ', '.join(literal(v) for v in row)+');')
                count+=1
            if count and ident:
                out.append(f'SET IDENTITY_INSERT {fq(table)} OFF;')
            out.append(f'-- {table}: {count} row(s) scripted')
            out.extend(['GO',''])
    if mode in ('schema','both'):
        # Add FKs after all CREATE TABLE and INSERT blocks to avoid circular FK/order problems.
        for child in ordered:
            for ix,group in enumerate(_fk_groups(db,child),1):
                parent=group[0]['table']
                if parent not in selection:
                    out.append(f'-- FK from {child} to {parent} omitted: parent table was not selected.')
                    continue
                fromcols=', '.join(brackets(r['from']) for r in group)
                tocols=', '.join(brackets(r['to']) for r in group)
                name=brackets('FK_'+child+'_'+parent+'_'+str(ix))
                out.append(f'ALTER TABLE {fq(child)} WITH CHECK ADD CONSTRAINT {name} FOREIGN KEY ({fromcols}) REFERENCES {fq(parent)} ({tocols});')
                out.append('GO')
    out.append('-- End of SQL Server-compatible educational script.')
    return '\n'.join(out)+'\n'

def export_script(db:LabDatabase,target:str|Path,tables:list[str],mode='both',version='2022',database_name=None) -> None:
    text=make_script(db,tables,mode,version,database_name)
    dest=Path(target)
    if dest.suffix.lower()!='.sql':
        raise LabError('Export file must have the .sql extension.')
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(text,encoding='utf-8-sig')
