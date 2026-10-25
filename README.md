# 🐍 Python Learning Tracker

A personal tracker that follows your Python learning from **Beginner to Advanced**, automatically.

You write and run code in VS Code as usual. The tracker logs each run, reads your code to see which Python topics you've used, ticks off topics and levels, and shows your progress on a dashboard. It also emails you progress reports and alerts when you fall behind.

Standard Python only: no `pip install` needed.

---

## Contents

1. [How it works](#how-it-works)
2. [Quick start](#quick-start)
3. [Daily use](#daily-use)
4. [The learning plan](#the-learning-plan)
5. [Rules: topics, levels, due dates](#rules-topics-levels-due-dates)
6. [Complexity score](#complexity-score)
7. [Dashboard](#dashboard)
8. [Emails](#emails)
9. [Commands](#commands)
10. [Configuration (`config.json`)](#configuration-configjson)
11. [Gmail App Password](#gmail-app-password)
12. [Project files](#project-files)
13. [Troubleshooting](#troubleshooting)
14. [Uninstalling](#uninstalling)
15. [Privacy](#privacy)

---

## How it works

```
 ⚙️ Setup  →  ▶️ Code in VS Code  →  🔍 Analyse  →  🎓 Level check  →  📊📧 Report
 (once)       (press Run as usual)   (reads code     (all topics done   (dashboard +
                                      from runs)      = level done)      emails)
```

1. **Setup (once):** `setup.py` asks a few questions, saves your settings, installs the run logger and schedules a daily task.
2. **Run logger:** every time Python runs a script inside your code folder, a small hook records the time, file, result (success / error / stopped), the error type, and a snapshot of the code.
3. **Analyse:** the analyser reads each snapshot with Python's built-in `ast` module (without running it again) to find the topics used and a complexity score.
4. **Level check:** topics from **successful** runs are ticked off. When every topic in a level is done, the level is complete. If the current level isn't done by its due date, you're **stuck**.
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
| Start date | `YYYY-MM-DD`, or Enter for today |
| Plan | `1` Standard or `2` Aggressive |
| Folder where you write your Python code | Enter to keep `C:\Python` |
| Progress email days | e.g. `Mon,Thu` |
| Time to check and send emails | 24-hour, e.g. `08:00` |
| Set up email sending now? | `y` |
| Gmail address to send from | The account the App Password belongs to |
| Gmail App Password | Paste **once**, press Enter (nothing shows while you paste) |
| Send a test email now? | `y` |

When it finishes you should see:

```
✓ Saved C:\Python\tracker\config.json
✓ App Password stored in your Windows user environment (PYTRACKER_GMAIL_APP_PASSWORD)
✓ Run logger installed (...\site-packages\usercustomize.py)
✓ Daily task 'PythonLearningTracker' scheduled at 08:00
✓ Test email sent to you@gmail.com
```

Your learning plan (`plan.html`) then opens in the browser.

**Setup runs only once.** Nothing needs to be started after you switch on the PC.

---

## Daily use

| When | What you do |
|---|---|
| Every day | Study the current level's links, then write and run practice code in `C:\Python`. That's all. |
| Anytime | Open the dashboard: `file:///C:/Python/tracker/dashboard.html` (bookmark it) |
| Email days | 📧 A progress report arrives (default Monday and Thursday) |
| If stuck | ⚠️ An alert arrives the day after a level's due date, then a reminder every 3 days |
| If inactive | 👋 A nudge arrives after 5 days with no runs |

Tips:

- Only code that **runs successfully** counts. A file that's saved but never run, or that crashes, doesn't tick topics off.
- Files that are only **imported** by another script (e.g. `helpers.py` imported by `main.py`) aren't analysed. Run them directly too if you want their topics counted.
- Anything inside `C:\Python\tracker\` is ignored, so the tracker's own code never counts as practice.

---

## The learning plan

9 levels across 3 tiers. Both plans cover the same levels and topics; only the time per level changes.

| | 📘 Standard | 🚀 Aggressive |
|---|---|---|
| Total length | 132 days (~4.5 months) | 65 days (~2 months) |
| Daily effort | 30–45 min | 1.5–2 hours |
| Daily target | 2 successful runs | 5 successful runs |
| Weekly target | 150 lines | 400 lines |
| Streak target | 30 days | 30 days |

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

Each level also has learning links and a practice project. See `plan.html` or `curriculum.json`.

---

## Rules: topics, levels, due dates

| Rule | Meaning |
|---|---|
| **Topic done** | The topic appears in a file that **ran successfully** on or after your start date. |
| **Level done** | Every topic in the level is done **and** the previous level is done. Levels complete in order, but topics you use early are remembered. |
| **Due date** | Start date + the planned days for every level up to and including this one. |
| **Overdue / stuck** | The current level isn't done by its due date. A stuck alert is sent, then a reminder every `reminder_every_days`. |
| **Days behind** | How many days the current level is past its due date. The expected finish date moves by the same amount. |
| **Inactive** | No runs for `inactive_after_days` (set `0` to turn off). |
| **Streak** | Consecutive days with at least one successful run, counted up to today or yesterday. |

Changing `plan` or `start_date` in `config.json` recalculates every due date.

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

"Lines" counts only lines that aren't blank or comments. Try it on any file:

```powershell
python tracker\analyzer.py some_script.py
```

---

## Dashboard

Open `file:///C:/Python/tracker/dashboard.html` in your browser.

- **Header:** plan, start date, day number, target finish
- **Banner:** stuck alert, "not started yet", or "all levels complete"
- **KPI cards:** current level, schedule (on track or days behind), streak, runs this week, average complexity
- **Roadmap:** all 9 levels with status (done / in progress / overdue / upcoming) and due dates
- **Current level:** topic chips (hover to see the file and date where each was first used), a "try next" tip, learning links, the practice project
- **Targets:** levels, topics, time used, today's runs, this week's lines, streak
- **Charts:** plan vs actual levels completed; daily successful vs failed runs (last 14 days)
- **Errors:** most common errors in the last 30 days
- **Recent runs:** the last 15 runs with result, lines, score and level

The dashboard is a static file. It's rebuilt by the daily task or when you run `python tracker\track.py`. Press **F5** in the browser to see the update.

`plan.html` shows the full roadmap with dates. You can preview the other plan or a different start date there (preview only; it doesn't change your settings).

Charts load Chart.js from the internet. Offline, everything except the charts still works.

---

## Emails

| Email | When | Contents |
|---|---|---|
| 📧 **Progress report** | Each of your `send_days` at `send_time` | Level and status, levels progress bar, streak, weekly runs, targets, files run since the last report, tips |
| ⚠️ **Stuck alert** | The day after the current level's due date, then every `reminder_every_days` | How many days over, topics still to do with lesson links, things to try, impact on finish date |
| 👋 **Inactivity nudge** | After `inactive_after_days` with no runs, repeated at the same interval | Days inactive and the next topic to try |

The daily task runs `send_report.py` once a day at `send_time`. If the PC was off then, Windows runs it once soon after you switch on.

---

## Commands

Run from `C:\Python`:

| Command | What it does |
|---|---|
| `python tracker\setup.py` | First-time setup, or change settings (Enter keeps each current value) |
| `python tracker\setup.py --uninstall` | Remove the logger, daily task and stored password (keeps your data) |
| `python tracker\track.py` | Refresh the dashboard and open it |
| `python tracker\track.py --no-open` | Refresh the dashboard without opening it |
| `python tracker\send_report.py` | Run the daily check now (dashboard + any emails due today) |
| `python tracker\send_report.py --send-now` | Send the progress email right now |
| `python tracker\send_report.py --preview` | Save emails as HTML files and open them; **sends nothing** |
| `python tracker\analyzer.py file.py` | Show the topics and complexity score of one file |

---

## Configuration (`config.json`)

Created by `setup.py`. You can also edit it by hand; changes apply on the next refresh.

```json
{
  "learner_name": "Soumya",
  "start_date": "2026-10-25",
  "plan": "aggressive",
  "code_folder": "C:\\Python",
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
  }
}
```

| Setting | Meaning |
|---|---|
| `learner_name` | Shown on the dashboard and emails |
| `start_date` | Day 1 of the plan (`YYYY-MM-DD`). Runs before it are ignored. |
| `plan` | `"standard"` or `"aggressive"` |
| `code_folder` | Only scripts inside this folder are logged. **Re-run setup after changing it** so the logger is updated. |
| `email.enabled` | `false` turns off all emails (the dashboard still updates) |
| `email.to` | List of recipients |
| `email.sender` | The Gmail account that sends (must match the App Password) |
| `email.send_days` | Full English day names |
| `email.send_time` | Time of the daily task. **Re-run setup after changing it** so the task is rescheduled. |
| `alerts.stuck_enabled` | Send stuck alerts and reminders |
| `alerts.reminder_every_days` | Days between stuck reminders |
| `alerts.inactive_after_days` | Days without runs before a nudge; `0` turns it off |

Plan targets, level lengths, topics and links live in `curriculum.json`.

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
├── setup.py           first-time wizard: config, logger, daily task, test email
├── track.py           reads the run log, analyses code, works out levels and stats
├── send_report.py     daily task: refresh dashboard, send emails and alerts
├── analyzer.py        complexity score and topic detection (ast)
├── dashboard.py       builds dashboard.html and plan.html
├── emailer.py         builds and sends the emails (smtplib)
├── run_logger.py      template for the run logger hook
├── settings.py        file paths, default config, JSON helpers
├── curriculum.json    the 9 levels: topics, links, projects, days per plan
│
├── config.json        your settings                 (generated)
├── dashboard.html     your progress dashboard       (generated)
├── plan.html          your full plan                (generated)
└── data\                                            (generated)
    ├── runs.jsonl          one line per script run
    ├── snapshots\          a copy of each code version that was run
    ├── email_state.json    when each email/alert was last sent
    └── send_report.log     log of every daily check (check here if emails stop)
```

The installed run logger lives at
`%APPDATA%\Python\Python3XX\site-packages\usercustomize.py`.
Python imports it automatically at startup; every step is wrapped in `try/except` so it can never break your scripts.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **A run doesn't appear on the dashboard** | Refresh with `python tracker\track.py`. Check the file is inside `code_folder` and not in `tracker\`. Check the run is on or after `start_date`. |
| **Nothing is logged at all** | Check the logger file exists (see above). If you use a **virtual environment** or a **new Python version**, user site-packages may be off or different; re-run setup with that Python. |
| **Topic not ticked** | It must be in a file that ran **successfully**. Try `python tracker\analyzer.py file.py` to see which topics are detected. |
| **Test email: "Connection unexpectedly closed"** | Usually a malformed password (e.g. pasted twice). Re-run setup and paste once; an App Password is 16 letters. |
| **"Username and Password not accepted"** | The App Password doesn't match `email.sender`, or it was deleted. Create a new one and re-run setup. |
| **No emails arrive** | Check `data\send_report.log`, check spam, check `email.enabled` and `send_days`. Test with `python tracker\send_report.py --send-now`. |
| **Daily task isn't running** | Open **Task Scheduler** and look for `PythonLearningTracker`. Re-run setup to recreate it. |
| **Charts are empty** | Chart.js needs internet access the first time the page loads. |
| **Want to restart the plan** | Set a new `start_date` in `config.json` (earlier runs are then ignored) and refresh. |

---

## Uninstalling

```powershell
python tracker\setup.py --uninstall
```

This removes the run logger, the scheduled task and the stored App Password. Your `config.json`, `data\` and HTML files stay. Delete the `tracker` folder to remove everything. Also delete the App Password at <https://myaccount.google.com/apppasswords>.

---

## Privacy

- Everything stays on your PC: run log, code snapshots, dashboard.
- The only data that leaves your PC is the emails, sent from your Gmail account to the addresses in `email.to`. They contain progress numbers and file names, not your code.
- Code snapshots in `data\snapshots\` are copies of your scripts. Don't put secrets (passwords, API keys) in practice scripts, or delete the snapshots if you did.
