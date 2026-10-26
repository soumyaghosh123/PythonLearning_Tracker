"""Eclipse builds never go through javac or `java` in a way the agent can see (the JDT compiler
runs inside Eclipse), so they are found by scanning workspaces for fresh .class files instead.

A .java file whose .class file is newer than the last scan counts as one build. A class file
containing "Unresolved compilation problem" is a build with errors that Eclipse ran anyway.
"""

import datetime as dt
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import settings

PREFS_NAME = "org.eclipse.ui.ide.prefs"
SKIP_DIRS = {".metadata", ".git", "node_modules"}
ERROR_MARKER = b"Unresolved compilation problem"
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "f": "\f"}


def _unescape(value):
    """Java .properties unescaping: \\n, \\t, \\uXXXX, and \\x for any other character x."""
    def repl(m):
        c = m.group(1)
        if c[0] == "u" and len(c) == 5:
            return chr(int(c[1:], 16))
        return _ESCAPES.get(c, c)
    return re.sub(r"\\(u[0-9a-fA-F]{4}|.)", repl, value, flags=re.S)


def parse_recent(text):
    """The workspace paths (as written, not checked for existence) in a prefs file's text."""
    for line in text.splitlines():
        if line.startswith("RECENT_WORKSPACES="):
            return [p for p in _unescape(line.split("=", 1)[1]).split("\n") if p.strip()]
    return []


def recent_workspaces(home=None, installs=None):
    """Existing workspaces from every Eclipse prefs file we can find, without repeats."""
    home = Path.home() if home is None else Path(home)
    settings_dirs = [p.parent for p in home.glob(f".eclipse/**/configuration/.settings/{PREFS_NAME}")]
    settings_dirs += [Path(i) / "configuration" / ".settings" for i in installs or []]
    settings_dirs += list(home.glob("eclipse/*/eclipse/configuration/.settings"))
    found = []
    for folder in settings_dirs:
        try:
            text = (folder / PREFS_NAME).read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        for value in parse_recent(text):
            path = Path(value)
            if path.is_dir() and path not in found:
                found.append(path)
    return found


def project_dirs(workspace):
    """Folders with a .classpath at depth 1 or 2 (Eclipse allows projects one level down)."""
    workspace = Path(workspace)
    found = []
    try:
        level1 = sorted(d for d in workspace.iterdir() if d.is_dir() and d.name not in SKIP_DIRS)
        for d in level1:
            if (d / ".classpath").is_file():
                found.append(d)
        for d in level1:
            if d in found:
                continue
            found += [c for c in sorted(d.iterdir())
                      if c.is_dir() and c.name not in SKIP_DIRS and (c / ".classpath").is_file()]
    except OSError:
        pass
    return found


def src_and_output(project):
    """(source folders, output folder) from the project's .classpath, with Eclipse's defaults."""
    project = Path(project)
    sources, output = [], None
    try:
        root = ET.parse(project / ".classpath").getroot()
        for entry in root.iter("classpathentry"):
            path, kind = entry.get("path", ""), entry.get("kind")
            if kind == "src" and path and not path.startswith("/") and entry.get("combineaccessrules") is None:
                sources.append(project / path)
            elif kind == "output" and path:
                output = project / path
    except (OSError, ET.ParseError):
        pass
    return sources or [project / "src"], output or project / "bin"


def _norm(path):
    return os.path.normpath(str(path)).replace("/", "\\").lower().rstrip("\\")


def is_excluded_factory(lang_config):
    """Same rule as the Java agent: bare names match as folder names, paths as a folder prefix."""
    from languages.java.pack import BUILTIN_EXCLUDES  # here: pack imports this module
    names = list(BUILTIN_EXCLUDES) + list(lang_config.get("exclude_folders", [])) + [str(settings.TRACKER_DIR)]
    rules = []
    for name in names:
        s = name.strip().replace("/", "\\").lower()
        s = s.rstrip("\\")
        if s:
            rules.append((s, "\\" in s or ":" in s))

    def is_excluded(path):
        p = _norm(os.path.abspath(path))
        for s, is_path in rules:
            if (p == s or p.startswith(s + "\\")) if is_path else ("\\" + s + "\\") in p:
                return True
        return False
    return is_excluded


def _read_state(data_dir):
    try:
        state = json.loads((Path(data_dir) / "eclipse_seen.json").read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_state(data_dir, state):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / "eclipse_seen.json").write_text(json.dumps(state), encoding="utf-8")


def exclusions_changed(data_dir, lang_config):
    return list(lang_config.get("exclude_folders", [])) != _read_state(data_dir).get("exclude", [])


def _java_files(source_dir):
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name.lower().endswith(".java"):
                yield Path(root) / name


def scan_workspaces(workspaces, data_dir, runs, is_excluded):
    """Record each source whose class file is new since the last scan. Returns the new run entries.

    data_dir is the per-language data folder."""
    data_dir = Path(data_dir)
    started = time.time()  # taken before the walk so a build during the scan is caught next time
    state = _read_state(data_dir)
    last_scan = state.get("last_scan", 0)
    shas = set(state.get("shas", []))
    shas |= {f.get("sha") for run in runs for f in run.get("files", [])}

    new = []
    for workspace in workspaces:
        for project in project_dirs(workspace):
            sources, output = src_and_output(project)
            for source_dir in sources:
                for java in _java_files(source_dir):
                    try:
                        cls = output / java.relative_to(source_dir).with_suffix(".class")
                        mtime = cls.stat().st_mtime
                        if mtime <= last_scan or is_excluded(java):
                            continue
                        raw = java.read_bytes()
                        # Compiler errors are recorded by the marker Eclipse writes into the class file.
                        marker_count = cls.read_bytes().count(ERROR_MARKER)
                    except OSError:
                        continue
                    sha = hashlib.sha256(raw).hexdigest()[:16]
                    if sha in shas:
                        continue
                    shas.add(sha)
                    snaps = data_dir / "snapshots"
                    snaps.mkdir(parents=True, exist_ok=True)
                    snap = snaps / (sha + ".java")
                    if not snap.exists():
                        snap.write_bytes(raw)
                    new.append({
                        "time": dt.datetime.fromtimestamp(mtime).isoformat(timespec="seconds"),
                        "file": str(java),
                        "status": "compile_error" if marker_count else "compiled",
                        "error": None,
                        "error_count": marker_count or None,
                        "duration": 0,
                        "source": "eclipse",
                        "files": [{"file": str(java), "sha": sha}],
                    })

    if new:
        with open(data_dir / "runs.jsonl", "a", encoding="utf-8") as f:
            for entry in new:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    state["last_scan"] = started
    state["shas"] = sorted(shas)
    _write_state(data_dir, state)
    return new


def prune_excluded(data_dir, is_excluded, exclude_folders=None):
    """Drop logged runs of now-excluded files, and snapshots nothing refers to any more.

    With exclude_folders, only runs when that list differs from the one stored last time, and
    then stores it. Returns the number of entries removed."""
    data_dir = Path(data_dir)
    state = _read_state(data_dir)
    if exclude_folders is not None:
        if list(exclude_folders) == state.get("exclude", []):
            return 0
        state["exclude"] = list(exclude_folders)
    removed = 0
    runs_path = data_dir / "runs.jsonl"
    if runs_path.exists():
        kept_lines, referenced = [], set()
        for line in runs_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                file = entry.get("file") or ""
            except (ValueError, AttributeError):
                kept_lines.append(line)  # not ours to judge
                continue
            if file and is_excluded(Path(file)):
                removed += 1
                continue
            kept_lines.append(line)
            files = entry.get("files")
            if files is None and entry.get("sha"):
                files = [{"sha": entry["sha"]}]
            referenced |= {f.get("sha") for f in files or []}
        if removed:
            runs_path.write_text("".join(l + "\n" for l in kept_lines), encoding="utf-8")
            for snap in (data_dir / "snapshots").glob("*"):
                if snap.stem not in referenced:
                    try:
                        snap.unlink()
                    except OSError:
                        pass
            # Their shas may be built again later (from an un-excluded folder), so forget them.
            state["shas"] = sorted(s for s in state.get("shas", []) if s in referenced)
    if exclude_folders is not None or removed:
        _write_state(data_dir, state)
    return removed
