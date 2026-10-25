# Multi-language Learning Tracker: Design

**Date:** 2026-10-25
**Status:** Approved in conversation; waiting for written-spec review
**Scope:** Extend the Python Learning Tracker so one learner can learn and track **Python, Java and JavaScript** at the same time, each with its own course.

---

## 1. Goals and constraints

### Goals
- At setup, a learner chooses **one or more languages**: Python, Java, JavaScript.
- Each language has its **own course**: levels, topics, tips, links, projects, plan lengths and targets.
- Each language is **tracked separately**: its own start date, plan, levels, due dates, streak, stuck and inactive alerts, dashboard tab and email section.
- The learner's normal workflow stays the same:
  - Python and JavaScript are written in **VS Code**.
  - Java is written in **Eclipse**, or compiled from the command line.
  - Learners press Run or Save as usual, with nothing extra to do.

### Constraints
- The tracker stays in **Python, standard library only**. There is no `pip`, and no Node or Java libraries.
- It runs on each learner's own Windows PC, as today. There is no server.
- **Hooks must never break a learner's program.**
- Code never leaves the PC. Emails contain progress numbers, folder names and file names only.
- The existing Python data and settings carry over automatically.

### Out of scope
- Languages other than these three. The design makes adding one a new folder, but none are built now.
- IntelliJ or other Java IDEs. Their runs and command-line `javac` calls are caught by the agent; their internal builds are not.
- Python and JavaScript activity outside their code folders.

---

## 2. Architecture: language packs

One shared engine, plus a self-contained pack per language.

```
tracker/
├── setup.py, track.py, send_report.py, dashboard.py, emailer.py, settings.py   (core engine)
├── analyzer.py          CLI: python tracker\analyzer.py <file>, which picks the pack by extension
├── migrate.py           one-time upgrade from the single-language layout
├── languages/
│   ├── __init__.py      registry: LANGUAGES = {"python": ..., "java": ..., "javascript": ...}
│   ├── base.py          the LanguagePack interface
│   ├── clike.py         shared tokenizer and syntax check for Java and JavaScript
│   ├── python/
│   │   ├── curriculum.json   (today's curriculum.json, moved unchanged)
│   │   ├── analyzer.py       (today's ast analyser, moved)
│   │   ├── run_logger.py     (today's usercustomize template)
│   │   └── pack.py
│   ├── javascript/
│   │   ├── curriculum.json
│   │   ├── analyzer.py
│   │   ├── node_hook.js
│   │   └── pack.py
│   └── java/
│       ├── curriculum.json
│       ├── analyzer.py
│       ├── eclipse_scan.py
│       ├── agent/TrackerAgent.java   (built into tracker-agent.jar by setup)
│       └── pack.py
└── tests/
```

### `LanguagePack` interface (`languages/base.py`)

| Member | Purpose |
|---|---|
| `key`, `label`, `icon`, `editor` | e.g. `"java"`, `"Java"`, `"☕"`, `"Eclipse"` |
| `extensions` | e.g. `{".java"}`; `{".js", ".mjs", ".cjs", ".html"}` |
| `curriculum()` | Loads the pack's `curriculum.json` |
| `analyze(source, path=None)` | Returns `{"topics": set, "score": int, "level": str, "lines": int, "syntax_ok": bool}` |
| `install(lang_config, data_dir)` | Installs the hook. Returns `(ok: bool, message: str)` |
| `uninstall()` | Removes the hook |
| `self_test(data_dir)` | Runs a tiny sample program through the hook and checks a log line appears |
| `collect(lang_config, data_dir, runs)` | Adds the extra entries this language finds on refresh: saved files, or Eclipse builds. Returns a list of new entries |

The engine (`track.py`) loops over the enabled languages and builds one report per language through this interface. It never branches on the language name.

---

## 3. Configuration (`config.json`)

```json
{
  "learner_name": "Soumya",
  "email":  { "enabled": true, "to": ["you@gmail.com"], "sender": "you@gmail.com",
              "send_days": ["Monday", "Thursday"], "send_time": "08:00" },
  "alerts": { "stuck_enabled": true, "reminder_every_days": 3, "inactive_after_days": 5 },
  "languages": {
    "python":     { "enabled": true,  "start_date": "2026-10-25", "plan": "aggressive",
                    "code_folder": "C:\\Python" },
    "java":       { "enabled": true,  "start_date": "2026-11-01", "plan": "standard",
                    "code_folder": "C:\\Users\\NRI\\eclipse-workspace",
                    "extra_workspaces": [], "exclude_folders": [] },
    "javascript": { "enabled": false, "start_date": "", "plan": "standard",
                    "code_folder": "C:\\JavaScript" }
  }
}
```

- `code_folder`:
  - **Python and JavaScript:** only activity inside this folder counts.
  - **Java:** this is the default Eclipse workspace. Java activity counts anywhere on the PC (see section 6).
- `java.extra_workspaces`: more folders to scan for Eclipse builds, on top of the workspaces found automatically.
- `java.exclude_folders`: folders whose Java activity never counts. Adding one also removes that folder's **past** entries and snapshots on the next refresh.
- `settings.load_config()` fills in defaults for every language block, so a partial or old config still loads.

---

## 4. Setup wizard (`python tracker\setup.py`)

### Flow
1. Your name, then email(s) for reports.
2. **Which languages are you learning?** The learner enters numbers, comma-separated: `1` 🐍 Python (VS Code), `2` ☕ Java (Eclipse), `3` 🟨 JavaScript (VS Code). Pressing Enter keeps the current choice.
3. For each chosen language:
   - start date (Enter for today)
   - plan (Standard or Aggressive, shown with that course's total days)
   - code folder (defaults: `C:\Python`, `%USERPROFILE%\eclipse-workspace`, `C:\JavaScript`)
4. Email days, time, Gmail address, App Password and test email, all as today.
5. Install hooks for the chosen languages and remove hooks for languages no longer chosen (their data is kept). Run each pack's `self_test` and print ✓ or a specific fix.
6. Schedule the daily task `LearningTracker`, and remove the old `PythonLearningTracker` task if it exists.
7. Print: "Restart Eclipse and VS Code once so they pick up the tracker." This is printed only when the Java or JavaScript environment variables changed.

### Checking tools
- **Java:** setup finds `javac` on `PATH` or under `JAVA_HOME`.
  - If found, it builds the agent jar and sets `JAVA_TOOL_OPTIONS`.
  - If not found, Java uses the **Eclipse-build scan only**, and setup says how to install or point to a JDK.
- **JavaScript:** setup finds `node`.
  - If found, it sets `NODE_OPTIONS`.
  - If not found, JavaScript uses **saved-file tracking only**.

Re-running setup works as today: pressing Enter keeps each current value. `--uninstall` removes every hook, both environment-variable additions and the task, and keeps all data.

---

## 5. Data layout and migration

```
data/
├── python/      runs.jsonl, snapshots/
├── java/        runs.jsonl, snapshots/, eclipse_seen.json
├── javascript/  runs.jsonl, snapshots/, saved_seen.json
├── email_state.json
└── send_report.log
```

### Run-log entry (all languages)
```json
{"time": "2026-10-25T09:12:03", "file": "C:\\...\\Main.java",
 "status": "success | error | stopped | compiled | compile_error | saved",
 "error": "NullPointerException", "error_count": null,
 "duration": 0.4, "source": "hook | agent | javac | eclipse | saved",
 "files": [{"file": "C:\\...\\Main.java", "sha": "ab12..."}]}
```

**Which statuses count toward topics and streak:**
- `success` and `compiled` always count.
- `saved` counts only when the file passed the syntax check. Saved entries are only created where runs can't be seen (see section 6).
- `error`, `stopped` and `compile_error` count as activity for the inactivity check, but not toward topics or streak.

Snapshots are stored as `snapshots/<sha><ext>`. The run logger and analyser read the extension from the stored file name.

### Migration (`migrate.py`, runs automatically from `load_config()` once)
1. If `config.json` has top-level `start_date`, `plan` or `code_folder`, move them into `languages.python` and set `enabled: true`.
2. Move `data/runs.jsonl` to `data/python/runs.jsonl`, and `data/snapshots/*` to `data/python/snapshots/`. Convert old entries (`"sha": x`) to the new shape (`"files": [{"file", "sha"}]`, `"source": "hook"`).
3. Convert `email_state.json` so the old stuck and inactive timestamps go under `python`.
4. Reinstall the Python `usercustomize.py`, so it writes to `data/python/`.
5. Write `config.json`. The migration is safe to run twice: if the layout is already new, it does nothing.

The tracker folder stays at `C:\Python\tracker`.

---

## 6. Capturing activity

### 🐍 Python: unchanged
`usercustomize.py` is installed exactly as today. The only change is that it writes to `data/python/`, in the new entry shape.

### 🟨 JavaScript: Node hook (`languages/javascript/node_hook.js`)

**Install:**
- Setup **appends** `--require "<tracker>\languages\javascript\node_hook.js"` to the user `NODE_OPTIONS` (in `HKCU\Environment`), keeping anything already there.
- Uninstall removes only that part.
- The hook reads its data folder and code folder from `languages/javascript/hook.json`, which setup writes.

**What it records:**
- Only scripts (`process.argv[1]`) inside the JavaScript `code_folder`, and not under `tracker\` or `node_modules\`. Any other Node process (npm, VS Code tools) does nothing.
- The status:

| Event | Status logged |
|---|---|
| Uncaught exception | `error`, with the error name. Caught with `process.on('uncaughtExceptionMonitor')`, which doesn't change Node's behaviour. Unhandled promise rejections arrive here too (Node 15+). |
| `SIGINT` | `stopped`. The hook records it, then calls `process.exit(130)`, which matches Node's default. |
| Exit code 0 | `success` |
| Any other exit code | `error`, with `"exit code N"` as the error |

- The entry and snapshot are written synchronously in `process.on('exit')`. Everything is inside `try/catch`.

### 🟨 JavaScript: saved-file fallback (`pack.collect`)

Every refresh scans `code_folder`. A file version (sha) with no recorded run becomes a `saved` entry, using the file's modified time and a snapshot. **This applies only to:**
- `.html` files. Their inline `<script>` blocks are analysed.
- `.js` files referenced by `<script src="...">` in an `.html` file in the same folder.
- All `.js` files, but only if the Node hook isn't installed.

`saved_seen.json` remembers the shas already recorded, so nothing is counted twice.

**Limit:** only the latest version of each file between two refreshes is seen.

### ☕ Java: agent (`languages/java/agent/TrackerAgent.java` → `tracker-agent.jar`)

**Build (at setup):**
- `javac --release 8` compiles the agent.
- Python's `zipfile` writes the jar with a `META-INF/MANIFEST.MF` containing `Premain-Class: TrackerAgent`. No `jar` tool is needed.
- Settings (data folder, exclude list, tracker folder) go in `agent.properties` next to the jar, so the paths aren't put into the environment variable.

**Install:**
- Setup appends `-javaagent:<path to tracker-agent.jar>` to the user `JAVA_TOOL_OPTIONS`, keeping anything already there. Uninstall removes only that part.
- The JVM then prints `Picked up JAVA_TOOL_OPTIONS: ...` once per Java program. This was accepted in the design discussion.
- If the jar path contains a space, setup refuses and explains why. The default `C:\Python\tracker` has no spaces.

**What it records** (in `premain`; every step inside `try/catch (Throwable)`):

1. **Identify the process** from `sun.java.command`:

| Process | What the agent does |
|---|---|
| `com.sun.tools.javac.Main` (command-line `javac`) | **Compile mode** |
| A `.java` path (single-file source launch, `java Foo.java`) | **Run mode** on that file |
| A main class name | **Run mode**. The agent finds `Foo.java` by mapping each classpath directory to its source folder (`bin` → `src`, `target/classes` → `src/main/java`, or the folder itself), then searching for `<package path>/<Foo>.java` |
| Eclipse itself (`org.eclipse.equinox.launcher...`), Maven or Gradle daemons, a `-jar` launch, or no source file found | Nothing is recorded |

2. **Excluded folders:** any source under `Program Files`, `Windows`, `AppData`, `.m2`, `.gradle`, `.p2`, `node_modules`, the tracker folder or `exclude_folders` is ignored.

3. **Compile mode:**
   - The agent reads the `.java` arguments, including `@argfiles`, and records each file's modified time and its expected `.class` file (from `-d`, or next to the source).
   - A shutdown hook then checks whether every expected `.class` is newer than the start time. If so, the status is `compiled`; otherwise it's `compile_error`.
   - It snapshots each source file.

4. **Run mode:**
   - The agent wraps the default uncaught exception handler: it records the exception's simple class name, then hands over to the previous handler, or prints the stack trace like the default one.
   - A shutdown hook writes `error` if an uncaught exception happened, otherwise `success`.
   - Snapshots cover the main file **plus every `.java` file in the same package folder**.

5. **Writing:** the agent appends JSON to `data/java/runs.jsonl` by hand (no libraries). The shutdown hook stops working after 2 seconds.

**Known limits:**
- Eclipse's Stop button ends the JVM abruptly, so that run isn't logged.
- `System.exit(non-zero)` is logged as `success`.

### ☕ Java: Eclipse build scan (`languages/java/eclipse_scan.py`, through `pack.collect`)

Eclipse compiles inside its own process, so its builds are found on every refresh.

**Workspaces scanned:**
- every workspace in Eclipse's `RECENT_WORKSPACES`, read from `org.eclipse.ui.ide.prefs` under each Eclipse install's `configuration\.settings` and under `%USERPROFILE%\.eclipse\`
- plus `code_folder`, plus `extra_workspaces`

**For each project:**
- The source and output folders come from `.classpath` (`kind="src"` and `kind="output"`), with `src` and `bin` as the defaults.
- A `.java` file whose `.class` is newer than the last scan, and whose source sha isn't in `eclipse_seen.json` yet, is recorded:
  - `compiled` if the `.class` bytes don't contain `Unresolved compilation problem`
  - `compile_error` otherwise, with `error_count` counting how often that marker appears
- The entry time is the `.class` file's modified time, and `source` is `"eclipse"`.

If the agent already logged the same sha (for example the file was run), no duplicate is added. The same exclusions as the agent apply.

**Limit:** only the latest build of each file between two refreshes is seen.

### ☕ Java: excluding a folder
When `exclude_folders` changes, the next refresh removes the matching entries from `data/java/runs.jsonl`, and any snapshots no longer referenced.

---

## 7. Analysis

### Python
Today's `ast` analyser, moved to `languages/python/analyzer.py`. It behaves exactly as before.

### Shared tokenizer for Java and JavaScript (`languages/clike.py`)
- Removes `//` and `/* */` comments, and records `has_comment`.
- Replaces the contents of string and char literals with a placeholder. JavaScript `'`, `"` and template literals are handled; template literals are recorded and their `${...}` expressions are kept as code. Java `"`, `'` and text blocks `"""` are handled.
- Treats JavaScript regex literals as strings, using a simple heuristic: a `/` after an operator, `(`, `,` or `=`.
- `syntax_ok` is true when the brackets `()[]{}` balance and every string and comment is closed.
- Returns the cleaned code, so topic patterns never match text inside comments or strings.

### Topic rules
Each pack's `analyzer.py` has a table `TOPIC_RULES = {topic_id: [compiled regex, ...]}`, run over the cleaned code. A topic is found when any of its patterns matches. Some topics need two conditions (for example `try_with_resources` needs `try\s*\(`); those use a small function instead of a regex. Every topic id in a course must have a rule; a test checks this.

### Complexity score (same formula for every language)
```
score = lines ÷ 10 + functions × 2 + classes × 4 + loops + conditions + try × 2 + imports
```
- **Java:**
  - Functions are method declarations.
  - The class that contains `public static void main` and the `main` method itself are **not counted**.
  - Imports are `import` lines.
- **JavaScript:**
  - Functions are `function` declarations or expressions and arrow functions.
  - Imports are `import`, or `require(` calls.
- The level bands are the same as Python's: 0–10 Beginner, 11–30 Intermediate, 31+ Advanced.

### CLI
`python tracker\analyzer.py file.py|file.java|file.js|file.html` picks the pack by file extension and prints the topics and the score, as today.

---

## 8. Courses

Each `languages/<lang>/curriculum.json` uses the existing format:
- `plans`: daily-run, weekly-lines and streak targets, labels and icons
- `levels`: id, name, tier, `days.standard` and `days.aggressive`, project, links, and topics with id, name, link and "try"
- new top-level fields: `"language"`, `"editor"` and `"extensions"`

**Python:** unchanged (9 levels, 132 days Standard, 65 days Aggressive).

### ☕ Java (Eclipse): 132 days Standard / 65 days Aggressive

| # | Level | Tier | Std | Agg | Topics |
|---|---|---|---|---|---|
| 1 | Java Basics | Beginner | 7 | 3 | class with `main`, `System.out.println`, primitive variables, `String`, `Scanner` input, operators, comments |
| 2 | Control Flow | Beginner | 10 | 5 | if/else, `switch`, for loops, while and do-while, break/continue |
| 3 | Arrays & Strings | Beginner | 12 | 6 | arrays, enhanced for, 2D arrays, String methods, `StringBuilder` |
| 4 | Methods | Intermediate | 12 | 6 | static methods, parameters and return, overloading, recursion |
| 5 | Classes & Objects | Intermediate | 14 | 7 | class and `new`, constructors, `this`, private fields with getters/setters, static members |
| 6 | Inheritance & Interfaces | Intermediate | 14 | 7 | `extends`, `super`, `@Override`, abstract classes, interfaces, polymorphism |
| 7 | Exceptions & Files | Advanced | 14 | 7 | try/catch/finally, throw/throws, custom exception, try-with-resources, reading files, writing files |
| 8 | Collections & Generics | Advanced | 21 | 10 | `ArrayList`, `HashMap`, `HashSet`, generics `<T>`, `Comparator`/`Comparable` |
| 9 | Modern Java & Projects | Advanced | 28 | 14 | lambdas, streams, enums/records, packages and imports, JUnit tests |

Plan targets are the same as Python's: Standard 2 runs a day and 150 lines a week; Aggressive 5 runs a day and 400 lines a week; a 30-day streak. For Java, "runs" includes successful compiles.

Links come from dev.java, the Oracle Java Tutorials and W3Schools Java.

### 🟨 JavaScript (VS Code + Node or browser): 132 days Standard / 65 days Aggressive

| # | Level | Tier | Std | Agg | Topics |
|---|---|---|---|---|---|
| 1 | JS Basics | Beginner | 7 | 3 | `console.log`, `let`/`const`, numbers and strings, template literals, operators, comments |
| 2 | Control Flow | Beginner | 10 | 5 | if/else, `switch`, for loops, while loops, `===` and ternary, break/continue |
| 3 | Functions | Beginner | 12 | 6 | function declarations, parameters and defaults, return, arrow functions, scope |
| 4 | Arrays & Objects | Intermediate | 14 | 7 | arrays and their methods, `map`/`filter`/`reduce`, objects, destructuring, spread `...` |
| 5 | DOM & Events | Intermediate | 14 | 7 | `querySelector`, changing text/HTML, `addEventListener`, creating elements, forms |
| 6 | Errors, JSON & Modules | Intermediate | 10 | 5 | try/catch, throw, `JSON.parse`/`stringify`, `import`/`export`, `require` |
| 7 | Asynchronous JS | Advanced | 21 | 10 | `setTimeout` and callbacks, promises, `async`/`await`, `fetch` |
| 8 | Classes & Modern JS | Advanced | 16 | 8 | `class`, constructor, `extends`/`super`, getters/setters and static, `Map`/`Set`, optional chaining `?.` |
| 9 | Node & Real Projects | Advanced | 28 | 14 | `fs` files, `process.argv`, an npm package, tests (`node:test` and `assert`), HTTP server |

Plan targets are the same as Python's. Links come from MDN and javascript.info.

Every level has 2 links and a practice project (for example Java L5: *a bank account class with deposit and withdraw*; JavaScript L5: *a to-do list page*). Every topic has a link and a "try this" tip. The full JSON content is written during implementation and reviewed by the project owner.

---

## 9. Engine (`track.py`)

- `build_report(config, today)` returns:
  ```
  {"learner", "generated", "today",
   "languages": {key: <language report>},
   "overall": {"any_streak", "week_activity",
               "daily_by_language": [{"date": ..., "python": n, "java": n, ...}] (14 days)}}
  ```
- A **language report** has the same fields as today's single report (levels, current level, stats, recent runs, errors, saved-not-run), plus:
  - `language`, `label`, `icon`
  - for Java: `java_folders`, a list of `{folder, files, last_seen}`
- For each enabled language, the engine:
  1. loads its runs
  2. calls `pack.collect` and appends the new entries
  3. applies exclusions
  4. analyses each snapshot through `pack.analyze`
  5. builds levels from that pack's curriculum, using the language's own `start_date` and `plan`
- The rules for topics done, levels done, due dates, stuck, days behind, streak and inactivity are **unchanged**. They're applied per language, with the counting statuses from section 5.
- If one language fails, its exception is caught and logged, and its report becomes `{"error": "..."}`. The other languages still build.

---

## 10. Dashboard and plan pages (`dashboard.py`)

### `dashboard.html`
- The title is "📚 <name>'s Learning Tracker".
- The tabs are **Overview**, then one per enabled language (🐍 / ☕ / 🟨).
- The last tab used is remembered in `localStorage`, inside `try/catch`. Overview is the default.

**Overview tab:**
- One card per enabled language: current level, status (on track or N days behind), streak, and a levels progress bar. Clicking a card opens that language's tab.
- The any-language streak and this week's activity count.
- A 14-day activity chart, stacked by language.

**Each language tab:**
- Everything today's dashboard has (banner, KPI cards, roadmap, current level with topic chips, "try next", links, project, targets, plan-vs-actual chart, daily chart, errors, recent runs), built only from that language's report.
- Status icons: ✅ success or compiled, ❌ error or compile error, ⏹ stopped, 💾 saved. Java's recent activity shows the folder.
- A language whose report has an error shows "Couldn't read <Language> data, see data\send_report.log".

**Java tab extra:** the "Java sources found in" table (folder, number of files, last seen), with a hint on how to exclude a folder.

**Languages that aren't enabled** get no tab. The Overview shows a small "Add Java with `python tracker\setup.py`" card instead.

### `plan.html`
- One tab for **each of the three languages, enabled or not**.
- Each tab has the Standard/Aggressive toggle, a start-date preview, and all levels with due dates, topics, links and projects.
- Enabled languages show "✅ your plan" with their own start date and plan. The others show "👀 preview".

Chart.js is loaded from the CDN at a fixed version, as today. Everything except the charts works offline.

---

## 11. Emails and alerts (`emailer.py`, `send_report.py`)

| Email | Behaviour |
|---|---|
| 📧 Progress report | One email per send day. An overview row (one tile per language), then a section per enabled language: level, status, progress bar, targets, files since the last report. Subject example: `📚 Progress: 🐍 L4 Functions · ☕ L2 (3 days behind) · 🔥 15-day streak` |
| ⚠️ Stuck alert | Worked out per language, using that language's due dates and `reminder_every_days`. All languages due an alert on the same day go into **one email**, with a section each (days over, topics to do with links, tips, impact on finish date). |
| 👋 Inactivity nudge | Per language. "Activity" means any entry for that language. All languages due a nudge on the same day go into one email. |

- `email_state.json`:
  ```
  {"progress_last_sent": ...,
   "python": {"stuck_last_sent": ..., "inactive_last_sent": ...},
   "java": {...},
   "javascript": {...}}
  ```
- `--preview` and `--send-now` work as today.
- The sender's display name becomes "Learning Tracker".

---

## 12. Error handling

- **Hooks:**
  - Python: every step is inside `try/except`, as today.
  - Node: every step is inside `try/catch`, and the hook never adds a listener that changes Node's default behaviour, except `SIGINT`, which exits with the same code.
  - Java agent: `catch (Throwable)` everywhere, and a 2-second limit on the shutdown hook. The agent never throws out of `premain`.
- **Data:**
  - Broken JSON lines in `runs.jsonl` are skipped.
  - A missing snapshot still counts as activity but adds no topics.
  - An unreadable file during a scan is skipped and logged.
- **Per-language isolation** in the engine, dashboard and emails (see section 9).
- **Setup:** every install step reports ✓ or a specific fix. A failed self-test doesn't stop setup; the language falls back to scan-only and setup says so.
- **Environment variables:**
  - They're written to `HKCU\Environment` through PowerShell, then a `WM_SETTINGCHANGE` broadcast is sent.
  - Existing values are kept, and the tracker's part is added or removed as a single token.

---

## 13. Testing (`tests/`, `python -m unittest discover tracker\tests`)

All tests use `unittest` and a temporary `PYTRACKER_HOME`.

| Area | What's covered |
|---|---|
| `clike` tokenizer | Comments, strings, template literals with `${}`, Java text blocks, regex literals, unbalanced brackets and unclosed strings |
| Java and JavaScript analysers | A sample per topic id, and every curriculum topic id has a rule. Negative cases: keywords inside comments or strings don't count, and a Java Hello World scores Beginner |
| Python analyser | The existing behaviour stays the same after the move |
| Migration | An old config, runs, snapshots and email state convert correctly. Running it twice changes nothing |
| Engine | Levels, due dates, streaks, stuck and inactive status per language from sample runs, including `compiled`, `compile_error` and `saved`. One language failing doesn't stop the others |
| Eclipse scan | Sample workspace with `.classpath`, `src/` and `bin/`, using `.class` files with and without the error marker. Reading the recent-workspaces prefs. Exclusions, and removing past entries when `exclude_folders` changes |
| JavaScript saved files | An `.html` page with an inline script, a `.js` file linked from HTML, an unlinked `.js` file (not counted), and a sha that's already been seen |
| Environment-variable editing | Adding to and removing from a `NODE_OPTIONS` or `JAVA_TOOL_OPTIONS` string with existing values, using pure string functions |
| Emails | A progress email with one language and with three. Combined stuck and inactivity emails |
| End-to-end, skipped if the tool is missing | `node` runs a success, an error and a non-zero-exit script through the hook. `javac` compiles a good and a bad file with the agent. `java` runs a program that succeeds and one that throws |

The README is rewritten for three languages: setup, what counts per language, the Eclipse and VS Code restart, the Java exclusions, and the known limits.

---

## 14. Known limits (documented in the README)

- **Java:**
  - Stopping a run with Eclipse's Stop button isn't logged.
  - `System.exit(non-zero)` counts as success.
  - Only the latest Eclipse build of each file between refreshes is seen.
  - The `Picked up JAVA_TOOL_OPTIONS` line appears in every Java program's console.
- **JavaScript:** browser code counts as "saved" (a syntax check only, not a real run), and only the latest version between refreshes is seen.
- **Topic detection for Java and JavaScript** uses patterns, not a full parser. It's accurate for learner-level code, but unusual formatting can be missed.
- After setup changes the Java or JavaScript hooks, Eclipse and VS Code must be restarted once.
