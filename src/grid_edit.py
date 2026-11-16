"""Type-aware conversion for editable table cells (without SQL concatenation)."""
from __future__ import annotations
from model_ext import validate_value

def cell_value(db, table: str, name: str, raw: str):
    """NULL sets SQL NULL; a backslash before NULL enters the literal word."""
    if raw.strip().upper() == 'NULL':
        return None
    if raw == r'\NULL':
        raw = 'NULL'
    return validate_value(db, table, name, raw)
