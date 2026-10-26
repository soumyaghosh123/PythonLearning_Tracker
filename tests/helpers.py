"""Shared test setup: isolated PYTRACKER_HOME and import path."""

import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

TRACKER = Path(__file__).resolve().parent.parent
if str(TRACKER) not in sys.path:
    sys.path.insert(0, str(TRACKER))

HOME = Path(tempfile.mkdtemp(prefix="pytracker_test_"))
os.environ["PYTRACKER_HOME"] = str(HOME)


def fresh_home():
    """Empty the test home and reload modules that cache paths."""
    for child in HOME.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink()
    import settings
    importlib.reload(settings)
    return HOME


def write_runs(path, entries):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
