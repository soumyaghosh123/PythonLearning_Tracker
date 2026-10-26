"""One-time upgrade of the old Python-only data layout to per-language folders.

Safe to call on every start: each step does nothing once it has been applied.
"""

import json
import shutil

import settings

OLD_CONFIG_KEYS = ("start_date", "plan", "code_folder")


def convert_entry(old):
    """Turn an old run entry ({"sha": s, ...}) into the multi-file shape."""
    if "files" in old:
        return old
    entry = {k: v for k, v in old.items() if k != "sha"}
    sha = old.get("sha")
    entry["files"] = [{"file": old.get("file"), "sha": sha}] if sha else []
    entry["source"] = "hook"
    return entry


def _migrate_config():
    config = settings.load_json(settings.CONFIG_PATH)
    if not isinstance(config, dict):
        return False
    if "languages" in config and not any(k in config for k in OLD_CONFIG_KEYS):
        return False
    if "languages" not in config:
        block = {"enabled": True}
        for key in OLD_CONFIG_KEYS:
            if key in config:
                block[key] = config[key]
        config["languages"] = {"python": block}
    for key in OLD_CONFIG_KEYS:
        config.pop(key, None)
    settings.save_json(settings.CONFIG_PATH, config)
    return True


def _migrate_runs():
    old_path = settings.DATA_DIR / "runs.jsonl"
    if not old_path.exists():
        return False
    new_path = settings.runs_path("python")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    with old_path.open(encoding="utf-8") as src, new_path.open("a", encoding="utf-8") as dst:
        for line in src:
            line = line.strip()
            if not line:
                continue
            try:
                entry = convert_entry(json.loads(line))
            except ValueError:
                continue  # skip a corrupt line rather than lose the rest
            dst.write(json.dumps(entry) + "\n")
    old_path.unlink()
    return True


def _migrate_snapshots():
    old_dir = settings.DATA_DIR / "snapshots"
    if not old_dir.is_dir():
        return False
    new_dir = settings.snapshot_dir("python")
    new_dir.mkdir(parents=True, exist_ok=True)
    for path in old_dir.iterdir():
        target = new_dir / path.name
        if not target.exists():
            shutil.move(str(path), str(target))
    try:
        old_dir.rmdir()  # only succeeds when empty
    except OSError:
        pass
    return True


def _migrate_email_state():
    state = settings.load_json(settings.EMAIL_STATE_PATH)
    if not isinstance(state, dict):
        return False
    if "alerts" not in state and "last_inactive_sent" not in state:
        return False
    languages = state.setdefault("languages", {})
    python = languages.setdefault("python", {})
    python.setdefault("alerts", state.pop("alerts", None) or {})
    python.setdefault("last_inactive_sent", state.pop("last_inactive_sent", None))
    state.pop("alerts", None)
    state.pop("last_inactive_sent", None)
    settings.save_json(settings.EMAIL_STATE_PATH, state)
    return True


def migrate_if_needed():
    """Upgrade the old layout in place. Returns True if anything changed."""
    config_changed = _migrate_config()
    changed = config_changed
    for step in (_migrate_runs, _migrate_snapshots, _migrate_email_state):
        changed = step() or changed
    if config_changed:
        print("Re-run setup.py to update the Python run logger")
    return changed
