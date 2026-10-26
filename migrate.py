"""One-time upgrade of the old Python-only data layout to per-language folders.

Safe to call on every start: each step does nothing once it has been applied.
"""

import json
import os
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


def _convert_file(path):
    """Append the converted lines of an old runs file to the Python runs file, then remove it.

    Lines that cannot be converted are kept verbatim in runs.corrupt.jsonl.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    good, bad = [], []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            old = json.loads(line)
            if not isinstance(old, dict):
                raise TypeError("run entry is not an object")
            good.append(json.dumps(convert_entry(old)) + "\n")
        except (ValueError, TypeError):
            bad.append(line + "\n")
    out_dir = settings.lang_dir("python")
    out_dir.mkdir(parents=True, exist_ok=True)
    # One write per file, so an interruption cannot leave half of it behind.
    for name, lines in (("runs.jsonl", good), ("runs.corrupt.jsonl", bad)):
        if lines:
            with (out_dir / name).open("a", encoding="utf-8") as f:
                f.write("".join(lines))
    try:
        path.unlink()
    except OSError:
        # Never leave content that would be appended again on the next start.
        path.write_text("", encoding="utf-8")


def _migrate_runs():
    old_path = settings.DATA_DIR / "runs.jsonl"
    pending = settings.DATA_DIR / "runs.jsonl.migrating"
    changed = False
    # A leftover from an interrupted run is processed first, exactly once.
    if pending.exists():
        _convert_file(pending)
        changed = True
    if old_path.exists():
        try:
            # Atomic rename: lines the old logger writes afterwards go to a fresh file.
            os.replace(old_path, pending)
        except OSError:
            return changed
        _convert_file(pending)
        changed = True
    return changed


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
