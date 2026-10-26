"""Runs once a day from Windows Task Scheduler (set up by setup.py).

Each time it:
  1. refreshes dashboard.html
  2. sends the progress email if today is one of your send_days
  3. sends one stuck alert covering every language whose current level is past its due date
     (then a reminder every `reminder_every_days`, tracked per language)
  4. sends one nudge covering every language with no runs for `inactive_after_days`

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
from settings import DATA_DIR, EMAIL_STATE_PATH, load_config, load_json, log_line, save_json
from track import build_report

LOG_PATH = DATA_DIR / "send_report.log"


def log(message):
    log_line(message)


def days_since(iso_date, today):
    return (today - dt.date.fromisoformat(iso_date[:10])).days if iso_date else None


def language_state(state, key):
    entry = state.setdefault("languages", {}).setdefault(key, {})
    entry.setdefault("alerts", {})
    entry.setdefault("last_inactive_sent", None)
    return entry


def renders(build, arg, label):
    """True if this language's part of an alert email can be built; a broken one is logged and left out."""
    try:
        build([arg])
        return True
    except Exception as exc:
        log(f"Skipped {label} in an alert email: {exc!r}")
        return False


def main():
    preview = "--preview" in sys.argv
    send_now = "--send-now" in sys.argv

    config = load_config()
    report = build_report(config)
    write_plan(config)
    write_dashboard(report)

    today = dt.date.fromisoformat(report["today"])
    state = load_json(EMAIL_STATE_PATH, None)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("last_progress_sent", None)
    alerts = config["alerts"]
    emails = []  # (kind, subject, html, text)
    # Languages whose report could not be built are skipped for alerts.
    reports = [(k, report["languages"][k]) for k in report["enabled"]
               if k in report["languages"] and "error" not in report["languages"][k]]

    # 1. One progress report on the chosen days
    last = state.get("last_progress_sent")
    is_send_day = today.strftime("%A") in config["email"]["send_days"]
    if send_now or preview or (is_send_day and days_since(last, today) != 0):
        since = dt.datetime.fromisoformat(last) if last else None
        emails.append(("progress",) + progress_email(report, since))

    # 2. Stuck alerts, then reminders: each language has its own due dates and timing
    stuck = []
    if alerts["stuck_enabled"] or preview:
        for key, rep in reports:
            cur = rep["current_level"]
            if cur and cur["status"] == "overdue":
                last_alert = language_state(state, key)["alerts"].get(str(cur["id"]))
                gap = days_since(last_alert, today)
                if preview or gap is None or gap >= alerts["reminder_every_days"]:
                    stuck.append((key, rep, last_alert is not None))
    stuck = [x for x in stuck if renders(stuck_email, (x[1], x[2]), x[1]["label"])]
    if stuck:
        emails.append(("stuck",) + stuck_email([(rep, reminder) for _, rep, reminder in stuck]))

    # 3. Inactivity nudges, combined into one email
    limit = alerts["inactive_after_days"]
    inactive = []
    for key, rep in reports:
        if rep["day_number"] >= 1 and rep["current_level"] and limit and rep["stats"]["days_inactive"] >= limit:
            gap = days_since(language_state(state, key)["last_inactive_sent"], today)
            if preview or gap is None or gap >= limit:
                inactive.append((key, rep))
    inactive = [x for x in inactive if renders(inactive_email, x[1], x[1]["label"])]
    if inactive:
        emails.append(("inactive",) + inactive_email([rep for _, rep in inactive]))

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
            for key, rep, _ in stuck:
                language_state(state, key)["alerts"][str(rep["current_level"]["id"])] = today.isoformat()
        elif kind == "inactive":
            for key, _ in inactive:
                language_state(state, key)["last_inactive_sent"] = today.isoformat()
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
