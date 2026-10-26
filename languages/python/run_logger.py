"""Python Learning Tracker: run logger.

setup.py copies this file into Python's user site-packages folder as
usercustomize.py. Python imports usercustomize automatically every time it
starts, so this code notices every script you run (VS Code's Run button,
the terminal, anything) and logs it, as long as the script is inside your
code folder.

For each run it records: time, file, success / error / stopped, error type,
how long it ran, and a snapshot of the code so it can be analysed later.

To stop logging, delete usercustomize.py (or run: python tracker\\setup.py --uninstall).
Every step is wrapped in try/except so the logger can never break your scripts.
"""

import sys

# setup.py fills these in when it installs the logger.
DATA_DIR = r"__DATA_DIR__"
CODE_FOLDER = r"__CODE_FOLDER__"
TRACKER_DIR = r"__TRACKER_DIR__"


def _script_path():
    import os

    candidates = [sys.argv[0] if sys.argv else ""]
    main = sys.modules.get("__main__")
    candidates.append(getattr(main, "__file__", "") or "")
    for path in candidates:
        if path.endswith(".py") and os.path.isfile(path):
            return os.path.abspath(path)
    return None


def _is_tracked(path):
    import os

    folder = os.path.normcase(os.path.abspath(CODE_FOLDER)) + os.sep
    tracker = os.path.normcase(os.path.abspath(TRACKER_DIR)) + os.sep
    path = os.path.normcase(path)
    return path.startswith(folder) and not path.startswith(tracker)


def _record(started, error):
    import datetime
    import hashlib
    import json
    import os
    import time

    path = _script_path()
    if not path or not _is_tracked(path):
        return

    with open(path, "rb") as f:
        code = f.read()
    sha = hashlib.sha256(code).hexdigest()[:16]

    snapshots = os.path.join(DATA_DIR, "snapshots")
    os.makedirs(snapshots, exist_ok=True)
    snapshot = os.path.join(snapshots, sha + ".py")
    if not os.path.exists(snapshot):
        with open(snapshot, "wb") as f:
            f.write(code)

    if error is None:
        status = "success"
    elif error == "KeyboardInterrupt":
        status = "stopped"
    else:
        status = "error"

    entry = {
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "file": path,
        "status": status,
        "error": error,
        "duration": round(time.time() - started, 2),
        "sha": sha,
    }
    with open(os.path.join(DATA_DIR, "runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _install():
    import atexit
    import time

    started = time.time()
    state = {"error": None}
    previous_hook = sys.excepthook

    def excepthook(exc_type, exc, tb):
        state["error"] = exc_type.__name__
        previous_hook(exc_type, exc, tb)

    def on_exit():
        try:
            _record(started, state["error"])
        except Exception:
            pass

    sys.excepthook = excepthook
    atexit.register(on_exit)


try:
    _install()
except Exception:
    pass
