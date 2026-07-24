"""
conftest.py — pytest configuration for tests/test_repo_intel/.

Adds Pat-Code to sys.path so imports like `from repo_intel.x import y` work
without requiring the package to be installed.
"""

import sys
from pathlib import Path

# Pat-Code is the directory containing repo_intel/, agent/, tools/, etc.
_PAT_CODE = Path(__file__).parent.parent.resolve()
if str(_PAT_CODE) not in sys.path:
    sys.path.insert(0, str(_PAT_CODE))
