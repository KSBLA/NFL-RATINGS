"""Compatibility entry point. Original application code is preserved in ordered sections.
Do not move execution order or run sections independently: they share the app namespace.
"""
from pathlib import Path as _Path
_SECTION_DIR = _Path(__file__).resolve().parent / "app_sections"
for _section_file in sorted(_SECTION_DIR.glob("*_app_part.py")):
    _section_source = _section_file.read_text(encoding="utf-8")
    exec(compile(_section_source, str(_section_file), "exec"), globals())
del _section_file, _section_source, _SECTION_DIR, _Path
