"""
conftest.py — Shared pytest fixtures and sys.path setup.

Adds Pat-Code/ to sys.path so all modules resolve correctly
without requiring the package to be installed in editable mode.
"""

import sys
from pathlib import Path

# Make "Pat-Code/" importable as the package root
_ROOT = Path(__file__).resolve().parent.parent  # repo root
_SRC  = _ROOT / "Pat-Code"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Also make the repo root available (for apply_patch, etc.)
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
