# 📚 Learning Tracker

A personal tracker that follows your learning of **🐍 Python, ☕ Java and 🟨 JavaScript**, from **Beginner to Advanced**, automatically.

You write and run code as usual: Python and JavaScript in VS Code, Java in Eclipse. The tracker logs each run, reads your code to see which topics you've used, ticks off topics and levels, and shows your progress on a dashboard. It also emails you progress reports and alerts when you fall behind.

Learn one language or all three at once. Each language has its own course, start date, plan and code folder, and is tracked separately.

Standard Python only: no `pip install` needed.

---

## Contents

1. [How it works](#how-it-works)
2. [Quick start](#quick-start)
3. [Daily use](#daily-use)
4. [The learning plan](#the-learning-plan)
5. [Rules: what counts](#rules-what-counts)
6. [Complexity score](#complexity-score)
7. [Dashboard](#dashboard)
8. [Emails](#emails)
9. [Commands](#commands)
10. [Configuration (`config.json`)](#configuration-configjson)
11. [Gmail App Password](#gmail-app-password)
12. [Project files](#project-files)
13. [Troubleshooting](#troubleshooting)
14. [Known limits](#known-limits)
15. [Uninstalling](#uninstalling)
16. [Privacy](#privacy)

---

## How it works

```
 ⚙️ Setup  →  ▶️ Code as usual  →  🔍 Analyse  →  🎓 Level check  →  📊📧 Report
 (once)       (Run / Save)        (reads code     (all topics done   (dashboard +
                                   from runs)      = level done)      emails)
```

1. **Setup (once):** `setup.py` asks which languages you're learning and a few questions about each, saves your settings, installs each language's hook and schedules a daily task.
2. **Capture:** each language has its own way of seeing what you run:

| | How it's captured | What is logged |
|---|---|---|
| 🐍 **Python** (VS Code) | A small hook (`usercustomize.py`) that Python loads automatically | Every script run inside your Python folder: time, file, result (success / error / stopped), error type, code snapshot |
| 🟨 **JavaScript** (VS Code) | A Node hook, added to the `NODE_OPTIONS` setting | Every `node` script run inside your JavaScript folder. **Browser JavaScript** can't be seen running, so a `.html` page, and the `.js` files it links to, are logged as 💾 *saved* when they pass a syntax check |
| ☕ **Java** (Eclipse) | A small Java agent, added to the `JAVA_TOOL_OPTIONS` setting, plus a scan of your Eclipse workspaces | Every `javac` compile and every Java program you run, **from any folder** (except the exclusions below), plus the builds Eclipse does in its recent workspaces |

3. **Analyse:** the analyser reads each code snapshot (without running it again) to find the topics used and a complexity score.
4. **Level check:** topics from counted runs are ticked off. When every topic in a level is done, the level is complete. If the current level isn't done by its due date, you're **stuck**.
5. **Report:** the dashboard is rebuilt, and emails are sent on your chosen days, plus alerts when stuck or inactive.

---

## Quick start

### 1. Get a Gmail App Password (for emails)

1. Turn on **2-Step Verification**: <https://myaccount.google.com/signinoptions/two-step-verification>
2. Create an App Password: <https://myaccount.google.com/apppasswords>
   - Name it something like `Python Tracker` and click **Create**.
   - Copy the **16-letter** password it shows. It is shown only once.

Don't paste the App Password anywhere except the setup wizard's hidden prompt.

### 2. Run the setup wizard

From `C:\Python` in the VS Code terminal:

```powershell
python tracker\setup.py
```

| Question | What to enter |
|---|---|
| Your name | Your first name |
| Email(s) for reports | Where reports go (comma-separate several) |
| Languages | Numbers, comma-separated: `1` 🐍 Python, `2` ☕ Java, `3` 🟨 JavaScript. For example `1,2,3`. Enter keeps the current choice. |
| *For each language you chose:* Start date | `YYYY-MM-DD`, or Enter for today |
| Plan | `1` Standard or `2` Aggressive (shown with that course's total days) |
| Code folder | Enter to keep the default: `C:\Python`, your `eclipse-workspace` folder (Java), `C:\JavaScript` |
| Progress email days | e.g. `Mon,Thu` |
| Time to check and send emails | 24-hour, e.g. `08:00` |
| Set up email sending now? | `y` |
| Gmail address to send from | The account the App Password belongs to |
| Gmail App Password | Paste **once**, press Enter (nothing shows while you paste) |
| Send a test email now? | `y` |

When it finishes you should see a line for each step, for example:

```
✓ Saved C:\Python\tracker\config.json
✓ App Password stored in your Windows user environment (PYTRACKER_GMAIL_APP_PASSWORD)
✓ 🐍 Run logger installed (...\site-packages\usercustomize.py)
✓ ☕ Java agent installed
✓ 🟨 Node hook installed
✓ Daily task 'LearningTracker' scheduled at 08:00 (runs later if the PC was off)
↻ Restart Eclipse and VS Code once so they pick up the tracker.
✓ Test email sent to you@gmail.com

✅ All set! 🐍 Python (Standard) from 25 Oct · ☕ Java (Standard) from 25 Oct · 🟨 JavaScript (Standard) from 25 Oct
   Write and run code in your folders as usual; it's tracked automatically.
   Refresh the dashboard any time with:  python tracker\track.py
```

A ✗ line says what went wrong and how to fix it. Your learning plan (`plan.html`) then opens in the browser.

**Restart Eclipse and VS Code once** after setup, so they pick up the new settings. Programs that were already open don't have them.

What you need on your PC:

- **Java:** a **JDK** (Java 8 or newer, any version) for the agent. Setup finds it even when it isn't on your `PATH` (it looks at `JAVA_HOME` and the usual `C:\Program Files` folders). **Without `javac`**, Java still works from the Eclipse-build scan, but runs outside Eclipse aren't seen.
- **JavaScript:** Node.js. Without `node`, JavaScript is tracked from saved files only.

### 3. After installing: check it works

For each language you chose:

1. Run one file: a `.py` file and a `.js` file from VS Code, a Java program from Eclipse.
2. Refresh the dashboard: `python tracker\track.py`.
3. Open the language's tab. The run should be listed under **Recent runs**.

If it isn't there, see [Troubleshooting](#troubleshooting).

**Setup runs only once.** Nothing needs to be started after you switch on the PC. Re-run it any time to change settings or add a language.

**Upgrading from the Python-only tracker?** Your settings and history move automatically the first time the tracker runs. Re-run `python tracker\setup.py` once so the Python logger writes to its new place and you can add Java or JavaScript.

---

## Daily use

| When | What you do |
|---|---|
| Every day | Study the current level's links, then write and run practice code: 🐍 Python in `C:\Python` (VS Code), ☕ Java in Eclipse (or compile with `javac`), 🟨 JavaScript in `C:\JavaScript` (VS Code, or open `.html` pages in the browser). That's all. |
| Anytime | Open the dashboard: `file:///C:/Python/tracker/dashboard.html` (bookmark it) |
| Email days | 📧 A progress report arrives (default Monday and Thursday) |
| If stuck | ⚠️ An alert arrives the day after a level's due date, then a reminder every 3 days |
| If inactive | 👋 A nudge arrives after 5 days with no activity |

Tips:

- Only code that **runs successfully** (or compiles) counts. A file that crashes doesn't tick topics off. See [Rules](#rules-what-counts).
- 🐍 Python: files that are only **imported** by another script aren't analysed. Run them directly too if you want their topics counted.
- ☕ Java: run or compile the class you want counted. A run also snapshots the other `.java` files in the same package folder.
- 🟨 JavaScript in the browser: just save the page. It's counted as 💾 saved if it passes a syntax check (it isn't a real run).
- Anything inside `C:\Python\tracker\` is ignored, so the tracker's own code never counts as practice.

---

## The learning plan

Each language has its own course of 9 levels across 3 tiers. Both plans cover the same levels and topics; only the time per level changes. The plan targets are the same for every language.

| | 📘 Standard | 🚀 Aggressive |
|---|---|---|
| Total length | 132 days (~4.5 months) | 65 days (~2 months) |
| Daily effort | 30–45 min | 1.5–2 hours |
| Daily target | 2 successful runs | 5 successful runs |
| Weekly target | 150 lines | 400 lines |
| Streak target | 30 days | 30 days |

For Java, "runs" includes successful compiles.

### 🐍 Python

| # | Level | Tier | Standard | Aggressive | Topics tracked |
|---|---|---|---|---|---|
| 1 | Python Basics | 🟢 Beginner | 7 d | 3 d | `print()`, variables, numbers and strings, `input()`, operators, comments |
| 2 | Control Flow | 🟢 Beginner | 10 d | 5 d | if/elif/else, for loops, while loops, `range()`, break/continue |
| 3 | Data Structures | 🟢 Beginner | 14 d | 7 d | lists, tuples, dictionaries, sets, slicing, list methods |
| 4 | Functions | 🟡 Intermediate | 14 d | 7 d | `def`, parameters, return, default arguments, lambda, scope (global/nonlocal) |
| 5 | Files & Errors | 🟡 Intermediate | 10 d | 5 d | `with open()`, reading files, writing files, try/except, raise, json |
| 6 | Modules & Packages | 🟡 Intermediate | 7 d | 4 d | import, from … import, standard library, your own module, a pip package |
| 7 | Object-Oriented Programming | 🔴 Advanced | 21 d | 10 d | class, `__init__`/self, methods, inheritance, special methods, class attributes |
| 8 | Advanced Python | 🔴 Advanced | 21 d | 10 d | comprehensions, generators, decorators, context managers, type hints, `*args`/`**kwargs` |
| 9 | Testing & Real Projects | 🔴 Advanced | 28 d | 14 d | unittest/pytest, assert, web APIs, `if __name__ == '__main__'`, command-line arguments |

### ☕ Java

| # | Level | Tier | Standard | Aggressive | Topics tracked |
|---|---|---|---|---|---|
| 1 | Java Basics | 🟢 Beginner | 7 d | 3 d | class with `main()`, `System.out.println`, primitive variables, `String`, `Scanner` input, operators, comments |
| 2 | Control Flow | 🟢 Beginner | 10 d | 5 d | if/else, `switch`, for loops, while and do-while, break/continue |
| 3 | Arrays & Strings | 🟢 Beginner | 12 d | 6 d | arrays, enhanced for, 2D arrays, String methods, `StringBuilder` |
| 4 | Methods | 🟡 Intermediate | 12 d | 6 d | static methods, parameters and return, overloading, recursion |
| 5 | Classes & Objects | 🟡 Intermediate | 14 d | 7 d | class and `new`, constructors, `this`, private fields with getters, static members |
| 6 | Inheritance & Interfaces | 🟡 Intermediate | 14 d | 7 d | `extends`, `super`, `@Override`, abstract classes, interfaces, polymorphism |
| 7 | Exceptions & Files | 🔴 Advanced | 14 d | 7 d | try/catch/finally, throw/throws, custom exception, try-with-resources, reading files, writing files |
| 8 | Collections & Generics | 🔴 Advanced | 21 d | 10 d | `ArrayList`, `HashMap`, `HashSet`, generics, `Comparator`/`Comparable` |
| 9 | Modern Java & Projects | 🔴 Advanced | 28 d | 14 d | lambdas, streams, enums and records, packages and imports, JUnit tests |

### 🟨 JavaScript

| # | Level | Tier | Standard | Aggressive | Topics tracked |
|---|---|---|---|---|---|
| 1 | JS Basics | 🟢 Beginner | 7 d | 3 d | `console.log`, `let`/`const`, numbers and strings, template literals, operators, comments |
| 2 | Control Flow | 🟢 Beginner | 10 d | 5 d | if/else, `switch`, for loops, while loops, `===` and ternary, break/continue |
| 3 | Functions | 🟢 Beginner | 12 d | 6 d | function declarations, default parameters, return, arrow functions, scope and closures |
| 4 | Arrays & Objects | 🟡 Intermediate | 14 d | 7 d | arrays, `map`/`filter`/`reduce`, objects, destructuring, spread `...` |
| 5 | DOM & Events | 🟡 Intermediate | 14 d | 7 d | `querySelector`, changing text and HTML, `addEventListener`, creating elements, forms |
| 6 | Errors, JSON & Modules | 🟡 Intermediate | 10 d | 5 d | try/catch, throw, `JSON.parse`/`stringify`, `import`/`export`, `require` |
| 7 | Asynchronous JS | 🔴 Advanced | 21 d | 10 d | `setTimeout` and callbacks, promises, `async`/`await`, `fetch` |
| 8 | Classes & Modern JS | 🔴 Advanced | 16 d | 8 d | `class` and constructor, `extends`/`super`, getters/setters and static, `Map`/`Set`, optional chaining `?.` |
| 9 | Node & Real Projects | 🔴 Advanced | 28 d | 14 d | `fs` files, `process.argv`, an npm package, `node:test` and `assert`, HTTP server |

Each level also has learning links and a practice project. See `plan.html` (it has a tab for each language, even ones you haven't chosen) or the `curriculum.json` file in each language's folder under `languages\`.

---

## Rules: what counts

Everything below is worked out **per language**, using that language's own start date and plan.

| Rule | Meaning |
|---|---|
| **Topic done** | The topic appears in code that **counted** on or after that language's start date (see the next table). |
| **Level done** | Every topic in the level is done **and** the previous level is done. Levels complete in order, but topics you use early are remembered. |
| **Due date** | Start date + the planned days for every level up to and including this one. |
| **Overdue / stuck** | The current level isn't done by its due date. A stuck alert is sent, then a reminder every `reminder_every_days`. |
| **Days behind** | How many days the current level is past its due date. The expected finish date moves by the same amount. |
| **Inactive** | No activity for `inactive_after_days` (set `0` to turn off). |
| **Streak** | Consecutive days with at least one counted run, up to today or yesterday. |

Changing `plan` or `start_date` for a language in `config.json` recalculates its due dates.

### Which results count

| Result | Counts toward topics, streak and daily target? |
|---|---|
| ✅ success (the program ran without an error) | Yes |
| ✅ compiled (Java compiled cleanly) | Yes |
| 💾 saved (browser JavaScript, see below) | Only if the syntax check passed |
| ❌ error or compile error | No |
| ⏹ stopped (you pressed Stop or Ctrl+C) | No |

Every result, counted or not, still counts as **activity**, so it prevents an inactivity nudge.

### Where activity counts

- 🐍 **Python and 🟨 JavaScript:** only code inside that language's `code_folder`.
- ☕ **Java:** anywhere on the PC. `javac` compiles and Java runs are seen from any folder, and Eclipse builds are scanned in your recent workspaces. These folders are **always ignored**: `Program Files`, `Program Files (x86)`, `Windows`, `AppData`, `.m2`, `.gradle`, `.p2`, `node_modules`, the tracker folder, and any folder in `languages.java.exclude_folders` (see [Configuration](#configuration-configjson)).
- 🟨 **Browser JavaScript:** a `.html` page (its inline `<script>` code) and the `.js` files it links with `<script src="...">` are counted as 💾 saved when you save them. A saved file is not run, so it only counts if it passes a syntax check: brackets balance and every string and comment is closed. If the Node hook can't be installed, every `.js` file in the folder is tracked this way too.

---

## Complexity score

Each file version that ran successfully gets a score:

```
score = lines ÷ 10  +  functions × 2  +  classes × 4  +  loops  +  conditions  +  try × 2  +  imports
```

| Score | Level |
|---|---|
| 0–10 | 🟢 Beginner |
| 11–30 | 🟡 Intermediate |
| 31+ | 🔴 Advanced |

"Lines" counts only lines that aren't blank or comments. The score and bands are the same for every language (for Java, the class holding `main` and `main` itself aren't counted). Try it on any `.py`, `.java`, `.js` or `.html` file:

```powershell
python tracker\analyzer.py some_script.py
```

---

## Dashboard

Open `file:///C:/Python/tracker/dashboard.html` in your browser. The title is "📚 *your name*'s Learning Tracker".

**Tabs:** **Overview**, then one tab per language you chose (🐍 / ☕ / 🟨). The browser remembers the last tab you used.

**Overview tab:**

- One card per language: current level, status (on track or days behind), streak and a levels progress bar. Click a card to open that language's tab.
- Your any-language streak and this week's activity
- A 14-day activity chart, stacked by language
- A small "add this language with `python tracker\setup.py`" card for languages you haven't chosen

**Each language tab:**

- **Banner:** stuck alert, "not started yet", or "all levels complete"
- **KPI cards:** current level, schedule (on track or days behind), streak, runs this week, average complexity
- **Roadmap:** all 9 levels with status (done / in progress / overdue / upcoming) and due dates
- **Current level:** topic chips (hover to see the file and date where each was first used), a "try next" tip, learning links, the practice project
- **Targets:** levels, topics, time used, today's runs, this week's lines, streak
- **Charts:** plan vs actual levels completed; daily successful vs failed runs (last 14 days)
- **Errors:** most common errors in the last 30 days
- **Recent runs:** the last 15 runs with result (✅ success or compiled, ❌ error, ⏹ stopped, 💾 saved), lines, score and level. For Java it shows the folder too.

The **☕ Java tab** also has a **"Java sources found in"** table (folder, number of files, last seen). If a work folder shows up that you don't want counted, add it to `exclude_folders`.

If one language can't be read, its tab says "Couldn't read *Language* data, see data\send_report.log" and the other tabs still work.

The dashboard is a static file. It's rebuilt by the daily task or when you run `python tracker\track.py`. Press **F5** in the browser to see the update.

`plan.html` shows the full roadmap with dates, with a tab for each of the three languages. Your languages are marked "✅ your plan"; the others are "👀 preview". You can preview the other plan or a different start date there (preview only; it doesn't change your settings).

Charts load Chart.js from the internet. Offline, everything except the charts still works.

---

## Emails

| Email | When | Contents |
|---|---|---|
| 📧 **Progress report** | Each of your `send_days` at `send_time` | One email: an overview tile per language, then a section per language with level and status, levels progress bar, streak, weekly runs, targets, files run since the last report, tips |
| ⚠️ **Stuck alert** | The day after a language's current level is due, then every `reminder_every_days` | Worked out per language. Languages due an alert the same day share **one email**, with a section each: days over, topics still to do with lesson links, things to try, impact on finish date |
| 👋 **Inactivity nudge** | After `inactive_after_days` with no activity in a language, repeated at the same interval | Per language, combined into one email when several are due: days inactive and the next topic to try |

The daily task runs `send_report.py` once a day at `send_time`. If the PC was off then, Windows runs it once soon after you switch on. Emails contain progress numbers, folder names and file names, never your code.

---

## Commands

Run from `C:\Python`:

| Command | What it does |
|---|---|
| `python tracker\setup.py` | First-time setup, or change settings or languages (Enter keeps each current value) |
| `python tracker\setup.py --uninstall` | Remove every hook, the daily task and the stored password (keeps your data). **Run it before deleting or moving the tracker folder.** |
| `python tracker\track.py` | Refresh the dashboard and open it |
| `python tracker\track.py --no-open` | Refresh the dashboard without opening it |
| `python tracker\send_report.py` | Run the daily check now (dashboard + any emails due today) |
| `python tracker\send_report.py --send-now` | Send the progress email right now |
| `python tracker\send_report.py --preview` | Save emails as HTML files and open them; **sends nothing** |
| `python tracker\analyzer.py file` | Show the topics and complexity score of one `.py`, `.java`, `.js` or `.html` file |

---

## Configuration (`config.json`)

Created by `setup.py`. You can also edit it by hand; changes apply on the next refresh.

```json
{
  "learner_name": "Soumya",
  "email": {
    "enabled": true,
    "to": ["you@gmail.com"],
    "sender": "you@gmail.com",
    "send_days": ["Monday", "Thursday"],
    "send_time": "08:00"
  },
  "alerts": {
    "stuck_enabled": true,
    "reminder_every_days": 3,
    "inactive_after_days": 5
  },
  "languages": {
    "python": {
      "enabled": true,
      "start_date": "2026-10-25",
      "plan": "aggressive",
      "code_folder": "C:\\Python"
    },
    "java": {
      "enabled": true,
      "start_date": "2026-11-01",
      "plan": "standard",
      "code_folder": "C:\\Users\\you\\eclipse-workspace",
      "extra_workspaces": [],
      "exclude_folders": []
    },
    "javascript": {
      "enabled": false,
      "start_date": "",
      "plan": "standard",
      "code_folder": "C:\\JavaScript"
    }
  }
}
```

| Setting | Meaning |
|---|---|
| `learner_name` | Shown on the dashboard and emails |
| `languages.<language>.enabled` | `true` to track that language. **Re-run setup after changing it** so its hook is installed or removed. |
| `languages.<language>.start_date` | Day 1 of that language's plan (`YYYY-MM-DD`). Activity before it is ignored. |
| `languages.<language>.plan` | `"standard"` or `"aggressive"` |
| `languages.<language>.code_folder` | 🐍 Python and 🟨 JavaScript: only code inside this folder is logged. ☕ Java: your default Eclipse workspace (Java activity counts anywhere). **Re-run setup after changing it** so the hook is updated. |
| `languages.java.extra_workspaces` | More Eclipse workspace folders to scan for builds, on top of your recent workspaces and `code_folder`. Example: `["D:\\work\\java"]` |
| `languages.java.exclude_folders` | Folders whose Java activity never counts. Adding one also removes that folder's **past** entries and snapshots on the next refresh. |
| `email.enabled` | `false` turns off all emails (the dashboard still updates) |
| `email.to` | List of recipients |
| `email.sender` | The Gmail account that sends (must match the App Password) |
| `email.send_days` | Full English day names |
| `email.send_time` | Time of the daily task. **Re-run setup after changing it** so the task is rescheduled. |
| `alerts.stuck_enabled` | Send stuck alerts and reminders |
| `alerts.reminder_every_days` | Days between stuck reminders |
| `alerts.inactive_after_days` | Days without activity before a nudge; `0` turns it off |

Plan targets, level lengths, topics and links live in `curriculum.json` inside each language's folder under `languages\`.

---

## Gmail App Password

- It's stored in your Windows user environment variable `PYTRACKER_GMAIL_APP_PASSWORD`, **never** in `config.json` or any project file.
- To change it, re-run `python tracker\setup.py`, press Enter through to the password prompt, and paste the new one.
- If a password leaks (e.g. pasted into a chat or document), delete it at <https://myaccount.google.com/apppasswords> and create a new one.
- "The setting you are looking for is not available for your account" on the App Passwords page usually means 2-Step Verification isn't on, you're signed into a different account, it's a work/school account, or Advanced Protection is on.

---

## Project files

```
C:\Python\tracker\
├── README.md          this file
├── setup.py           first-time wizard: config, hooks, daily task, test email
├── track.py           reads the run logs, analyses code, works out levels and stats
├── send_report.py     daily task: refresh dashboard, send emails and alerts
├── analyzer.py        command-line analyser: picks the language by file extension
├── dashboard.py       builds dashboard.html and plan.html
├── emailer.py         builds and sends the emails (smtplib)
├── settings.py        file paths, default config, JSON helpers
├── migrate.py         one-time upgrade from the Python-only layout
├── languages\         one folder per language
│   ├── base.py, clike.py, envvars.py   shared code
│   ├── python\        curriculum.json, analyzer.py, run_logger.py, pack.py
│   ├── java\          curriculum.json, analyzer.py, eclipse_scan.py, pack.py
│   │   └── agent\     TrackerAgent.java (built into tracker-agent.jar by setup)
│   └── javascript\    curriculum.json, analyzer.py, node_hook.js, saved_scan.py, pack.py
├── tests\             the automated tests
│
├── config.json        your settings                 (generated)
├── dashboard.html     your progress dashboard       (generated)
├── plan.html          your full plan                (generated)
└── data\                                            (generated)
    ├── python\         runs.jsonl, snapshots\
    ├── java\           runs.jsonl, snapshots\, eclipse_seen.json
    ├── javascript\     runs.jsonl, snapshots\, saved_seen.json
    ├── email_state.json    when each email/alert was last sent
    └── send_report.log     log of every daily check (check here if emails stop)
```

Where each hook lives:

- 🐍 `%APPDATA%\Python\Python3XX\site-packages\usercustomize.py`, which Python imports automatically at startup.
- 🟨 A `--require` entry in your user `NODE_OPTIONS` setting, pointing at `languages\javascript\node_hook.js`.
- ☕ A `-javaagent` entry in your user `JAVA_TOOL_OPTIONS` setting, pointing at `languages\java\agent\tracker-agent.jar`.

Every step of every hook is wrapped so it can never break your programs.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **A run doesn't appear on the dashboard** | Refresh with `python tracker\track.py`. Check the file is inside the language's `code_folder` (Python, JavaScript) and not in `tracker\`. Check the run is on or after that language's `start_date`. |
| **Nothing is logged at all (Python)** | Check the logger file exists (see above). If you use a **virtual environment** or a **new Python version**, user site-packages may be off or different; re-run setup with that Python. |
| **Java run not logged** | Restart Eclipse (it only reads the setting at startup). In a new terminal run `echo %JAVA_TOOL_OPTIONS%`; it should contain `tracker-agent.jar`. Check the folder isn't excluded (built-in exclusions or `exclude_folders`). Without a JDK only Eclipse builds are seen: install one and re-run setup. |
| **"Picked up JAVA_TOOL_OPTIONS: ..." appears in the console** | Expected. The Java runtime prints it once for every Java program when the tracker's agent is installed. It's harmless. |
| **Node run not logged** | Restart VS Code. In a new terminal run `echo %NODE_OPTIONS%`; it should contain `node_hook.js`. Check the script is inside the JavaScript `code_folder`. |
| **A work folder shows in "Java sources found in"** | Add that folder to `languages.java.exclude_folders` in `config.json`. On the next refresh it disappears and its past entries and snapshots are removed. |
| **Every `node` program fails with `Cannot find module ... node_hook.js`** | The tracker folder was moved or deleted while its hook was still installed. Remove the tracker part (`--require ...node_hook.js`) from `NODE_OPTIONS`: Windows **Settings → System → About → Advanced system settings → Environment Variables**, under *User variables*. Or put the tracker folder back where it was and run `python tracker\setup.py --uninstall`. (Re-running `setup.py` from the tracker's current folder also replaces an old tracker entry with the right one.) |
| **Every Java program fails with `Error occurred during initialization of VM` or `agent library failed to init`** | Same cause. Remove the tracker part (`-javaagent:...tracker-agent.jar`) from `JAVA_TOOL_OPTIONS` in the same Environment Variables window. Or put the tracker folder back where it was and run `python tracker\setup.py --uninstall`. (Re-running `setup.py` from the tracker's current folder also replaces an old tracker entry with the right one.) |
| **Topic not ticked** | It must be in code that **counted** (a run that succeeded or compiled). Try `python tracker\analyzer.py file` to see which topics are detected. |
| **Test email: "Connection unexpectedly closed"** | Usually a malformed password (e.g. pasted twice). Re-run setup and paste once; an App Password is 16 letters. |
| **"Username and Password not accepted"** | The App Password doesn't match `email.sender`, or it was deleted. Create a new one and re-run setup. |
| **No emails arrive** | Check `data\send_report.log`, check spam, check `email.enabled` and `send_days`. Test with `python tracker\send_report.py --send-now`. |
| **Daily task isn't running** | Open **Task Scheduler** and look for `LearningTracker`. Re-run setup to recreate it. |
| **A language's tab says "Couldn't read ... data"** | See the error in `data\send_report.log`. The other languages are not affected. |
| **Charts are empty** | Chart.js needs internet access the first time the page loads. |
| **Want to restart a language's plan** | Set a new `start_date` for it in `config.json` (earlier activity is then ignored) and refresh. |

---

## Known limits

- **Java:**
  - Stopping a run with Eclipse's **Stop button** isn't logged (the program ends abruptly).
  - `System.exit(n)` is logged as a success, whatever `n` is.
  - If your program sets its own default exception handler, the tracker can't see its exceptions, so the run is logged as a success.
  - Eclipse builds are found when the dashboard is refreshed, and only the **latest build of each file** between two refreshes is seen.
  - The `Picked up JAVA_TOOL_OPTIONS` line appears in every Java program's console.
  - IntelliJ and other IDEs: their runs and command-line `javac` are caught by the agent, but their own internal builds aren't.
- **JavaScript:** browser code counts as 💾 *saved* (a syntax check only, not a real run), and only the latest saved version of a file between refreshes is seen.
- **Topic detection for Java and JavaScript** uses patterns, not a full parser. It's accurate for learner-level code, but unusual formatting can be missed.
- After setup changes the Java or JavaScript hooks, restart Eclipse and VS Code once.
- Other languages, and Python or JavaScript activity outside the code folder, aren't tracked.

---

## Uninstalling

**Run the uninstall command BEFORE you delete or move the `tracker` folder.** The Java and JavaScript hooks live in your Windows settings and point at files in that folder; if the folder disappears first, every Java and Node program will fail to start (see [Troubleshooting](#troubleshooting)).

```powershell
python tracker\setup.py --uninstall
```

This removes the Python logger, the Node hook and Java agent entries (only the tracker's part of `NODE_OPTIONS` and `JAVA_TOOL_OPTIONS`; anything else you had there is kept), the scheduled task and the stored App Password. Your `config.json`, `data\` and HTML files stay. Restart Eclipse and VS Code afterwards. Then you can delete the `tracker` folder to remove everything. Also delete the App Password at <https://myaccount.google.com/apppasswords>.

---

## Privacy

- Everything stays on your PC: run logs, code snapshots, dashboard.
- The only data that leaves your PC is the emails, sent from your Gmail account to the addresses in `email.to`. They contain progress numbers, folder names and file names, not your code.
- Code snapshots in `data\<language>\snapshots\` are copies of your code. Don't put secrets (passwords, API keys) in practice code, or delete the snapshots if you did.
- **Java snapshots can come from any folder** on the PC, not just your workspace. If a folder holds work you don't want copied, add it to `languages.java.exclude_folders`; its past entries and snapshots are then deleted on the next refresh.
