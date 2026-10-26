"""Shared file paths and helpers for loading/saving the tracker's JSON files."""

import datetime as dt
import json
import os
from pathlib import Path

TRACKER_DIR = Path(__file__).resolve().parent

# Everything the tracker writes lives under HOME. It defaults to this folder;
# the PYTRACKER_HOME environment variable can point it elsewhere (handy for testing).
HOME = Path(os.environ.get("PYTRACKER_HOME", TRACKER_DIR))

CONFIG_PATH = HOME / "config.json"
DATA_DIR = HOME / "data"
EMAIL_STATE_PATH = DATA_DIR / "email_state.json"
DASHBOARD_PATH = HOME / "dashboard.html"
PLAN_PATH = HOME / "plan.html"

PASSWORD_ENV_VAR = "PYTRACKER_GMAIL_APP_PASSWORD"
TASK_NAME = "LearningTracker"
OLD_TASK_NAME = "PythonLearningTracker"

DEFAULT_LANGUAGE = {
    "python": {
        "enabled": False,
        "start_date": "",
        "plan": "standard",
        "code_folder": r"C:\Python",
    },
    "java": {
        "enabled": False,
        "start_date": "",
        "plan": "standard",
        "code_folder": os.path.join(os.path.expanduser("~"), "eclipse-workspace"),
        "extra_workspaces": [],
        "exclude_folders": [],
    },
    "javascript": {
        "enabled": False,
        "start_date": "",
        "plan": "standard",
        "code_folder": r"C:\JavaScript",
    },
}

DEFAULT_CONFIG = {
    "learner_name": "",
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
    "languages": DEFAULT_LANGUAGE,
}


def lang_dir(key):
    return DATA_DIR / key


def runs_path(key):
    return lang_dir(key) / "runs.jsonl"          # one line per run (written by the hook/agent/scan)


def snapshot_dir(key):
    return lang_dir(key) / "snapshots"           # copy of each version of code that was run


def enabled_languages(config):
    """Keys of enabled languages, in registry order."""
    from languages import all_packs
    langs = config.get("languages", {})
    return [p.key for p in all_packs() if langs.get(p.key, {}).get("enabled")]


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
    import migrate  # imported here: migrate itself imports settings
    migrate.migrate_if_needed()
    config = load_json(CONFIG_PATH)
    if config is None:
        raise SystemExit("No config.json found. Run:  python tracker\\setup.py")
    # Fill in any settings missing from older config files.
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for key, value in config.items():
        if key == "languages" and isinstance(value, dict):
            for lang, block in value.items():
                if isinstance(block, dict) and isinstance(merged["languages"].get(lang), dict):
                    merged["languages"][lang].update(block)
                else:
                    merged["languages"][lang] = block
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def log_line(text):
    """Print a timestamped line and append it to data/send_report.log."""
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {text}"
    print(line)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "send_report.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")
