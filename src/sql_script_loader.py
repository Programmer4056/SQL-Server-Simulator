"""Safely load SQL text files for review before executing a documented subset.

File selection and execution confirmation live in the Qt application; importing
this module never runs SQL.  User-selected files are not automatically trusted.
"""
from __future__ import annotations
from pathlib import Path
from core import LabError

MAX_SCRIPT_BYTES = 10 * 1024 * 1024


def read_sql_script(path: str | Path, max_bytes: int = MAX_SCRIPT_BYTES) -> str:
    path = Path(path)
    if path.suffix.lower() not in ('.sql', '.txt'):
        raise LabError('Choose a .sql or .txt script file.')
    if path.stat().st_size > max_bytes:
        raise LabError('SQL script is over 10 MB. Split it into smaller batches.')
    with path.open('rb') as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise LabError('SQL script is over 10 MB. Split it into smaller batches.')
    try:
        if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            text = raw.decode('utf-16')
        else:
            text = raw.decode('utf-8-sig')
    except UnicodeError as exc:
        raise LabError('Unsupported encoding. Save the script as UTF-8 or UTF-16.') from exc
    if '\x00' in text:
        raise LabError('This file is not a plain-text SQL script.')
    if not text.strip():
        raise LabError('The selected SQL script is empty.')
    return text
