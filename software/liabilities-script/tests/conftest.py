"""Pytest config: put `liabilities-script/` on sys.path so tests can import
`structure`, `motifs`, etc. without a package install. The script directory
is not a Python package by itself (no top-level __init__), so this bootstrap
mirrors what the Docker entrypoint does at runtime."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
