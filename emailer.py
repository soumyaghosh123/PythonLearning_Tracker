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

def progress_email(report, since=None):
    """Twice-weekly progress report. `since` = time of the last report (for 'files since last report')."""
    s, plan, cur = report["stats"], report["plan"], report["current_level"]
    rows = []

    if report["day_number"] < 1:
        status_line = f"Your plan starts on <b>{fmt(report['start_date'])}</b>."
    elif not cur:
        status_line = "🎉 <b>All 9 levels complete!</b>"
    else:
        state = (f'<span style="color:{RED};font-weight:600;">{cur["overdue_days"]} days overdue</span>'
                 if cur["status"] == "overdue" else f'<span style="color:{GREEN};font-weight:600;">on track</span>')
        status_line = (f'Current level: <b>{cur["id"]}. {esc(cur["name"])}</b> '
                       f'({TIER_ICON[cur["tier"]]} {cur["tier"]}) · {cur["topics_done"]}/{len(cur["topics"])} topics · {state}')
    rows.append(row(
        heading(f'🗺️ Learning path · {plan["icon"]} {plan["label"]} plan')
        + f'<div style="font-size:14px;margin-bottom:8px;">{status_line}</div>'
        + progress_bar("Levels completed", report["levels_done"], 9, GREEN)
        + f'<div style="font-size:12px;color:{MUTED};">Day {max(0, report["day_number"])} of {report["total_days"]} · '
          f'Planned finish {fmt(report["planned_finish"])} · Expected finish {fmt(report["expected_finish"])}</div>', top=20))

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
                    + progress_bar("Topics mastered", report["topics_done"], report["topics_total"])
                    + progress_bar("Streak (days)", s["streak"], plan["streak_target_days"])))

    # Files run successfully since the last report
    latest = {}
    for run in report["_runs"]:
        if run["status"] == "success" and run["analysis"] and (since is None or run["dt"] > since):
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
    if report["errors"]:
        e = report["errors"][0]
        tips.append(f"<b>🐞 Most common error:</b> {esc(e['error'])} ({e['count']}×). Read the last line of the traceback carefully when it appears.")
    if tips:
        rows.append(row(tip_box("<br>".join(t for t in tips if t))))

    subject_level = f'Level {cur["id"]} {cur["name"]}' if cur else "all levels done"
    subject = (f'🐍 Python progress: {subject_level} · {s["streak"]}-day streak · '
               f'{s["week_lines"]}/{plan["weekly_lines_target"]} lines this week')
    body = wrap(BLUE, "🐍 Python Progress Report",
                f'{esc(report["learner"] or "Your")} · {fmt(report["today"])}', rows)
    text = (f"Python progress report ({fmt(report['today'])})\n"
            f"Plan: {plan['label']} · Day {max(0, report['day_number'])} of {report['total_days']}\n"
            f"Levels: {report['levels_done']}/9 · {subject_level}\n"
            f"Streak: {s['streak']} days · Lines this week: {s['week_lines']}/{plan['weekly_lines_target']}\n")
    return subject, body, text


def stuck_email(report, reminder=False):
    cur = report["current_level"]
    used = (dt.date.fromisoformat(report["today"]) - dt.date.fromisoformat(cur["starts"])).days + 1
    missing = [t for t in cur["topics"] if not t["done"]]
    todo = "".join(
        f'<div style="font-size:14px;margin-bottom:4px;">⬜ {esc(t["name"])}: '
        f'<a href="{esc(t["link"])}" style="color:{BLUE};">read the lesson</a></div>' for t in missing)
    tries = "<br>".join(f"• {esc(t['try'])}" for t in missing[:3])

    rows = [
        row(f'Level <b>{cur["id"]}. {esc(cur["name"])}</b> was planned for <b>{cur["days"]} days</b> '
            f'(due <b>{fmt(cur["due"])}</b>). It has now taken <b>{used} days</b>, which is '
            f'<b style="color:{RED};">{cur["overdue_days"]} days over</b>.', top=20),
        row(progress_bar("Topics completed", cur["topics_done"], len(cur["topics"]), RED)
            + '<div style="font-size:14px;margin-bottom:6px;"><b>Still to do:</b></div>' + todo),
        row(tip_box(f"<b>💡 Try this:</b><br>{tries}<br>Run each file successfully to tick the topic off.")),
        row(f'<div style="font-size:14px;"><b>Impact on schedule:</b> the course finish date moves from '
            f'<b>{fmt(report["planned_finish"])}</b> to about <b>{fmt(report["expected_finish"])}</b>.</div>'),
    ]
    label = "Reminder: still stuck" if reminder else "Stuck"
    subject = f'⚠️ {label} on Level {cur["id"]} "{cur["name"]}": {cur["overdue_days"]} days over the planned time'
    body = wrap(RED, "⚠️ Level overdue",
                f'{report["plan"]["label"]} plan · Day {report["day_number"]} since {fmt(report["start_date"])}', rows)
    text = (f"Level {cur['id']} {cur['name']} is {cur['overdue_days']} days overdue (due {fmt(cur['due'])}).\n"
            f"Still to do: {', '.join(t['name'] for t in missing)}\n")
    return subject, body, text


def inactive_email(report):
    days = report["stats"]["days_inactive"]
    cur = report["current_level"]
    rows = [row(f'<div style="font-size:15px;">No Python runs for <b>{days} days</b>. '
                f'A short session today keeps your plan on track.</div>', top=20)]
    if cur:
        rows.append(row(tip_box(next_topic_tip(cur) or f"Keep going with Level {cur['id']}.")))
    subject = f"🐍 {days} days without Python, time for a quick session?"
    body = wrap(YELLOW, "👋 We miss your code", f'{report["plan"]["label"]} plan · Day {report["day_number"]}', rows)
    return subject, body, f"No Python runs for {days} days.\n"


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
    message["From"] = f"Python Learning Tracker <{sender}>"
    message["To"] = ", ".join(email["to"])
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as server:
        server.login(sender, password.replace(" ", ""))
        server.send_message(message)
