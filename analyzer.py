"""Command-line front end: analyse one source file with the matching language pack.

Try it:  python tracker/analyzer.py welcome.py
"""

import sys
from pathlib import Path

from languages import pack_for_path
# Kept importable here so older callers (track.py) keep working.
from languages.python.analyzer import analyze_source  # noqa: F401


def main(argv):
    if len(argv) != 2:
        raise SystemExit("Usage: python analyzer.py <file.py|.java|.js|.html>")
    path = Path(argv[1])
    pack = pack_for_path(path)
    if pack is None:
        raise SystemExit(f"Unsupported file type: {path.suffix}")
    result = pack.analyze(path.read_text(encoding="utf-8-sig", errors="replace"), str(path))
    for key, value in result.items():
        print(f"{key:>11}: {value}")


if __name__ == "__main__":
    main(sys.argv)
