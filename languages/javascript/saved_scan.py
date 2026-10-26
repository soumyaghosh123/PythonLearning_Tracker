"""Saved-file tracking for JavaScript: browser code never goes through Node, so
.html pages (and the .js files they load) are recorded when they are saved.
With the Node hook off, every .js file is recorded this way too."""

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

import settings
from languages.javascript.analyzer import analyze_js, extract_scripts

SKIP_DIRS = {"node_modules", ".git", ".vscode", "dist", "build"}
SCRIPT_EXTS = {".js", ".mjs", ".cjs"}


def _read(path):
    """(raw bytes, text) of a source file; text decodes like the rest of the tracker (R4)."""
    raw = Path(path).read_bytes()
    return raw, raw.decode("utf-8-sig", errors="replace")


def _syntax_ok(path, text):
    if str(path).lower().endswith(".html"):
        text = extract_scripts(text)[0]
    return analyze_js(text, str(path))["syntax_ok"]


def _local_src(src):
    """A relative src without query/hash, or None for URLs and absolute paths."""
    src = src.strip().split("#")[0].split("?")[0]
    if not src or src.startswith(("/", "\\")) or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", src):
        return None
    return src


def _candidates(code_folder, hook_on):
    tracker = os.path.normcase(str(settings.TRACKER_DIR))
    html_files, js_files = [], []
    for root, dirs, files in os.walk(code_folder):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS
                   and os.path.normcase(os.path.abspath(os.path.join(root, d))) != tracker]
        for name in files:
            full = Path(root) / name
            ext = full.suffix.lower()
            if ext == ".html":
                html_files.append(full)
            elif ext == ".js":
                js_files.append(full)
    found = list(html_files)
    for html in html_files:
        try:
            srcs = extract_scripts(_read(html)[1])[1]
        except OSError:
            continue
        for src in srcs:
            rel = _local_src(src)
            if rel is None:
                continue
            target = (html.parent / rel)
            if target.suffix.lower() in SCRIPT_EXTS and target.is_file():
                found.append(target)
    if not hook_on:
        found.extend(js_files)
    seen, unique = set(), []
    for path in found:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def collect_saved(lang_config, data_dir, runs, hook_on):
    """Record each new version of browser code (and of .js, hook off) as a 'saved' run.

    data_dir is the per-language data folder. Returns the new run entries."""
    data_dir = Path(data_dir)
    seen_path = data_dir / "saved_seen.json"
    try:
        seen = set(json.loads(seen_path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        seen = set()
    run_shas = {f.get("sha") for run in runs for f in run.get("files", [])}

    new = []
    for path in _candidates(lang_config["code_folder"], hook_on):
        try:
            raw, text = _read(path)
            mtime = path.stat().st_mtime
        except OSError:
            continue
        sha = hashlib.sha256(raw).hexdigest()[:16]
        if sha in seen or sha in run_shas:
            continue
        ok = _syntax_ok(path, text)
        snaps = data_dir / "snapshots"
        snaps.mkdir(parents=True, exist_ok=True)
        snap = snaps / (sha + path.suffix.lower())
        if not snap.exists():
            snap.write_bytes(raw)
        new.append({
            "time": dt.datetime.fromtimestamp(mtime).isoformat(timespec="seconds"),
            "file": str(path),
            "status": "saved" if ok else "error",
            "error": None if ok else "SyntaxError",
            "error_count": None,
            "duration": 0,
            "source": "saved",
            "files": [{"file": str(path), "sha": sha}],
        })
        seen.add(sha)

    if new:
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / "runs.jsonl", "a", encoding="utf-8") as f:
            for entry in new:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        seen_path.write_text(json.dumps(sorted(seen)), encoding="utf-8")
    return new
