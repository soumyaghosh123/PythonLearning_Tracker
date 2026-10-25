"""Shared file paths and helpers for loading/saving the tracker's JSON files."""

import json
import os
from pathlib import Path

TRACKER_DIR = Path(__file__).resolve().parent

# Everything the tracker writes lives under HOME. It defaults to this folder;
# the PYTRACKER_HOME environment variable can point it elsewhere (handy for testing).
HOME = Path(os.environ.get("PYTRACKER_HOME", TRACKER_DIR))

CONFIG_PATH = HOME / "config.json"
DATA_DIR = HOME / "data"
RUNS_PATH = DATA_DIR / "runs.jsonl"          # one line per script run (written by the run logger)
SNAPSHOT_DIR = DATA_DIR / "snapshots"        # copy of each version of code that was run
EMAIL_STATE_PATH = DATA_DIR / "email_state.json"
DASHBOARD_PATH = HOME / "dashboard.html"
PLAN_PATH = HOME / "plan.html"
CURRICULUM_PATH = TRACKER_DIR / "curriculum.json"

PASSWORD_ENV_VAR = "PYTRACKER_GMAIL_APP_PASSWORD"
TASK_NAME = "PythonLearningTracker"

DEFAULT_CONFIG = {
    "learner_name": "",
    "start_date": "",
    "plan": "standard",
    "code_folder": str(TRACKER_DIR.parent),
    "email": {
        "enabled": False,
        "to": [],
        "sender": "",
        "send_days": ["Monday", "Thursday"],
        "send_time": "08:00",
    },
    "alerts": {
        "stuck_enabled": True,
        "reminder_every_days": 3,
        "inactive_after_days": 5,
    },
}


def load_json(path, default=None):
    """Read a JSON file, or return `default` if it doesn't exist yet."""
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config():
    config = load_json(CONFIG_PATH)
    if config is None:
        raise SystemExit("No config.json found. Run:  python tracker\\setup.py")
    # Fill in any settings missing from older config files.
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for key, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def load_curriculum():
    return load_json(CURRICULUM_PATH)
