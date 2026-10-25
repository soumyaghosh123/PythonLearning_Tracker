"""Runs once a day from Windows Task Scheduler (set up by setup.py).

Each time it:
  1. refreshes dashboard.html
  2. sends the progress email if today is one of your send_days
  3. sends a stuck alert if the current level is past its due date
     (then a reminder every `reminder_every_days`)
  4. sends a nudge if you haven't run any Python for `inactive_after_days`

Manual options:
  python tracker\\send_report.py              # do the daily check now
  python tracker\\send_report.py --send-now   # send the progress email right away
  python tracker\\send_report.py --preview    # save the emails as HTML files and open them (sends nothing)
"""

import datetime as dt
import html
import sys
import traceback
import webbrowser

from dashboard import write_dashboard, write_plan
from emailer import inactive_email, progress_email, send_email, stuck_email
from settings import DATA_DIR, EMAIL_STATE_PATH, load_config, load_curriculum, load_json, save_json
from track import build_report

LOG_PATH = DATA_DIR / "send_report.log"


def log(message):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    print(line)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def days_since(iso_date, today):
    return (today - dt.date.fromisoformat(iso_date[:10])).days if iso_date else None


def main():
    preview = "--preview" in sys.argv
    send_now = "--send-now" in sys.argv

    config = load_config()
    curriculum = load_curriculum()
    report = build_report(config, curriculum)
    write_plan(config, curriculum)
    write_dashboard(report)

    today = dt.date.fromisoformat(report["today"])
    state = load_json(EMAIL_STATE_PATH, {"last_progress_sent": None, "alerts": {}, "last_inactive_sent": None})
    alerts = config["alerts"]
    started = report["day_number"] >= 1
    cur = report["current_level"]
    emails = []  # (kind, subject, html, text)

    # 1. Progress report on the chosen days
    last = state.get("last_progress_sent")
    is_send_day = today.strftime("%A") in config["email"]["send_days"]
    if send_now or preview or (is_send_day and days_since(last, today) != 0):
        since = dt.datetime.fromisoformat(last) if last else None
        emails.append(("progress",) + progress_email(report, since))

    # 2. Stuck alert, then reminders
    if cur and cur["status"] == "overdue" and (alerts["stuck_enabled"] or preview):
        last_alert = state["alerts"].get(str(cur["id"]))
        gap = days_since(last_alert, today)
        if preview or gap is None or gap >= alerts["reminder_every_days"]:
            emails.append(("stuck",) + stuck_email(report, reminder=last_alert is not None))

    # 3. Inactivity nudge
    limit = alerts["inactive_after_days"]
    if started and cur and limit and report["stats"]["days_inactive"] >= limit:
        gap = days_since(state.get("last_inactive_sent"), today)
        if preview or gap is None or gap >= limit:
            emails.append(("inactive",) + inactive_email(report))

    if preview:
        for kind, subject, html_body, _ in emails:
            path = DATA_DIR / f"preview_{kind}.html"
            title = f"<title>{html.escape(subject)}</title>"
            path.write_text(html_body.replace("<html>", "<html><head><meta charset=\"utf-8\">" + title + "</head>", 1),
                            encoding="utf-8")
            print(f"{kind:>9}: {subject}\n           {path}")
            webbrowser.open(path.as_uri())
        if not emails:
            print("Nothing to preview.")
        return

    if not config["email"]["enabled"]:
        log(f"Dashboard updated. Email is turned off in config.json ({len(emails)} email(s) skipped).")
        return

    for kind, subject, html_body, text_body in emails:
        try:
            send_email(config, subject, html_body, text_body)
        except Exception as error:
            log(f"FAILED to send {kind} email: {error}")
            continue
        log(f"Sent {kind} email: {subject}")
        if kind == "progress":
            state["last_progress_sent"] = dt.datetime.now().isoformat(timespec="seconds")
        elif kind == "stuck":
            state["alerts"][str(cur["id"])] = today.isoformat()
        elif kind == "inactive":
            state["last_inactive_sent"] = today.isoformat()
    save_json(EMAIL_STATE_PATH, state)
    if not emails:
        log("Dashboard updated. No emails due today.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        log("ERROR\n" + traceback.format_exc())
        raise
