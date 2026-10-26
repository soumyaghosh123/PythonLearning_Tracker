"""Builds the progress, stuck-alert and inactivity emails, and sends them through Gmail.

Emails use inline styles (style="...") because Gmail ignores <style> blocks.
"""

import datetime as dt
import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from settings import DASHBOARD_PATH, PASSWORD_ENV_VAR

BLUE, GREEN, RED, YELLOW, MUTED = "#3572a5", "#2e9e5b", "#d64545", "#f2c94c", "#6b7385"
TIER_ICON = {"Beginner": "🟢", "Intermediate": "🟡", "Advanced": "🔴"}


def fmt(iso, year=True):
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.day} {d.strftime('%b')}" + (f" {d.year}" if year else "")


def esc(text):
    return html.escape(str(text))


# ---------- building blocks ----------

def wrap(header_color, title, subtitle, body_rows):
    rows = "".join(body_rows)
    return f"""<!doctype html><html><body style="margin:0;background:#eef1f6;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f6;padding:16px;font-family:'Segoe UI',Arial,sans-serif;color:#1d2433;">
<tr><td align="center">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #dde2ea;">
  <tr><td style="background:{header_color};padding:24px;color:#ffffff;">
    <div style="font-size:22px;font-weight:700;">{title}</div>
    <div style="font-size:13px;opacity:.9;">{subtitle}</div>
  </td></tr>
  {rows}
  <tr><td style="padding:20px 24px 24px;font-size:12px;color:{MUTED};">
    Full dashboard: {esc(DASHBOARD_PATH)} · Change targets, plan or email settings in config.json
  </td></tr>
</table></td></tr></table></body></html>"""


def row(content, top=16):
    return f'<tr><td style="padding:{top}px 24px 0;">{content}</td></tr>'


def heading(text):
    return f'<div style="font-size:16px;font-weight:700;margin-bottom:8px;">{text}</div>'


def progress_bar(label, value, goal, color=BLUE):
    pct = min(100, round(value / goal * 100)) if goal else 0
    if value >= goal:
        color = GREEN
    return (f'<div style="font-size:14px;">{label} <span style="float:right;">{value} / {goal}</span></div>'
            f'<div style="background:#e9edf4;border-radius:6px;height:10px;margin:4px 0 12px;">'
            f'<div style="width:{pct}%;background:{color};height:10px;border-radius:6px;"></div></div>')


def tip_box(content):
    return (f'<div style="background:#fff8e1;border-left:4px solid {YELLOW};padding:12px 14px;'
            f'border-radius:6px;font-size:14px;">{content}</div>')


def next_topic_tip(level):
    topic = next((t for t in level["topics"] if not t["done"]), None)
    if not topic:
        return ""
    return (f'<b>💡 Next step:</b> {esc(topic["try"])} '
            f'<a href="{esc(topic["link"])}" style="color:{BLUE};">Read the lesson</a>')


# ---------- the three emails ----------

def is_done(rep):
    """Started, no current level left: every level of the course is complete."""
    return rep["day_number"] >= 1 and not rep["current_level"]


def status_text(rep):
    """Short plain status used in tiles and the text part."""
    cur = rep["current_level"]
    if rep["day_number"] < 1:
        return f"starts {fmt(rep['start_date'])}"
    if not cur:
        return "all done"
    return "overdue" if cur["status"] == "overdue" else "on track"


def subject_part(rep):
    cur = rep["current_level"]
    if rep["day_number"] < 1:
        return f'{rep["icon"]} starts {fmt(rep["start_date"], year=False)}'
    if not cur:
        return f'{rep["icon"]} all done'
    behind = rep["days_behind"]
    return f'{rep["icon"]} L{cur["id"]} {cur["name"]}' + (f" ({behind} days behind)" if behind else "")


def language_section(rep, since=None):
    """Rows for one language: level status, tiles, targets, files since the last report, tips."""
    s, plan, cur = rep["stats"], rep["plan"], rep["current_level"]
    rows = []

    if rep["day_number"] < 1:
        status_line = f"Your plan starts on <b>{fmt(rep['start_date'])}</b>."
    elif not cur:
        status_line = f"🎉 <b>All {len(rep['levels'])} levels complete!</b>"
    else:
        state = (f'<span style="color:{RED};font-weight:600;">{cur["overdue_days"]} days overdue</span>'
                 if cur["status"] == "overdue" else f'<span style="color:{GREEN};font-weight:600;">on track</span>')
        status_line = (f'Current level: <b>{cur["id"]}. {esc(cur["name"])}</b> '
                       f'({TIER_ICON[cur["tier"]]} {cur["tier"]}) · {cur["topics_done"]}/{len(cur["topics"])} topics · {state}')
    rows.append(row(
        heading(f'{rep["icon"]} {esc(rep["label"])} · {esc(plan["icon"])} {esc(plan["label"])} plan')
        + f'<div style="font-size:14px;margin-bottom:8px;">{status_line}</div>'
        + progress_bar("Levels completed", rep["levels_done"], len(rep["levels"]), GREEN)
        + f'<div style="font-size:12px;color:{MUTED};">Day {max(0, rep["day_number"])} of {rep["total_days"]} · '
          f'Planned finish {fmt(rep["planned_finish"])} · Expected finish {fmt(rep["expected_finish"])}</div>', top=20))

    def tile(label, value):
        return (f'<td align="center" style="padding:10px;background:#f5f7fb;border-radius:8px;">'
                f'<div style="font-size:12px;color:{MUTED};">{label}</div>'
                f'<div style="font-size:22px;font-weight:700;">{value}</div></td>')
    rows.append(row('<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                    + tile("🔥 Streak", f'{s["streak"]} days') + '<td width="8"></td>'
                    + tile("▶️ Runs this week", f'{s["success_week"]}/{s["runs_week"]} ✓') + '<td width="8"></td>'
                    + tile("⭐ Avg score", s["avg_score"]) + '</tr></table>'))

    rows.append(row(heading("🎯 Targets")
                    + progress_bar("This week's lines of code", s["week_lines"], plan["weekly_lines_target"])
                    + progress_bar("Topics mastered", rep["topics_done"], rep["topics_total"])
                    + progress_bar("Streak (days)", s["streak"], plan["streak_target_days"])))

    # Files that counted since the last report (file names only, never code)
    latest = {}
    for run in rep["_runs"]:
        if run["status"] in ("success", "compiled") and run["analysis"] and (since is None or run["dt"] > since):
            latest[run["file"]] = run
    if latest:
        lines = "".join(
            f'<tr style="border-top:1px solid #e3e7ef;"><td>{esc(Path(f).name)}</td><td>{r["analysis"]["lines"]}</td>'
            f'<td>{r["analysis"]["score"]}</td><td>{TIER_ICON[r["analysis"]["level"]]} {r["analysis"]["level"]}</td></tr>'
            for f, r in list(latest.items())[-10:])
        table = (f'<table width="100%" cellpadding="6" cellspacing="0" style="font-size:13px;border-collapse:collapse;">'
                 f'<tr style="color:{MUTED};"><th align="left">File</th><th align="left">Lines</th>'
                 f'<th align="left">Score</th><th align="left">Level</th></tr>{lines}</table>')
    else:
        table = f'<div style="font-size:14px;color:{MUTED};">No successful runs since the last report.</div>'
    rows.append(row(heading("📂 Files since last report") + table))

    tips = []
    if cur:
        tips.append(next_topic_tip(cur))
    remaining = plan["weekly_lines_target"] - s["week_lines"]
    if remaining > 0:
        tips.append(f"<b>📌 Weekly target:</b> write {remaining} more lines by Sunday.")
    if rep["errors"]:
        e = rep["errors"][0]
        tips.append(f"<b>🐞 Most common error:</b> {esc(e['error'])} ({e['count']}×). Read the error message carefully when it appears.")
    if tips:
        rows.append(row(tip_box("<br>".join(t for t in tips if t))))
    return rows


def overview_row(reports):
    """One tile per language: icon, label, current level (or all done), status."""
    cells = []
    for rep in reports:
        if "error" in rep:
            level, status = "couldn't read", ""
        else:
            cur = rep["current_level"]
            level = "all done" if is_done(rep) else (f'L{cur["id"]} {cur["name"]}' if cur else "not started")
            status = status_text(rep)
        cells.append(f'<td align="center" style="padding:10px;background:#f5f7fb;border-radius:8px;">'
                     f'<div style="font-size:12px;color:{MUTED};">{rep["icon"]} {esc(rep["label"])}</div>'
                     f'<div style="font-size:15px;font-weight:700;">{esc(level)}</div>'
                     f'<div style="font-size:12px;color:{MUTED};">{esc(status)}</div></td>')
    return row('<table width="100%" cellpadding="0" cellspacing="0"><tr>'
               + '<td width="8"></td>'.join(cells) + '</tr></table>', top=20)


def error_row(rep):
    return row(f'<div style="font-size:14px;color:{MUTED};">{rep["icon"]} {esc(rep["label"])}: '
               f"couldn't read this language's data today (see send_report.log).</div>")


def progress_email(report, since=None):
    """Twice-weekly progress report. `since` = time of the last report (for 'files since last report')."""
    reps = [report["languages"][k] for k in report["enabled"] if k in report["languages"]]
    rows = [overview_row(reps)] if reps else []
    parts, text_lines = [], []
    for rep in reps:
        if "error" in rep:
            rows.append(error_row(rep))
            text_lines.append(f"{rep['label']}: couldn't read this language's data today.")
            continue
        rows.extend(language_section(rep, since))
        parts.append(subject_part(rep))
        s = rep["stats"]
        text_lines.append(f"{rep['label']}: {status_text(rep)} · Day {max(0, rep['day_number'])} of {rep['total_days']} · "
                          f"Levels {rep['levels_done']}/{len(rep['levels'])} · Streak {s['streak']} days · "
                          f"Lines this week {s['week_lines']}/{rep['plan']['weekly_lines_target']}")
    streak = report["overall"]["any_streak"]
    subject = "📚 Progress: " + " · ".join(parts + [f"🔥 {streak}-day streak"])
    body = wrap(BLUE, "📚 Learning Progress Report",
                f'{esc(report["learner"] or "Your")} · {fmt(report["today"])}', rows)
    text = f"Learning progress report ({fmt(report['today'])})\n" + "\n".join(text_lines) + f"\nStreak: {streak} days\n"
    return subject, body, text


def stuck_section(rep):
    cur = rep["current_level"]
    used = (dt.date.fromisoformat(rep["today"]) - dt.date.fromisoformat(cur["starts"])).days + 1
    missing = [t for t in cur["topics"] if not t["done"]]
    todo = "".join(
        f'<div style="font-size:14px;margin-bottom:4px;">⬜ {esc(t["name"])}: '
        f'<a href="{esc(t["link"])}" style="color:{BLUE};">read the lesson</a></div>' for t in missing)
    tries = "<br>".join(f"• {esc(t['try'])}" for t in missing[:3])
    return [
        row(heading(f'{rep["icon"]} {esc(rep["label"])}')
            + f'Level <b>{cur["id"]}. {esc(cur["name"])}</b> was planned for <b>{cur["days"]} days</b> '
              f'(due <b>{fmt(cur["due"])}</b>). It has now taken <b>{used} days</b>, which is '
              f'<b style="color:{RED};">{cur["overdue_days"]} days over</b>.', top=20),
        row(progress_bar("Topics completed", cur["topics_done"], len(cur["topics"]), RED)
            + '<div style="font-size:14px;margin-bottom:6px;"><b>Still to do:</b></div>' + todo),
        row(tip_box(f"<b>💡 Try this:</b><br>{tries}<br>Run each file successfully to tick the topic off.")),
        row(f'<div style="font-size:14px;"><b>Impact on schedule:</b> the course finish date moves from '
            f'<b>{fmt(rep["planned_finish"])}</b> to about <b>{fmt(rep["expected_finish"])}</b>.</div>'),
    ]


def stuck_email(items):
    """items: [(language report, is_reminder), ...] for every language due an alert today."""
    rows, text_lines = [], []
    for rep, _ in items:
        rows.extend(stuck_section(rep))
        cur = rep["current_level"]
        missing = [t["name"] for t in cur["topics"] if not t["done"]]
        text_lines.append(f"{rep['label']}: Level {cur['id']} {cur['name']} is {cur['overdue_days']} days overdue "
                          f"(due {fmt(cur['due'])}). Still to do: {', '.join(missing)}")
    if len(items) == 1:
        rep, reminder = items[0]
        cur = rep["current_level"]
        label = "Reminder: still stuck" if reminder else "Stuck"
        subject = (f'{rep["icon"]} ⚠️ {label} on Level {cur["id"]} "{cur["name"]}": '
                   f'{cur["overdue_days"]} days over the planned time')
        subtitle = f'{rep["label"]} · {rep["plan"]["label"]} plan · Day {rep["day_number"]} since {fmt(rep["start_date"])}'
    else:
        names = " · ".join(f'{r["icon"]} L{r["current_level"]["id"]} {r["current_level"]["name"]}' for r, _ in items)
        subject = f"⚠️ Stuck in {len(items)} languages: {names}"
        subtitle = f"{len(items)} languages are past their planned time"
    body = wrap(RED, "⚠️ Level overdue", esc(subtitle), rows)
    return subject, body, "\n".join(text_lines) + "\n"


def inactive_email(items):
    """items: [language report, ...] for every language due a nudge today."""
    rows, text_lines = [], []
    for rep in items:
        days, cur = rep["stats"]["days_inactive"], rep["current_level"]
        content = (f'<div style="font-size:15px;">{rep["icon"]} <b>{esc(rep["label"])}</b>: no runs for '
                   f'<b>{days} days</b>. A short session today keeps your plan on track.</div>')
        if cur:
            content += '<div style="height:8px"></div>' + tip_box(next_topic_tip(cur) or f"Keep going with Level {cur['id']}.")
        rows.append(row(content, top=20))
        text_lines.append(f"{rep['label']}: no runs for {days} days."
                          + (f" Next: Level {cur['id']} {cur['name']}." if cur else ""))
    if len(items) == 1:
        rep = items[0]
        subject = f'{rep["icon"]} {rep["stats"]["days_inactive"]} days without {rep["label"]}, time for a quick session?'
    else:
        subject = f"👋 {len(items)} languages need a quick session"
    body = wrap(YELLOW, "👋 We miss your code", f"{len(items)} language(s) waiting", rows)
    return subject, body, "\n".join(text_lines) + "\n"


# ---------- sending ----------

def get_password():
    """The Gmail App Password from the environment, or from the Windows user registry
    (setup.py stores it there; newly started programs may not see it in os.environ yet)."""
    password = os.environ.get(PASSWORD_ENV_VAR)
    if password:
        return password
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, PASSWORD_ENV_VAR)[0]
    except (ImportError, OSError):
        return None


def send_email(config, subject, html_body, text_body, password=None):
    email = config["email"]
    password = password or get_password()
    if not password:
        raise RuntimeError(f"No Gmail App Password found. Re-run setup.py (it is stored in {PASSWORD_ENV_VAR}).")
    sender = email.get("sender") or email["to"][0]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Learning Tracker <{sender}>"
    message["To"] = ", ".join(email["to"])
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as server:
        server.login(sender, password.replace(" ", ""))
        server.send_message(message)
