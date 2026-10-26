# Multi-language Learning Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track Python, Java and JavaScript learning side by side, each with its own course, capture method, progress, dashboard tab and email section.

**Architecture:** A shared engine (`track.py`, `dashboard.py`, `emailer.py`, `send_report.py`, `setup.py`) talks to one `LanguagePack` per language under `languages/<key>/`. Each pack owns its curriculum, analyser, run hook and extra-activity collector. The per-language report keeps today's report shape, so the dashboard and email code render each language with the code they already have.

**Tech Stack:** Python 3 standard library only (`ast`, `re`, `json`, `zipfile`, `unittest`, `subprocess`); Node.js CommonJS for the Node hook; Java 8 source for the agent (compiled by setup with the learner's `javac`); static HTML + Chart.js 4.4.1 from cdnjs (unchanged).

**Spec:** `docs/superpowers/specs/2026-10-25-multi-language-design.md`

## Global Constraints

- No third-party Python packages. No Node or Java libraries; the agent and the hook use only their platforms' built-ins.
- Hooks must never break a learner's program: every hook step sits inside `try/except`, `try/catch` or `catch (Throwable)`.
- Code never leaves the PC. Emails contain progress numbers, folder names and file names only.
- The tracker folder stays at `C:\Python\tracker`. `PYTRACKER_HOME` still redirects everything the tracker writes (the tests use it).
- Language keys are exactly `python`, `java`, `javascript`. Icons: 🐍, ☕, 🟨. Editors: VS Code, Eclipse, VS Code.
- Run statuses are exactly `success`, `error`, `stopped`, `compiled`, `compile_error`, `saved`. Sources are `hook`, `agent`, `javac`, `eclipse`, `saved`.
- `success` and `compiled` count toward topics, streak and the daily target. `saved` counts only when `syntax_ok` is true. Every status counts as activity for inactivity.
- Java exclusions (always): `Program Files`, `Program Files (x86)`, `Windows`, `AppData`, `.m2`, `.gradle`, `.p2`, `node_modules`, the tracker folder, and `languages.java.exclude_folders`.
- Default code folders: `C:\Python`, `%USERPROFILE%\eclipse-workspace`, `C:\JavaScript`.
- Scheduled task name: `LearningTracker`. Setup removes the old `PythonLearningTracker` task.
- Email sender display name: `Learning Tracker`. Dashboard title: `📚 <name>'s Learning Tracker`.
- Agent: compiled with `javac --release 8`. Its manifest has `Premain-Class: TrackerAgent`. Its shutdown hook gives up after 2 seconds.
- Match the existing code style: module docstrings, short comments on the "why", `snake_case`, f-strings, `pathlib`.

## Review Focus

1. **A learner runs Python with the old hook still installed after migrating.** New lines can land in the old `data/runs.jsonl`. The migration moves any leftover lines from there on every load, so nothing is lost. Tested in Task 2.
2. **Java source paths with spaces, quotes, backslashes or non-ASCII characters** (`C:\Users\Ana María\My "Test"\Main.java`). The agent's hand-written JSON must escape these so the line still parses. Tested in Task 9.
3. **Java files saved by Eclipse in Windows-1252 rather than UTF-8.** Reading snapshots must never crash: decode as UTF-8 with `errors="replace"`. Tested in Task 5.
4. **Large folders.** The Eclipse workspace `.metadata`, `node_modules`, `.git` and output folders must be skipped by the scans, so a refresh stays fast and doesn't pick up generated or dependency code. Tested in Tasks 8 and 10.
5. **Different start dates per language.** A Java compile before Java's `start_date` must not count, even if it's after Python's start date. Tested in Task 3.

---

## File structure

```
tracker/
├── analyzer.py              MODIFY → CLI only: picks a pack by extension
├── settings.py              MODIFY → new config shape, per-language paths
├── migrate.py               CREATE → one-time and leftover migration
├── track.py                 MODIFY → per-language reports + overall
├── dashboard.py             MODIFY → Overview + language tabs; plan tabs
├── emailer.py               MODIFY → multi-language progress, combined stuck/inactive
├── send_report.py           MODIFY → per-language alert state
├── setup.py                 MODIFY → language choice, per-language questions, hooks, task rename
├── README.md                MODIFY → rewritten for three languages
├── curriculum.json          DELETE (moved)
├── run_logger.py            DELETE (moved)
├── languages/
│   ├── __init__.py          CREATE → registry: get_pack(key), all_packs(), pack_for_path(path)
│   ├── base.py              CREATE → LanguagePack base class
│   ├── clike.py             CREATE → tokenizer + syntax check for Java/JS
│   ├── envvars.py           CREATE → add/remove a token in a user env var
│   ├── python/   __init__.py, pack.py, analyzer.py (moved), curriculum.json (moved), run_logger.py (moved)
│   ├── javascript/ __init__.py, pack.py, analyzer.py, curriculum.json, node_hook.js, saved_scan.py
│   └── java/     __init__.py, pack.py, analyzer.py, curriculum.json, eclipse_scan.py, agent/TrackerAgent.java
└── tests/
    ├── __init__.py, helpers.py   temp PYTRACKER_HOME, sample runs
    ├── fixtures/                 sample sources per language, sample Eclipse workspace
    └── test_*.py                 one per task
```

The tests run from `C:\Python` with `python -m unittest discover -s tracker/tests -t tracker`. Every test module starts with `import tests.helpers`, which puts `tracker/` on `sys.path` and sets `PYTRACKER_HOME` to a fresh temporary folder **before** importing `settings`.

---

### Task 1: Language-pack skeleton and the Python pack

**Files:**
- Create: `languages/__init__.py`, `languages/base.py`, `languages/python/__init__.py`, `languages/python/pack.py`
- Move (`git mv`): `analyzer.py` → `languages/python/analyzer.py`; `curriculum.json` → `languages/python/curriculum.json`; `run_logger.py` → `languages/python/run_logger.py`
- Create: `analyzer.py` (new, CLI only)
- Create: `tests/__init__.py`, `tests/helpers.py`, `tests/test_packs.py`, `tests/fixtures/python/loops.py`

**Interfaces:**
- Produces, in `languages/base.py`, the class `LanguagePack` with:
  - attributes `key: str`, `label: str`, `icon: str`, `editor: str`, `extensions: set[str]`, `dir: Path`
  - `curriculum() -> dict`: loads `self.dir / "curriculum.json"`, cached
  - `analyze(source: str, path: str | None = None) -> dict`: keys `topics` (sorted list), `score`, `level`, `lines`, `syntax_ok`, plus any extra counts
  - `install(lang_config: dict, data_dir: Path) -> tuple[bool, str]`, `uninstall() -> str`, `self_test(lang_config: dict) -> tuple[bool, str]`: the defaults return `(False, "not supported")` and `"nothing to remove"`
  - `collect(lang_config: dict, data_dir: Path, runs: list[dict]) -> list[dict]`: the default returns `[]`
  - `hook_installed() -> bool`: the default returns `False`
- Produces, in `languages/__init__.py`:
  - `get_pack(key: str) -> LanguagePack`
  - `all_packs() -> list[LanguagePack]`, ordered python, java, javascript
  - `pack_for_path(path) -> LanguagePack | None`, chosen by the file extension (lower-cased)
- Produces the shared function `complexity_level(score: int) -> str`, kept in `languages/base.py` and re-used by the Python analyser.
- Python pack: `analyze` wraps `analyze_source` and adds `syntax_ok = result["parsed"]`. `extensions = {".py"}`.

- [ ] **Step 1: Write `tests/helpers.py`**
  - Insert the `tracker` dir at `sys.path[0]`.
  - Set `os.environ["PYTRACKER_HOME"] = tempfile.mkdtemp()`.
  - Provide `fresh_home() -> Path`. It empties that folder and returns it, and calls `importlib.reload(settings)` for modules that cache paths.
  - Provide `write_runs(path, entries)`.

- [ ] **Step 2: Write the failing tests in `tests/test_packs.py`**

```python
def test_registry_order_and_lookup(self):
    self.assertEqual([p.key for p in all_packs()], ["python", "java", "javascript"])
    self.assertEqual(pack_for_path(r"C:\x\Main.JAVA").key, "java")
    self.assertEqual(pack_for_path("page.html").key, "javascript")
    self.assertIsNone(pack_for_path("notes.txt"))

def test_python_pack_matches_old_analyser(self):
    src = (FIXTURES / "python" / "loops.py").read_text(encoding="utf-8")
    result = get_pack("python").analyze(src, str(FIXTURES / "python" / "loops.py"))
    self.assertTrue(result["syntax_ok"])
    self.assertIn("for_loop", result["topics"])
    self.assertIn("while_loop", result["topics"])

def test_python_syntax_error(self):
    result = get_pack("python").analyze("def broken(:\n")
    self.assertFalse(result["syntax_ok"])
    self.assertEqual(result["topics"], [])

def test_python_curriculum_unchanged(self):
    cur = get_pack("python").curriculum()
    self.assertEqual(len(cur["levels"]), 9)
    self.assertEqual(sum(l["days"]["standard"] for l in cur["levels"]), 132)
```

  `loops.py` contains a `for` over `range(3)` and a `while` loop. The java/javascript packs appear in the registry as stubs here: create their `pack.py` with `key`, `label`, `icon`, `editor`, `extensions` only. Tasks 5 and 6 fill them in.

- [ ] **Step 3: Run it**

  Run: `python -m unittest discover -s tracker/tests -t tracker -k packs`
  Expected: FAIL, because `languages` can't be imported.

- [ ] **Step 4: Implement**
  - Do the `git mv`s.
  - Inside `languages/python/analyzer.py`, import `complexity_level` from `languages.base` instead of defining it.
  - Add `"language": "python", "editor": "VS Code", "extensions": [".py"]` to the moved `curriculum.json`.
  - The new root `analyzer.py`:
    - takes `python tracker\analyzer.py <file>` and finds the pack with `pack_for_path`
    - reads the file as UTF-8 with `errors="replace"`
    - prints each result key the way the old CLI did
    - exits with `"Usage: python analyzer.py <file.py|.java|.js|.html>"` if there's no argument, and `"Unsupported file type: <ext>"` for an unknown extension

- [ ] **Step 5: Run the tests again**

  Run: `python -m unittest discover -s tracker/tests -t tracker -k packs`
  Expected: 4 tests OK.

- [ ] **Step 6: Commit**

  Message: `Add language-pack registry and move Python analyser and course into languages/python`

---

### Task 2: Settings, per-language paths and migration

**Files:**
- Modify: `settings.py`
- Create: `migrate.py`
- Test: `tests/test_migrate.py`

**Interfaces:**
- Produces in `settings.py`:
  - `DEFAULT_CONFIG` = `{"learner_name", "email", "alerts", "languages": {key: DEFAULT_LANGUAGE[key]}}`. Each language default has `enabled: False`, `start_date: ""`, `plan: "standard"`, and the default `code_folder`. Java's also has `extra_workspaces: []` and `exclude_folders: []`.
  - `lang_dir(key) -> Path`, which is `DATA_DIR / key`
  - `runs_path(key) -> Path`
  - `snapshot_dir(key) -> Path`
  - `enabled_languages(config) -> list[str]`, in registry order
  - `load_config()`: calls `migrate.migrate_if_needed()` first, then deep-merges the defaults per language block
  - `load_curriculum()`: **removed**. Callers use `get_pack(key).curriculum()`.
  - `TASK_NAME = "LearningTracker"`, `OLD_TASK_NAME = "PythonLearningTracker"`
- Produces in `migrate.py`:
  - `migrate_if_needed() -> bool`: returns True if anything changed
  - `convert_entry(old: dict) -> dict`: `{"sha": s, ...}` becomes `{..., "files": [{"file": file, "sha": s}], "source": "hook"}`, without the `sha` key. An entry that already has `files` is returned unchanged.
- **New `email_state.json` shape:** `{"last_progress_sent": iso | None, "languages": {key: {"alerts": {level_id: date}, "last_inactive_sent": date | None}}}`. The old top-level `alerts` and `last_inactive_sent` move under `languages.python`.

- [ ] **Step 1: Write the failing tests**

```python
def test_old_layout_is_migrated(self):
    home = fresh_home()
    save_json(home / "config.json", {"learner_name": "S", "start_date": "2026-10-01",
                                     "plan": "aggressive", "code_folder": r"C:\Python", "email": {}, "alerts": {}})
    write_runs(home / "data" / "runs.jsonl", [{"time": "2026-10-02T10:00:00", "file": r"C:\Python\a.py",
                                               "status": "success", "error": None, "duration": 1, "sha": "abc"}])
    (home / "data" / "snapshots").mkdir(parents=True); (home / "data" / "snapshots" / "abc.py").write_text("print(1)")
    save_json(home / "data" / "email_state.json", {"last_progress_sent": "2026-10-20T08:00:00",
                                                   "alerts": {"4": "2026-10-19"}, "last_inactive_sent": None})
    config = load_config()
    self.assertEqual(config["languages"]["python"],
                     {"enabled": True, "start_date": "2026-10-01", "plan": "aggressive", "code_folder": r"C:\Python"})
    self.assertNotIn("start_date", config)
    [entry] = read_jsonl(home / "data" / "python" / "runs.jsonl")
    self.assertEqual(entry["files"], [{"file": r"C:\Python\a.py", "sha": "abc"}])
    self.assertTrue((home / "data" / "python" / "snapshots" / "abc.py").exists())
    state = load_json(home / "data" / "email_state.json")
    self.assertEqual(state["languages"]["python"]["alerts"], {"4": "2026-10-19"})

def test_migration_is_idempotent(self): ...      # call load_config() twice; files and config unchanged the 2nd time
def test_leftover_old_runs_are_appended(self):    # Review Focus 1
    # After migrating, write a new line to data/runs.jsonl and call load_config() again:
    # the line is appended to data/python/runs.jsonl in the new shape, and data/runs.jsonl is gone.
def test_defaults_fill_partial_language_block(self):
    # config with languages.java = {"enabled": True} → java gets plan "standard", exclude_folders [] etc.
```

- [ ] **Step 2: Run them**

  Run: `python -m unittest discover -s tracker/tests -t tracker -k migrate`
  Expected: FAIL.

- [ ] **Step 3: Implement `settings.py` changes and `migrate.py`**
  - Migration order:
    1. config
    2. leftover or old `data/runs.jsonl` lines (appended, then the file is deleted)
    3. `data/snapshots/*` files moved to `data/python/snapshots/` (skip any that already exist)
    4. email state
  - Reinstalling the Python logger after a migration is done by `setup.py` (Task 13). `migrate_if_needed` only logs `"Re-run setup.py to update the Python run logger"` when it migrated a config.

- [ ] **Step 4: Run them again**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Per-language settings, data folders and automatic migration of the Python layout`

---

### Task 3: Engine, per-language and overall reports

**Files:**
- Modify: `track.py`
- Modify: `languages/python/run_logger.py`: write `{"time", "file", "status", "error", "error_count": None, "duration", "source": "hook", "files": [{"file", "sha"}]}` to `<DATA_DIR>/python/runs.jsonl`, and snapshots to `<DATA_DIR>/python/snapshots/<sha>.py`. `DATA_DIR` placeholder stays the top-level data dir.
- Test: `tests/test_track.py`

**Interfaces:**
- Consumes: `get_pack`, `settings.runs_path`, `snapshot_dir`, `enabled_languages` (Tasks 1 and 2).
- Produces in `track.py`:
  - `COUNTING = {"success", "compiled"}`
  - `counts(run) -> bool`: True when the status is in `COUNTING`, or when the status is `saved` and `run["analysis"]["syntax_ok"]` is true
  - `load_runs(key: str, start_date: date) -> list[dict]`: same rules as today, per language
  - `attach_analysis(pack, key, runs)`:
    - analyses every file in `run["files"]` from `snapshot_dir(key) / f"{sha}{Path(file).suffix.lower()}"`, read with `encoding="utf-8", errors="replace"`
    - `run["analysis"]` gets the union of topics, the sum of `lines`, the max `score` with its `level`, and `syntax_ok` = all files ok. It's `None` if there are no readable snapshots.
  - `build_language_report(key: str, config: dict, today: date) -> dict`:
    - **today's report dict, unchanged in shape**, plus `language`, `label`, `icon`, `editor`, `curriculum_levels` (= `len(levels)`)
    - `success`-based logic everywhere switches to `counts(run)`. That covers `topic_first`, success days, `latest_per_file`, and the daily chart, where `success` = counting runs and `error` = the rest.
    - the error table includes `compile_error` entries, with the label `f"{error_count} compile errors"` when `error` is empty
    - `recent` items gain `source` and `folder` (the parent folder path)
    - `saved_not_run` uses `pack.extensions`
    - it calls `pack.collect(lang_config, lang_dir(key), runs)` before analysis. Collected entries are appended to `runs_path(key)` by the collector, not by the engine.
  - `build_report(config=None, today=None) -> dict`:
    ```
    {"generated", "today", "learner",
     "languages": {key: report or {"language": key, "label", "icon", "error": str}},
     "overall": {"any_streak": int, "week_activity": int,
                 "daily_by_language": [{"date": iso, "<key>": n, ...}] (14 days, counting runs)},
     "enabled": [keys]}
    ```
    Each language is built inside `try/except Exception`. On failure the error is logged through `send_report.log`'s format (`settings.log_line(text)`, moved into `settings.py` from `send_report.log`) and `error` is set to `str(exc)`.
  - `main()` prints one line per language: `🐍 Python: day 12 of 65 · 3/9 levels · current: Functions`.

- [ ] **Step 1: Write the failing tests**

  These use a fake config with python and java enabled. Java runs are written straight to `data/java/runs.jsonl`, with snapshots in `data/java/snapshots`. Java's analyser is still the Task 1 stub, so a stub `analyze` is monkeypatched to return `{"topics": ["println"], "score": 1, "level": "Beginner", "lines": 3, "syntax_ok": True}`.

```python
def test_compiled_counts_and_compile_error_does_not(self):
    write java runs: compiled on 2026-11-02 (sha a), compile_error on 2026-11-03 (sha b, error_count 2)
    rep = build_report(config, today=date(2026, 11, 3))["languages"]["java"]
    self.assertEqual(rep["stats"]["streak"], 1)              # only 11-02 counts → streak ends yesterday
    self.assertTrue(rep["levels"][0]["topics"][1]["done"])   # println, from the compiled run
    self.assertEqual(rep["errors"][0]["error"], "2 compile errors")

def test_language_start_dates_are_separate(self):          # Review Focus 5
    python start 2026-10-01, java start 2026-11-01; java compiled run on 2026-10-15
    rep = build_report(config, today=date(2026, 11, 3))
    self.assertEqual(rep["languages"]["java"]["stats"]["total_runs"], 0)

def test_one_language_failing_keeps_others(self):
    monkeypatch get_pack("java").analyze to raise RuntimeError("boom")
    rep = build_report(config, today=...)
    self.assertEqual(rep["languages"]["java"]["error"], "boom")
    self.assertIn("levels", rep["languages"]["python"])

def test_saved_counts_only_when_syntax_ok(self): ...       # saved + syntax_ok False → not in topics or streak
def test_overall_any_streak_spans_languages(self): ...     # python on day 1, java on day 2 → any_streak 2
def test_python_migrated_entries_still_analysed(self): ... # old-shape entry converted by Task 2 → topics found
```

- [ ] **Step 2: Run them**

  Run: `python -m unittest discover -s tracker/tests -t tracker -k track`
  Expected: FAIL.

- [ ] **Step 3: Implement the `track.py` and `run_logger.py` changes listed in Interfaces**

- [ ] **Step 4: Run all tests**

  Run: `python -m unittest discover -s tracker/tests -t tracker`
  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Build a report per language plus an overall summary`

  Note: `dashboard.py`, `emailer.py` and `send_report.py` consume the new shape from Tasks 11 and 12 onwards. Until then `track.py`'s `main()` only prints. It doesn't write the dashboard.

---

### Task 4: Shared C-like tokenizer

**Files:**
- Create: `languages/clike.py`
- Test: `tests/test_clike.py`

**Interfaces:**
- Produces `tokenize(source: str, language: str) -> Cleaned`, where `language` is `"java"` or `"javascript"`.
- `Cleaned` is a dataclass with these fields:

| Field | Type | Meaning |
|---|---|---|
| `code` | `str` | Comments removed; every string, char and regex literal replaced by `""` |
| `has_comment` | `bool` | |
| `has_template` | `bool` | JavaScript only |
| `strings` | `list[str]` | The original string contents, kept for rules like the `"use strict"` check or file names |
| `syntax_ok` | `bool` | |
| `lines` | `int` | Lines that aren't blank and aren't only a comment |

- **JavaScript template literals:** the text between backticks becomes `""`, but each `${ ... }` expression is kept in `code`. Brace depth is tracked, and nested templates are allowed.
- **Java text blocks** (`"""`) are treated as one string.
- **JavaScript regex literals:** a `/` counts as the start of a regex when the previous meaningful character is empty or one of `( , = : [ ! & | ? { } ; + - * % < > ~ ^`, or the previous word is `return`, `typeof`, `case`, `do`, `else` or `in`.
- **`syntax_ok` is false when:**
  - a string, comment, template or regex isn't closed
  - brackets `()[]{}` don't balance in the cleaned code
  - a closing bracket doesn't match its opener

- [ ] **Step 1: Write the failing tests**

```python
def test_comments_and_strings_removed(self):
    c = tokenize('int x = 1; // class Foo\n/* while */ String s = "for (;;)";', "java")
    self.assertNotIn("class", c.code); self.assertNotIn("while", c.code); self.assertNotIn("for", c.code)
    self.assertTrue(c.has_comment); self.assertTrue(c.syntax_ok); self.assertEqual(c.strings, ["for (;;)"])

def test_template_keeps_expressions(self):
    c = tokenize("const s = `hi ${name.map(x => x)} class`;", "javascript")
    self.assertIn("name.map(x => x)", c.code); self.assertNotIn("class", c.code); self.assertTrue(c.has_template)

def test_regex_literal_vs_division(self):
    self.assertNotIn("class", tokenize("const r = /class/g; const h = a / b / c;", "javascript").code)
    self.assertTrue(tokenize("const h = a / b / c;", "javascript").syntax_ok)

def test_java_text_block(self):
    self.assertNotIn("while", tokenize('String t = """\n  while "x"\n""";', "java").code)

def test_unbalanced_and_unclosed(self):
    self.assertFalse(tokenize("if (x { }", "java").syntax_ok)
    self.assertFalse(tokenize('let s = "abc;', "javascript").syntax_ok)
    self.assertFalse(tokenize("/* never closed", "java").syntax_ok)
    self.assertFalse(tokenize("(]", "java").syntax_ok)

def test_line_count_ignores_blank_and_comment_lines(self):
    self.assertEqual(tokenize("// a\n\nint x;\n/* b\n c */\nint y;\n", "java").lines, 2)
```

- [ ] **Step 2: Run them**

  Run: `python -m unittest discover -s tracker/tests -t tracker -k clike`
  Expected: FAIL.

- [ ] **Step 3: Implement**

  Use a single left-to-right scanner with states `code`, `line_comment`, `block_comment`, `string(quote)`, `template` and `regex`, plus a stack for template `${` depth. The `lines` count comes from a second pass over the original lines, using the comment spans the scanner recorded.

- [ ] **Step 4: Run them again**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Add comment/string-aware tokenizer for Java and JavaScript`

---

### Task 5: Java analyser and course

**Files:**
- Create: `languages/java/analyzer.py`, `languages/java/curriculum.json`
- Modify: `languages/java/pack.py` (`analyze`, `curriculum`)
- Create: `tests/fixtures/java/*.java`, with one file per level named `l1_basics.java` … `l9_modern.java`, plus `hello.java` and `cp1252.java`
- Test: `tests/test_java_analyzer.py`

**Interfaces:**
- Consumes: `clike.tokenize` (Task 4) and `complexity_level` (Task 1).
- Produces `analyze_java(source: str, path: str | None = None) -> dict`, with the same keys as the Python result: `parsed` (= `syntax_ok`), `lines`, `functions`, `classes`, `loops`, `conditions`, `tries`, `imports`, `score`, `level`, `topics`, `syntax_ok`.
- Produces `TOPIC_RULES: dict[str, list[re.Pattern] | Callable[[Cleaned], bool]]`, with exactly one entry per topic id in the Java curriculum.

**What goes in the course.** Use the levels, tiers, days and topics from spec §8, and the same plan targets as Python:
- Standard: `daily_runs_target: 2`, `weekly_lines_target: 150`, `streak_target_days: 30`, `daily_effort: "30–45 min a day"`
- Aggressive: `daily_runs_target: 5`, `weekly_lines_target: 400`, `streak_target_days: 30`, `daily_effort: "1.5–2 hours a day"`
- Each level has 2 links (dev.java, docs.oracle.com/javase/tutorial or w3schools.com/java) and a project. Level 5's project: "Bank account class with deposit and withdraw that refuses overdrafts."
- Each topic has a `link` and a `try`.
- `"language": "java"`, `"editor": "Eclipse"`, `"extensions": [".java"]`.

**Topic ids, in course order.** Each id's rule must match the matching fixture.

| Level | Topic ids |
|---|---|
| L1 | `main_method`, `println`, `primitives`, `strings`, `scanner`, `operators`, `comments` |
| L2 | `if_else`, `switch`, `for_loop`, `while_loop`, `break_continue` |
| L3 | `arrays`, `enhanced_for`, `arrays_2d`, `string_methods`, `string_builder` |
| L4 | `static_methods`, `params_return`, `overloading`, `recursion` |
| L5 | `class_new`, `constructors`, `this_keyword`, `encapsulation`, `static_members` |
| L6 | `extends`, `super_call`, `override`, `abstract_class`, `interfaces`, `polymorphism` |
| L7 | `try_catch`, `throw_throws`, `custom_exception`, `try_with_resources`, `read_file`, `write_file` |
| L8 | `array_list`, `hash_map`, `hash_set`, `generics`, `comparator` |
| L9 | `lambdas`, `streams`, `enums_records`, `packages`, `junit` |

**Rules that need a decision** (write the rest as plain regexes):

| Topic | Rule |
|---|---|
| `main_method` | `public\s+static\s+void\s+main\s*\(` |
| `comments` | `Cleaned.has_comment` |
| `strings` | `\bString\b` together with a string literal in `strings` |
| `enhanced_for` | `for\s*\(\s*(final\s+)?[\w<>\[\],\s]+\s+\w+\s*:` |
| `arrays_2d` | `\[\s*\]\s*\[\s*\]`, or `new\s+\w+\s*\[[^\]]*\]\s*\[` |
| `overloading` | the same method name declared twice with different parameter lists |
| `recursion` | a method whose body calls its own name |
| `encapsulation` | a `private` field **and** a `get[A-Z]\w*\s*\(` method |
| `polymorphism` | `\b([A-Z]\w*)\s+\w+\s*=\s*new\s+(?!\1\b)[A-Z]\w*\s*\(` (declared type ≠ created type), or `@Override` together with `extends`/`implements` |
| `custom_exception` | `class\s+\w+\s+extends\s+\w*(Exception\|Error)\b` |
| `read_file` | `FileReader`, `BufferedReader`, `Files\.read\w*`, `Files\.lines`, or `new\s+Scanner\s*\(\s*new\s+File` |
| `write_file` | `FileWriter`, `PrintWriter`, `BufferedWriter`, or `Files\.write\w*` |
| `junit` | `import\s+(static\s+)?org\.junit`, or `@Test\b` |
| `packages` | `^\s*package\s+[\w.]+\s*;`, or a non-`java.lang` `import` |

**Score:**
- `functions`: method declarations, i.e. `(public|private|protected|static|\s)+[\w<>\[\]]+\s+\w+\s*\([^)]*\)\s*(throws [\w, ]+)?\s*\{`, minus `main`
- `classes`: `\b(class|interface|enum|record)\s+\w+`, minus the class that declares `main`
- `loops`: `for` + `while` + `do` keywords
- `conditions`: `if` + `case`
- `tries`: `try`
- `imports`: `import` lines
- `score = lines // 10 + functions*2 + classes*4 + loops + conditions + tries*2 + imports`

- [ ] **Step 1: Write the failing tests**

```python
def test_each_level_fixture_finds_its_topics(self):
    for level in get_pack("java").curriculum()["levels"]:
        src = fixture(level)                                  # l<id>_*.java
        found = set(analyze_java(src)["topics"])
        for t in level["topics"]:
            self.assertIn(t["id"], found, f"{t['id']} not detected in level {level['id']}")

def test_every_topic_has_a_rule(self):
    ids = {t["id"] for l in get_pack("java").curriculum()["levels"] for t in l["topics"]}
    self.assertEqual(ids, set(TOPIC_RULES))

def test_hello_world_is_beginner(self):
    r = analyze_java(read("hello.java"))
    self.assertEqual((r["classes"], r["functions"], r["level"]), (0, 0, "Beginner"))

def test_keywords_in_comments_and_strings_ignored(self):
    r = analyze_java('class A { public static void main(String[] a) { // extends Foo\n System.out.println("while"); } }')
    self.assertNotIn("extends", r["topics"]); self.assertNotIn("while_loop", r["topics"])

def test_non_utf8_source_does_not_crash(self):                # Review Focus 3
    src = (FIX / "cp1252.java").read_bytes().decode("utf-8", errors="replace")   # file contains byte 0xE9
    self.assertIn("println", analyze_java(src)["topics"])

def test_course_totals(self):
    levels = get_pack("java").curriculum()["levels"]
    self.assertEqual(sum(l["days"]["standard"] for l in levels), 132)
    self.assertEqual(sum(l["days"]["aggressive"] for l in levels), 65)
```

- [ ] **Step 2: Run them**

  Run: `python -m unittest discover -s tracker/tests -t tracker -k java_analyzer`
  Expected: FAIL.

- [ ] **Step 3: Write `curriculum.json`, the fixtures, `analyzer.py`, and `pack.analyze`**

- [ ] **Step 4: Run them again**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Add Java course and pattern-based Java analyser`

---

### Task 6: JavaScript analyser and course

**Files:**
- Create: `languages/javascript/analyzer.py`, `languages/javascript/curriculum.json`
- Modify: `languages/javascript/pack.py`
- Create: `tests/fixtures/javascript/l1_basics.js` … `l9_node.js`, `l5_dom.html`
- Test: `tests/test_js_analyzer.py`

**Interfaces:**
- Consumes: `clike.tokenize` (Task 4).
- Produces:
  - `analyze_js(source: str, path: str | None = None) -> dict`, with the same keys as `analyze_java`
  - `extract_scripts(html: str) -> tuple[str, list[str]]`: the inline `<script>` bodies joined by `\n`, and the list of `src` values. Regex: `<script\b([^>]*)>(.*?)</script>`, case-insensitive with DOTALL.
- For `.html` paths, `pack.analyze` analyses `extract_scripts(source)[0]`.
- `TOPIC_RULES` has one entry per JavaScript topic id.

**What goes in the course:** levels, tiers, days and topics from spec §8; plan targets as in Task 5; links from developer.mozilla.org and javascript.info; Level 5's project is "To-do list page: add, tick off and delete items." Also `"language": "javascript"`, `"editor": "VS Code"`, `"extensions": [".js", ".mjs", ".cjs", ".html"]`.

**Topic ids:**

| Level | Topic ids |
|---|---|
| L1 | `console_log`, `let_const`, `numbers_strings`, `template_literals`, `operators`, `comments` |
| L2 | `if_else`, `switch`, `for_loop`, `while_loop`, `strict_ternary`, `break_continue` |
| L3 | `function_decl`, `default_params`, `return`, `arrow_functions`, `scope` |
| L4 | `arrays`, `map_filter_reduce`, `objects`, `destructuring`, `spread` |
| L5 | `query_selector`, `dom_content`, `event_listener`, `create_element`, `forms` |
| L6 | `try_catch`, `throw`, `json`, `es_modules`, `require` |
| L7 | `timers_callbacks`, `promises`, `async_await`, `fetch` |
| L8 | `classes`, `class_extends`, `getters_static`, `map_set`, `optional_chaining` |
| L9 | `fs_files`, `process_argv`, `npm_package`, `node_test`, `http_server` |

**Rules that need a decision:**

| Topic | Rule |
|---|---|
| `strict_ternary` | `===` or `!==`, **and** a ternary `\?[^?.:]+:` |
| `scope` | `let` or `const` declared inside a `{}` block of a function, **plus** a closure (a function returning a function, `return\s+(function\|\(?[\w,\s]*\)?\s*=>)`) |
| `destructuring` | `(const\|let\|var)\s*[\[{]` |
| `spread` | `\.\.\.\w` |
| `dom_content` | `\.(textContent\|innerHTML\|innerText)\s*=` |
| `forms` | `\.value\b` together with an `addEventListener\(\s*""` |

  The `forms` rule matches `""` because string contents are replaced; use the original strings to check for `"submit"` or `"input"`.

| Topic | Rule (continued) |
|---|---|
| `npm_package` | a `require("x")` or `import ... from "x"` where `x` doesn't start with `.`, `/` or `node:`, and isn't a Node built-in (`fs`, `path`, `http`, `https`, `os`, `url`, `util`, `events`, `assert`, `child_process`, `crypto`, `readline`, `stream`, `test`) |
| `node_test` | `node:test`, or `require("assert")` / `node:assert` together with `test(` or `it(` |
| `getters_static` | `\b(get\|set\|static)\s+\w+\s*\(` |

  `npm_package` and `node_test` read the module names from `Cleaned.strings`.

**Score:**
- `functions`: `function` keyword + `=>` + class method declarations
- `classes`: `\bclass\s+\w+`
- `loops`, `conditions` and `tries`: as for Java
- `imports`: `import` statements + `require(` calls

- [ ] **Step 1: Write the failing tests**

  These follow the same pattern as Task 5:
  - `test_each_level_fixture_finds_its_topics`: L5 uses `l5_dom.html` through `pack.analyze`
  - `test_every_topic_has_a_rule`
  - `test_course_totals` (132 / 65)

  Plus:

```python
def test_html_inline_scripts_only(self):
    code, srcs = extract_scripts('<p>class</p><script src="app.js"></script><script>document.querySelector("p")</script>')
    self.assertEqual(srcs, ["app.js"]); self.assertIn("querySelector", code); self.assertNotIn("<p>", code)

def test_relative_and_builtin_modules_are_not_npm(self):
    r = analyze_js('const fs = require("fs"); const u = require("./util"); import x from "node:path";')
    self.assertNotIn("npm_package", r["topics"])
    self.assertIn("npm_package", analyze_js('const chalk = require("chalk");')["topics"])
```

- [ ] **Step 2: Run them**

  Expected: FAIL.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run them again**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Add JavaScript course and analyser, including HTML inline scripts`

---

### Task 7: User environment-variable helpers

**Files:**
- Create: `languages/envvars.py`
- Test: `tests/test_envvars.py`

**Interfaces:**
- Produces these pure functions:
  - `add_token(value: str | None, token: str) -> str`: appends with a single space. If `token` is already present (exact match after splitting on spaces outside quotes), it returns the value unchanged.
  - `remove_token(value: str | None, token: str) -> str`: removes every exact occurrence and collapses the spaces.
- Produces these side-effect functions:
  - `get_user_env(name) -> str | None`: reads `HKCU\Environment` with `winreg`
  - `set_user_env(name, value: str)`: deletes the value when `value` is empty; otherwise writes `REG_EXPAND_SZ`. It then broadcasts `WM_SETTINGCHANGE` with `ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 5000, None)`.
  - `user_env_add(name, token) -> bool` and `user_env_remove(name, token) -> bool`: return whether anything changed
- The existing `setup.py` password store and remove switch to `set_user_env`, so the PowerShell environment-variable code is removed.

- [ ] **Step 1: Write the failing tests**

```python
NODE = '--require "C:\\Python\\tracker\\languages\\javascript\\node_hook.js"'
def test_add_keeps_existing(self):
    self.assertEqual(add_token("--max-old-space-size=4096", NODE), "--max-old-space-size=4096 " + NODE)
def test_add_is_idempotent(self):
    self.assertEqual(add_token(NODE, NODE), NODE)
def test_add_to_empty(self):
    self.assertEqual(add_token(None, NODE), NODE)
def test_remove_only_ours(self):
    self.assertEqual(remove_token("-Xmx1g " + NODE + " -Dx=1", NODE), "-Xmx1g -Dx=1")
    self.assertEqual(remove_token(NODE, NODE), "")
```

  The `NODE` token is a single token because the quotes are part of it. Tokens are compared as whole quoted strings, so splitting must respect quotes.

- [ ] **Step 2: Run them**

  Expected: FAIL.

- [ ] **Step 3: Implement**

  The registry functions are not unit-tested. Setup's self-test covers them, and so does Task 14's manual check.

- [ ] **Step 4: Run them again**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Add helpers to add/remove the tracker's part of user environment variables`

---

### Task 8: JavaScript capture (Node hook and saved files)

**Files:**
- Create: `languages/javascript/node_hook.js`, `languages/javascript/saved_scan.py`
- Modify: `languages/javascript/pack.py`: `install`, `uninstall`, `self_test`, `hook_installed`, `collect`
- Test: `tests/test_js_capture.py`

**Interfaces:**
- Consumes: `envvars` (Task 7), `extract_scripts` and `analyze_js` (Task 6), and `settings.runs_path` / `snapshot_dir` (Task 2).
- `HOOK_TOKEN = f'--require "{pack.dir / "node_hook.js"}"'`
- `install(lang_config, data_dir)`:
  1. writes `languages/javascript/hook.json` = `{"data_dir": str(data_dir), "code_folder": ..., "tracker_dir": ...}`
  2. if `shutil.which("node")` is set, calls `user_env_add("NODE_OPTIONS", HOOK_TOKEN)` and returns `(True, "Node hook installed")`
  3. otherwise returns `(False, "node not found: JavaScript will use saved-file tracking only")`
- `hook_installed()`: True when `HOOK_TOKEN` is in the user `NODE_OPTIONS`.

**`node_hook.js`** (CommonJS, no dependencies; the whole body sits inside `try {} catch {}`):
- reads `hook.json` from `__dirname`
- `script = process.argv[1]`, resolved with `path.resolve`
- **tracked** when:
  - the extension is `.js`, `.mjs` or `.cjs`
  - the lower-cased path starts with `code_folder + sep`
  - and it isn't under `tracker_dir` and has no `\node_modules\` segment
- if not tracked, it returns straight away
- otherwise it records `started = Date.now()` and `error = null`, then registers:
  - `process.on("uncaughtExceptionMonitor", e => error = (e && e.name) || "Error")`
  - `process.once("SIGINT", () => { stopped = true; process.exit(130); })`
  - `process.on("exit", code => write(code))`
- `write`:
  - status: `stopped` if stopped, else `error` if `error` or `code !== 0`, else `success`
  - error text: `error || (code !== 0 && !stopped ? "exit code " + code : null)`
  - sha: `crypto.createHash("sha256")` over the file bytes, first 16 hex characters
  - snapshot: `<data_dir>/javascript/snapshots/<sha><ext>`, written only if it doesn't exist
  - appends `JSON.stringify(entry) + "\n"` with `fs.appendFileSync` to `<data_dir>/javascript/runs.jsonl`, where `entry` is `{time: local ISO without ms, file, status, error, error_count: null, duration: secs (2 dp), source: "hook", files: [{file, sha}]}`
  - local ISO time: build it from `Date` with the timezone offset removed (`new Date(Date.now() - tzOffset).toISOString().slice(0, 19)`)

**`saved_scan.collect_saved(lang_config, data_dir, runs, hook_on: bool) -> list[dict]`:**
- walks `code_folder`, skipping folders named `node_modules`, `.git`, `.vscode`, `dist` or `build`, and the tracker dir
- candidates:
  - every `.html` file
  - `.js`, `.mjs` and `.cjs` files referenced by `<script src>` from an `.html` file in the same folder (relative paths only)
  - every `.js` file, but only when `hook_on` is False
- for each candidate:
  - sha = sha256 of the bytes [:16]
  - it's skipped when the sha is in `saved_seen.json` or matches any `run["files"]` sha
  - otherwise it gets a snapshot, an entry `{time: mtime iso, file, status: "saved", error: None if syntax_ok else "SyntaxError", error_count: None, duration: 0, source: "saved", files: [{file, sha}]}` appended to `runs.jsonl`, and its sha added to `saved_seen.json`
  - if `syntax_ok` is false, the status is `error` instead of `saved` (spec §12)
- returns the new entries, which `pack.collect` passes back to the engine

- [ ] **Step 1: Write the failing tests**

```python
def test_html_and_linked_js_are_saved_unlinked_is_not(self):
    folder with index.html (<script src="app.js"></script><script>console.log(1)</script>), app.js, other.js
    new = collect_saved(cfg, data_dir, runs=[], hook_on=True)
    self.assertEqual(sorted(Path(e["file"]).name for e in new), ["app.js", "index.html"])
    self.assertEqual({e["status"] for e in new}, {"saved"})

def test_seen_sha_not_recorded_twice(self): ...           # second call returns []
def test_sha_already_run_is_skipped(self): ...            # runs contain app.js's sha → app.js not saved
def test_hook_off_saves_every_js(self): ...               # hook_on=False → other.js included
def test_syntax_error_logged_as_error(self): ...          # index.html with "<script>if (x {</script>" → status "error"
def test_skips_node_modules(self): ...                    # Review Focus 4: node_modules/lib/index.html ignored

@unittest.skipUnless(shutil.which("node"), "node not installed")
def test_node_hook_end_to_end(self):
    # Write hook.json for a temp code folder and data dir, then run
    #   node --require <hook> ok.js      → success
    #   node --require <hook> boom.js    (throw new TypeError) → error, "TypeError"
    #   node --require <hook> exit3.js   (process.exit(3))     → error, "exit code 3"
    #   node --require <hook> outside.js (outside code folder) → no entry
    # Check the 3 lines in runs.jsonl and that a snapshot exists for each.
```

- [ ] **Step 2: Run them**

  Expected: FAIL.

- [ ] **Step 3: Implement `node_hook.js`, `saved_scan.py` and the pack methods**

  `self_test` writes `hook.json` pointing at a temp data dir, runs `node -e` on a temp script inside a temp code folder through `--require`, checks for one `success` line, then rewrites `hook.json` with the real settings.

- [ ] **Step 4: Run them again**

  Expected: OK. The end-to-end test runs if Node is installed.

- [ ] **Step 5: Commit**

  Message: `Capture JavaScript runs with a Node hook and browser code as saved files`

---

### Task 9: Java agent

**Files:**
- Create: `languages/java/agent/TrackerAgent.java`
- Modify: `languages/java/pack.py`: `build_agent`, `install`, `uninstall`, `self_test`, `hook_installed`
- Test: `tests/test_java_agent.py`

**Interfaces:**
- Consumes: `envvars` (Task 7) and `settings` (Task 2).
- `build_agent(out_dir: Path) -> Path`:
  1. runs `javac --release 8 -d <tmp> TrackerAgent.java`, finding `javac` through `shutil.which("javac")` or `%JAVA_HOME%\bin\javac.exe`
  2. writes `out_dir / "tracker-agent.jar"` with `zipfile`: `META-INF/MANIFEST.MF` = `"Manifest-Version: 1.0\r\nPremain-Class: TrackerAgent\r\n\r\n"`, plus every `.class` file
  3. raises `RuntimeError("javac not found")` or `RuntimeError(<javac stderr>)` on failure
- `AGENT_TOKEN = f"-javaagent:{jar_path}"`. `install` refuses with `(False, "...path contains a space...")` if `" " in str(jar_path)`.
- `install(lang_config, data_dir)`:
  1. builds the jar into `pack.dir / "agent"`
  2. writes `agent.properties` next to it: `data_dir`, `tracker_dir`, `exclude` (a `;`-joined list of the built-in exclusions from Global Constraints plus `exclude_folders`), all as `key=value` lines with backslashes doubled
  3. calls `user_env_add("JAVA_TOOL_OPTIONS", AGENT_TOKEN)`
  4. if there's no `javac`, returns `(False, "javac not found: Java will use the Eclipse-build scan only. Install a JDK or set JAVA_HOME, then re-run setup.")`

**`TrackerAgent.java`** (Java 8, one file, static nested classes allowed):
- `public static void premain(String args, Instrumentation inst)`:
  - the whole body is inside `try { ... } catch (Throwable t) {}`
  - loads `agent.properties` from the jar's folder (`TrackerAgent.class.getProtectionDomain().getCodeSource().getLocation()`)
- `cmd = System.getProperty("sun.java.command", "")`. The main class or file is the first token, using quote-aware splitting.
- **Mode:**

| `cmd` starts with / is | Mode |
|---|---|
| `com.sun.tools.javac.Main` | **compile** |
| first token ends in `.java` | **source run** |
| `org.eclipse.`, `org.gradle.`, `org.codehaus.plexus.classworlds`, or ends in `.jar` | nothing |
| anything else | **class run** |

- **Compile mode:**
  - reads the remaining args, expanding `@file` arguments (one argument per line, quotes stripped)
  - `-d <dir>` sets the output dir; the other options are skipped, including those that take a value (`-cp`, `-classpath`, `--class-path`, `-sourcepath`, `-encoding`, `--release`, `-source`, `-target`, `-processorpath`)
  - for each `.java` arg that isn't excluded: expected class = `<d or source dir>/<package path>/<Name>.class`, where the package comes from the source's `package x.y;` line
  - a shutdown hook then writes one entry per run: `status = compiled` if every expected `.class` has `lastModified >= startMillis`, otherwise `compile_error` with `error_count` = the number of missing or stale classes
  - `file` = the first source, `files` = all of them
  - `source: "javac"`
- **Class run:**
  - the main class becomes a relative path `a/b/Main.java`
  - for each entry in `java.class.path` that is a directory, the agent tries these candidates in order: `dir`, `dir/../src`, `dir/../../src/main/java` (when `dir` ends in `target/classes`), `dir/../src/main/java`
  - the first existing `<candidate>/<rel>` that isn't excluded is the source
  - if none is found, nothing is recorded
- **Source run:** the source is the first token, resolved against `user.dir`.
- **Run modes (class and source):**
  - wraps the default uncaught exception handler: it stores `e.getClass().getSimpleName()`, then delegates to the previous handler, or calls `e.printStackTrace()` if there wasn't one
  - a shutdown hook writes `status = error` (with that name) or `success`
  - `files` = the source plus every other `*.java` in the same folder, excluding any listed folders
  - `source: "agent"`
- **Writing an entry:**
  - snapshots: `<data_dir>/java/snapshots/<sha16>.java`, where `sha16` = SHA-256 of the file bytes, first 16 hex characters (`MessageDigest`), written only if missing
  - the entry line is appended to `<data_dir>/java/runs.jsonl` through a `FileOutputStream(path, true)` in UTF-8
  - `time`: `LocalDateTime.now().withNano(0).toString()`
  - `duration`: seconds with 2 decimals
- **Excluded** = the lower-cased absolute path contains `\<name>\` for any built-in name, or starts with an `exclude` entry or `tracker_dir`.
- **JSON** is built by hand by `static String json(String s)`. It escapes `\` `"` `\n` `\r` `\t`, control characters < 0x20 as `\u00XX`, and leaves non-ASCII as is (the stream is UTF-8).
- **The shutdown hook** runs its work in a daemon thread and `join(2000)`s it.

- [ ] **Step 1: Write the failing tests**

  All are `@skipUnless(shutil.which("javac") and shutil.which("java"))`, except `test_install_refuses_space`.

```python
def test_compile_success_and_failure(self):
    jar = build_agent(tmp); write agent.properties (data_dir=tmp_data)
    run: javac -J-javaagent:<jar> Good.java  → compiled
    run: javac -J-javaagent:<jar> Bad.java   → compile_error, error_count 1
    # (-J passes the agent to javac's own JVM, same effect as JAVA_TOOL_OPTIONS)
    lines = read_jsonl(tmp_data / "java" / "runs.jsonl")
    self.assertEqual([l["status"] for l in lines], ["compiled", "compile_error"])
    self.assertEqual(lines[0]["source"], "javac")

def test_class_run_finds_source_through_bin_src(self):
    project/src/app/Main.java (package app; uses Helper), project/src/app/Helper.java, compiled to project/bin
    run: java -javaagent:<jar> -cp project/bin app.Main → success,
         files = Main.java + Helper.java
    run: java -javaagent:<jar> -cp project/bin app.Boom (throws IllegalStateException) → error "IllegalStateException"

def test_source_launch(self): ...      # java -javaagent:<jar> Hello.java → success, file = Hello.java
def test_excluded_folder_not_logged(self): ...   # same run with the project under exclude → no line

def test_paths_with_spaces_quotes_unicode_are_valid_json(self):   # Review Focus 2
    project folder named 'Ana María "test"' → run Main → json.loads(line)["file"] ends with r'Ana María "test"\src\app\Main.java'
    # (a space in the *source* path is fine; only the jar path may not contain one)

def test_install_refuses_space(self):
    ok, msg = pack.install_with_jar_path(Path(r"C:\My Tools\tracker-agent.jar"), ...)
    self.assertFalse(ok); self.assertIn("space", msg)
```

  `install_with_jar_path(jar_path, lang_config, data_dir)` is the testable core of `install`. `install` calls it with the real path.

- [ ] **Step 2: Run them**

  Expected: FAIL. On a machine without a JDK, everything except `test_install_refuses_space` is skipped. In that case, run the whole task on a machine with a JDK before you mark it done.

- [ ] **Step 3: Implement `TrackerAgent.java`, `build_agent` and the pack methods**

  `self_test`:
  1. builds into a temp dir
  2. compiles and runs a temp `Hello.java` through `java -javaagent:<tmpjar>` with a temp `agent.properties`
  3. checks for a `success` line

- [ ] **Step 4: Run them again**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Add Java agent that logs javac compiles and Java runs from any folder`

---

### Task 10: Eclipse build scan and Java exclusions

**Files:**
- Create: `languages/java/eclipse_scan.py`
- Modify: `languages/java/pack.py`: `collect`
- Modify: `track.py`: add `java_folders` to the Java report (the only language-specific line in the engine, added through an optional pack hook, `pack.extra_report(runs) -> dict`, which defaults to `{}` in `LanguagePack` and is merged into the language report)
- Create: `tests/fixtures/java/eclipse_ws/` (`.metadata/`; `Proj/.classpath`; `Proj/src/app/Main.java`, `Proj/src/app/Broken.java`; `Proj/bin/app/Main.class` and `Proj/bin/app/Broken.class`, which are just bytes, the second containing `Unresolved compilation problem` twice), plus `tests/fixtures/java/org.eclipse.ui.ide.prefs`
- Test: `tests/test_eclipse_scan.py`

**Interfaces:**
- Produces:
  - `recent_workspaces(home: Path = Path.home(), installs: list[Path] | None = None) -> list[Path]`
    - reads `RECENT_WORKSPACES=` from every `org.eclipse.ui.ide.prefs` found under `home/.eclipse/**/configuration/.settings/`, under `<install>/configuration/.settings/` for each install, and under `home/eclipse/*/eclipse/configuration/.settings/` (the Eclipse Installer's default)
    - each value is `\n`-separated (in the file, `\\n` and `\:` are escaped Java-properties style), so unescape it, keep the paths that exist, and dedupe them
  - `project_dirs(workspace: Path) -> list[Path]`: folders containing a `.classpath`, at depth 1 or 2, skipping `.metadata`
  - `src_and_output(project: Path) -> tuple[list[Path], Path]`: parses `.classpath` with `xml.etree`. Each `kind="src"` path (without `combineaccessrules`, and not starting with `/`) is a source folder; `kind="output"` is the output folder. The defaults are `[project/"src"]` and `project/"bin"`.
  - `scan_workspaces(workspaces: list[Path], data_dir: Path, runs: list[dict], is_excluded: Callable[[Path], bool]) -> list[dict]`
    - for each `.java` file under each source folder, the class file is `output/<rel>.class`, with `.java` replaced by `.class`
    - a file is recorded when the class exists, its mtime is greater than `eclipse_seen.json["last_scan"]` (0 the first time), and the source sha isn't already seen in `eclipse_seen.json["shas"]` or in any run's `files`
    - entry: `{time: class mtime iso, file, status: "compiled" | "compile_error", error: None, error_count: count of b"Unresolved compilation problem" or None, duration: 0, source: "eclipse", files: [{file, sha}]}`, with a snapshot and an append to `runs.jsonl`
    - when it finishes it writes `last_scan = time.time()` and the updated `shas`
  - `is_excluded_factory(lang_config) -> Callable[[Path], bool]`: the same rule as the agent
  - `prune_excluded(data_dir: Path, is_excluded) -> int`
    - rewrites `runs.jsonl` without the entries whose `file` is excluded
    - deletes snapshots no longer referenced by any entry
    - returns the number of entries removed
    - runs only when `exclude_folders` differs from `eclipse_seen.json["exclude"]`, and then stores the new list
- `pack.collect`:
  1. `prune_excluded` (if the exclusions changed)
  2. `scan_workspaces(recent_workspaces() + [code_folder] + extra_workspaces, ...)`, deduped by `Path.resolve()`
- `pack.extra_report(runs)` returns `{"java_folders": [...]}`, grouped by the source root (`project` folder = the parent of the first folder named `src`, otherwise the file's parent), as `{folder, files: unique file count, last_seen: date}`, sorted by `last_seen` descending, top 15.

- [ ] **Step 1: Write the failing tests**

```python
def test_reads_recent_workspaces(self):
    prefs line: RECENT_WORKSPACES=C\:\\Users\\x\\ws1\nC\:\\Users\\x\\ws2 (both created in tmp)
    self.assertEqual(recent_workspaces(home=tmp_home), [ws1, ws2])

def test_compiled_and_compile_error(self):
    new = scan_workspaces([WS], data_dir, [], lambda p: False)
    by = {Path(e["file"]).name: e for e in new}
    self.assertEqual(by["Main.java"]["status"], "compiled")
    self.assertEqual((by["Broken.java"]["status"], by["Broken.java"]["error_count"]), ("compile_error", 2))

def test_second_scan_records_nothing_new(self): ...
def test_sha_already_logged_by_agent_is_skipped(self): ...
def test_custom_classpath_folders(self): ...    # .classpath src path="source", output path="classes"
def test_skips_metadata(self):                    # Review Focus 4
    put a .classpath + src/X.java + bin/X.class under WS/.metadata/.plugins/p → not recorded

def test_prune_when_exclude_changes(self):
    two entries, one under C:\work → after adding C:\work to exclude_folders, collect() leaves 1 entry
    and the C:\work snapshot is deleted
```

- [ ] **Step 2: Run them**

  Expected: FAIL.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run all tests**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Count Eclipse builds from all recent workspaces and support Java folder exclusions`

---

### Task 11: Dashboard and plan pages with language tabs

**Files:**
- Modify: `dashboard.py`, `track.py` (`main` writes the pages again)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: the `build_report` shape (Task 3) and `all_packs()` (Task 1).
- `write_dashboard(report, path=DASHBOARD_PATH) -> Path`: embeds `{"learner", "generated", "today", "enabled", "overall", "languages": {key: public report}}`. Keys starting with `_` are stripped at every level.
- `write_plan(config, path=PLAN_PATH) -> Path`: embeds `{"courses": {key: {"label", "icon", "editor", "curriculum"}}, "mine": {key: {"plan", "start"} for enabled}}`.
- The JavaScript in the templates:
  - the current single-report rendering becomes `renderLanguage(R, el)`, called once per language tab
  - the existing element ids are prefixed with the language key
  - the existing ids, CSS and chart code are re-used, with Chart.js still at the pinned 4.4.1 cdnjs URL
- **Tab bar:** `Overview` plus one button per `enabled` key. The active tab is saved in `localStorage["tracker.tab"]`, with reads and writes wrapped in `try/catch`.
- **Overview:**
  - cards with the current level name, status (`✅ on track` or `⚠️ N days behind`), `🔥 N-day streak`, and a `levels_done/9` bar
  - each card opens its tab
  - the `🔥 Any-language streak` and `This week: N runs/compiles` lines
  - a stacked bar chart from `overall.daily_by_language`, one dataset per language, coloured with the categorical palette from the `dataviz` skill (load the skill in this task)
  - "Add <Language> with `python tracker\setup.py`" cards for the languages that aren't enabled
- **Language tab:** today's sections. The banner and the "no runs yet" text name the language and editor ("Run a .java file in Eclipse", "Run a .js file in VS Code"). The "all complete" banner says "the <Language> learning path".
- **Error report:** shows `⚠️ Couldn't read <Label> data, see data\send_report.log` and nothing else.
- **Status icons in recent runs:** `success` ✅ / `compiled` ✅ compiled / `error` ❌ / `compile_error` ❌ compile / `stopped` ⏹ / `saved` 💾 saved. Java recent runs show `folder`.
- **Java tab only:** the "Java sources found in" table from `java_folders`, with the hint `Not your learning code? Add the folder to languages.java.exclude_folders in config.json.`
- **`plan.html`:** one tab per pack (all three). The toggle and start preview work per tab. The note says `✅ This is your plan.` for enabled languages with a matching plan and start, otherwise `👀 Preview only.`
- `track.py` `main()` writes both pages again and opens the dashboard as before.

- [ ] **Step 1: Write the failing tests**

```python
def test_dashboard_embeds_each_enabled_language(self):
    html = write_dashboard(sample_report(enabled=["python", "java"])).read_text(encoding="utf-8")
    data = json.loads(re.search(r"const R = (.*?);\n", html).group(1))
    self.assertEqual(sorted(data["languages"]), ["java", "python"])
    self.assertNotIn("_runs", json.dumps(data))

def test_error_language_still_renders_page(self): ...   # languages.java = {"error": "boom", ...} → write succeeds, data has error
def test_plan_has_all_three_courses(self):
    data = embedded(write_plan(config_with_only_python))
    self.assertEqual(sorted(data["courses"]), ["java", "javascript", "python"]); self.assertEqual(list(data["mine"]), ["python"])
def test_script_close_tag_escaped(self): ...             # a file name containing "</script>" doesn't break out
```

  Match the embedding variable to the template: keep `const R = __DATA__;` and `const D = __DATA__;` as they are today.

- [ ] **Step 2: Run them**

  Expected: FAIL.

- [ ] **Step 3: Implement the template and `dashboard.py` changes**

- [ ] **Step 4: Run the tests, then check by eye**

  Run: `python -m unittest discover -s tracker/tests -t tracker -k dashboard`
  Expected: OK.

  Then:
  1. Set `PYTRACKER_HOME` to a temp folder holding a sample config with Python and Java enabled and a few runs. Run `python tracker\track.py`.
  2. Open the page and check:
     - each tab switches
     - the Overview cards open their tabs
     - the charts draw
     - the page has no horizontal scroll at 375px width (use DevTools device mode)
     - dark mode is readable

- [ ] **Step 5: Commit**

  Message: `Dashboard with Overview and per-language tabs; plan page with all three courses`

---

### Task 12: Emails and the daily check

**Files:**
- Modify: `emailer.py`, `send_report.py`
- Test: `tests/test_emails.py`

**Interfaces:**
- Consumes: the `build_report` shape (Task 3) and the email-state shape (Task 2).
- `progress_email(report, since=None) -> (subject, html, text)`:
  - an overview row of tiles (icon, label, current level or "all done", status), then today's section per enabled language
  - the existing section builder becomes `language_section(lang_report, since)`, with `9` replaced by `len(lang_report["levels"])` in the progress bar
  - **Subject:** `📚 Progress: ` + `" · "`-joined parts, one per language: `f"{icon} L{id} {name}"`, plus ` ({n} days behind)` when behind, or `f"{icon} all done"`. Then ` · 🔥 {any_streak}-day streak`.
  - languages with `error` get a one-line "couldn't read" row
- `stuck_email(items: list[tuple[lang_report, reminder: bool]]) -> (subject, html, text)`:
  - one section per language, using today's stuck body
  - **Subject** for 1 item: today's subject with the language icon in front. For several: `⚠️ Stuck in {n} languages: 🐍 L4 Functions · ☕ L2 Control Flow`.
- `inactive_email(items: list[lang_report]) -> (subject, html, text)`:
  - **Subject** for 1 item: `{icon} {days} days without {label}, time for a quick session?`
  - **Subject** for several: `👋 {n} languages need a quick session`
  - the body lists each language with its days inactive and next topic
- Every "Python" in the subjects and headers becomes language-neutral. `From` = `f"Learning Tracker <{sender}>"`.
- `send_report.main()`:
  - builds the report and writes both pages
  - **progress**: same rules as today, one email
  - **stuck**: for each enabled language whose report has a current level with `status == "overdue"`, the gap is checked against `state["languages"][key]["alerts"][str(level_id)]`. All languages that are due go into one `stuck_email`.
  - **inactive**: per language, using `last_inactive_sent`, with a single combined email
  - **after sending:** the state is updated for each language included
  - `--preview` and `--send-now` work as today. Languages with `error` are skipped for alerts.

- [ ] **Step 1: Write the failing tests**

```python
def test_progress_subject_lists_languages(self):
    subject, html, text = progress_email(report(py=("L4", "Functions", 0), java=("L2", "Control Flow", 3), any_streak=15))
    self.assertEqual(subject, "📚 Progress: 🐍 L4 Functions · ☕ L2 Control Flow (3 days behind) · 🔥 15-day streak")
    self.assertNotIn("def ", html)                        # no code in emails

def test_single_language_progress_email(self): ...        # only python enabled → one section, no overview errors
def test_stuck_combined(self):
    subject, _, _ = stuck_email([(py_overdue, False), (java_overdue, True)])
    self.assertTrue(subject.startswith("⚠️ Stuck in 2 languages"))

def test_daily_check_alert_state_per_language(self):
    # Monkeypatch send_email to record calls; python overdue at level 4, java not.
    # Run send_report.main() twice on the same day:
    #   1st → one stuck email; state.languages.python.alerts == {"4": today}
    #   2nd → no stuck email
def test_migrated_state_keeps_reminder_timing(self): ...  # old alerts {"4": today-1} → no stuck email today (reminder_every_days 3)
```

- [ ] **Step 2: Run them**

  Expected: FAIL.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run all tests, then preview the emails by eye**

  Run: `python -m unittest discover -s tracker/tests -t tracker`
  Expected: OK.

  Then run `python tracker\send_report.py --preview` against the sample home from Task 11 and check the preview files by eye.

- [ ] **Step 5: Commit**

  Message: `Multi-language progress email; combined stuck and inactivity alerts per language`

---

### Task 13: Setup wizard, hooks and uninstall

**Files:**
- Modify: `setup.py`
- Test: `tests/test_setup.py`

**Interfaces:**
- Consumes: the packs' `install`, `uninstall` and `self_test` (Tasks 1, 8 and 9); `envvars` (Task 7); `settings` (Task 2).
- `parse_language_choice(text: str, current: list[str]) -> list[str]`:
  - `""` returns `current`
  - `"1,3"` and `"3, 1"` return `["python", "javascript"]` (registry order)
  - anything that isn't in 1–3 raises `ValueError("Enter numbers 1-3, comma-separated")`
- The Python pack's `install` and `uninstall` take over today's `install_logger` (target `usercustomize.py`; it writes the template with `__DATA_DIR__`, `__CODE_FOLDER__` and `__TRACKER_DIR__`). `setup.py` no longer has its own `install_logger`.
- `setup()` flow, following spec §4:
  1. name, emails
  2. the language menu (each line shows the icon, label and `(editor)`; the default is the currently enabled list, or `1` for a new install)
  3. per chosen language: `── {icon} {label} ──`, start date, plan (with that course's totals), code folder (Java's prompt is `Code folder (your Eclipse workspace)`)
  4. the email questions, as today
  5. `save_json(CONFIG_PATH, config)`
  6. for each pack:
     - enabled → `install`, then `self_test`; print `✓ msg` or `✗ msg`
     - disabled with `hook_installed()` → `uninstall` and print it
  7. `schedule_task(send_time)` with the task name `LearningTracker`, then `Unregister-ScheduledTask PythonLearningTracker` (ignore errors)
  8. if `NODE_OPTIONS` or `JAVA_TOOL_OPTIONS` changed, print `↻ Restart Eclipse and VS Code once so they pick up the tracker.`
  9. test email, build the report, write the pages, open `plan.html`
- `--uninstall`: every pack's `uninstall`, the scheduled task (both names), and the password. The data is kept.
- The opening banner is `📚 Learning Tracker: setup`. The final line lists each language: `✅ All set! 🐍 Python (Aggressive) from 25 Oct · ☕ Java (Standard) from 1 Nov`.

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_language_choice(self):
    self.assertEqual(parse_language_choice("3, 1", []), ["python", "javascript"])
    self.assertEqual(parse_language_choice("", ["java"]), ["java"])
    with self.assertRaises(ValueError): parse_language_choice("4", [])

def test_setup_installs_chosen_and_removes_dropped(self):
    # Monkeypatch input()/getpass with answers choosing "1,2"; packs replaced by fakes that record calls,
    # with javascript.hook_installed() → True.
    # Then: python.install and java.install are called, javascript.uninstall is called,
    # and config.languages.javascript.enabled is False with its data folder untouched.
```

- [ ] **Step 2: Run them**

  Expected: FAIL.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run all tests**

  Expected: OK.

- [ ] **Step 5: Commit**

  Message: `Setup asks which languages to learn and installs each language's hook`

---

### Task 14: README and full verification

**Files:**
- Modify: `README.md`

**What to do:**
- Rewrite the README for three languages, keeping today's structure and tone. Change these sections:
  - the title (`📚 Learning Tracker`) and "How it works", with a table of the capture method per language
  - Quick start (the setup questions now include the language menu and per-language questions, and the Eclipse and VS Code restart)
  - Daily use per language
  - The learning plan (three course tables, from spec §8)
  - Rules (counting statuses, Java anywhere with exclusions, browser JavaScript saved)
  - Dashboard (tabs), Emails (combined), Commands (the analyser takes any of the extensions)
  - Configuration (the new `config.json` from spec §3, and a settings table including `extra_workspaces` and `exclude_folders`)
  - Project files (the new tree), Troubleshooting:
    - "Java run not logged": restart Eclipse; check `JAVA_TOOL_OPTIONS`; check the folder isn't excluded
    - "Picked up JAVA_TOOL_OPTIONS line": expected
    - "Node run not logged": restart VS Code; `echo %NODE_OPTIONS%`
    - "A work folder shows in Java sources": use `exclude_folders`
  - Known limits (spec §14), Uninstalling, Privacy (Java snapshots can come from any folder; use exclusions)

**Steps:**

- [ ] **Step 1: Write the README**

- [ ] **Step 2: Run the full test suite**

  Run: `python -m unittest discover -s tracker/tests -t tracker -v`
  Expected: every test OK. List any that were skipped, with the reason (for example no JDK).

- [ ] **Step 3: Check the real install end to end** (on this PC, with the learner's real config)
  1. Run `python tracker\setup.py`. Choose `1,2,3` and keep the Python values.
     - Expect a ✓ for every hook, or a clear ✗ fallback message.
     - Check that `data\python\runs.jsonl` holds all the old runs.
  2. Restart VS Code and Eclipse.
  3. Run one `.py` file, one `.js` file through VS Code, one Java program in Eclipse, and `javac` on a file in an unrelated folder (for example `C:\temp\X.java`).
  4. Run `python tracker\track.py`. Each run should appear in its tab, and the `C:\temp` folder should be listed under "Java sources found in".
  5. Run `python tracker\send_report.py --preview` and check the emails.

- [ ] **Step 4: Commit**

  Message: `README for Python, Java and JavaScript tracking`
