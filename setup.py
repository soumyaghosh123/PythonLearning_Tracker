"""First-time setup for the Python Learning Tracker.

    python tracker\\setup.py              # set up, or change settings (re-run any time)
    python tracker\\setup.py --uninstall  # stop tracking (keeps your data)

It asks a few questions, then:
  1. saves config.json
  2. installs the run logger (so every script you run in VS Code is logged)
  3. schedules a daily Windows task that refreshes the dashboard and sends emails
  4. optionally sends a test email
  5. opens your full learning plan
"""

import datetime as dt
import getpass
import re
import site
import subprocess
import sys
import webbrowser
from pathlib import Path

from settings import (CONFIG_PATH, DATA_DIR, DEFAULT_CONFIG, PASSWORD_ENV_VAR, TASK_NAME, TRACKER_DIR,
                      load_config, load_curriculum, save_json)

LOGGER_MARKER = "Python Learning Tracker: run logger"
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------- asking questions ----------

def ask(question, default="", check=None):
    """Ask until `check(answer)` returns a value (or raises ValueError with a hint)."""
    suffix = f" [{default}]" if default else ""
    while True:
        answer = input(f"{question}{suffix}: ").strip() or default
        if check is None:
            return answer
        try:
            return check(answer)
        except ValueError as error:
            print(f"  ✗ {error}")


def check_name(text):
    if not text:
        raise ValueError("Please enter a name.")
    return text


def check_emails(text):
    emails = [e.strip() for e in text.split(",") if e.strip()]
    if not emails or not all(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e) for e in emails):
        raise ValueError("Enter one or more email addresses separated by commas.")
    return emails


def check_date(text):
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValueError("Use the format YYYY-MM-DD, e.g. 2026-11-01.") from None


def check_days(text):
    days = []
    for part in text.split(","):
        part = part.strip().lower()
        match = [d for d in WEEKDAYS if part and d.lower().startswith(part[:3])]
        if not match:
            raise ValueError("Use day names like Mon,Thu or Monday,Thursday.")
        days.append(match[0])
    return sorted(set(days), key=WEEKDAYS.index)


def check_time(text):
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", text):
        raise ValueError("Use 24-hour HH:MM, e.g. 08:00 or 19:30.")
    hours, minutes = text.split(":")
    return f"{int(hours):02d}:{minutes}"


def yes(question, default=True):
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not answer else answer.startswith("y")


# ---------- installing pieces ----------

def install_logger(config):
    target_dir = Path(site.getusersitepackages())
    target = target_dir / "usercustomize.py"
    if target.exists() and LOGGER_MARKER not in target.read_text(encoding="utf-8", errors="ignore"):
        print(f"  ✗ {target} already exists and isn't ours, so the run logger was NOT installed.")
        return False
    code = (TRACKER_DIR / "run_logger.py").read_text(encoding="utf-8")
    code = (code.replace("__DATA_DIR__", str(DATA_DIR))
                .replace("__CODE_FOLDER__", config["code_folder"])
                .replace("__TRACKER_DIR__", str(TRACKER_DIR)))
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(code, encoding="utf-8")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Run logger installed ({target})")
    return True


def powershell(script):
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True)


def schedule_task(send_time):
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    script = f"""
$action = New-ScheduledTaskAction -Execute '{exe}' -Argument '"{TRACKER_DIR / "send_report.py"}"' -WorkingDirectory '{TRACKER_DIR}'
$trigger = New-ScheduledTaskTrigger -Daily -At '{send_time}'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings -Description 'Python Learning Tracker: daily dashboard refresh and emails' -Force | Out-Null
"""
    result = powershell(script)
    if result.returncode == 0:
        print(f"  ✓ Daily task '{TASK_NAME}' scheduled at {send_time} (runs later if the PC was off)")
        return True
    print(f"  ✗ Could not schedule the daily task:\n{result.stderr.strip()}")
    return False


def store_password(password):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, PASSWORD_ENV_VAR, 0, winreg.REG_SZ, password)


def remove_password():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, PASSWORD_ENV_VAR)
    except OSError:
        pass


# ---------- main flows ----------

def setup():
    print("\n🐍 Python Learning Tracker: setup\n")
    try:
        config = load_config()
        print("Existing settings found. Press Enter to keep the value in [brackets].\n")
    except SystemExit:
        config = {**DEFAULT_CONFIG, "email": dict(DEFAULT_CONFIG["email"]), "alerts": dict(DEFAULT_CONFIG["alerts"])}
    curriculum = load_curriculum()
    email = config["email"]

    config["learner_name"] = ask("Your name", config["learner_name"], check_name)
    email["to"] = ask("Email(s) for reports (comma separated)", ", ".join(email["to"]), check_emails)
    config["start_date"] = ask("Start date (YYYY-MM-DD)", config["start_date"] or dt.date.today().isoformat(), check_date)

    print("\nChoose a plan:")
    keys = list(curriculum["plans"])
    for i, key in enumerate(keys, 1):
        plan = curriculum["plans"][key]
        total = sum(level["days"][key] for level in curriculum["levels"])
        print(f"  {i}) {plan['icon']} {plan['label']:<11} {total} days · {plan['daily_effort']}")
    default_plan = str(keys.index(config["plan"]) + 1) if config["plan"] in keys else "1"

    def check_plan(text):
        if text not in [str(i) for i in range(1, len(keys) + 1)]:
            raise ValueError(f"Enter a number from 1 to {len(keys)}.")
        return keys[int(text) - 1]
    config["plan"] = ask("Plan", default_plan, check_plan)

    def check_folder(text):
        if not Path(text).is_dir():
            raise ValueError("That folder doesn't exist.")
        return str(Path(text).resolve())
    config["code_folder"] = ask("\nFolder where you write your Python code", config["code_folder"], check_folder)

    email["send_days"] = ask("Progress email days", ",".join(d[:3] for d in email["send_days"]), check_days)
    email["send_time"] = ask("Time to check and send emails (24h)", email["send_time"], check_time)

    # Gmail sending
    password = None
    print("\nTo send emails, the tracker needs a Gmail account and a Gmail App Password")
    print("(a special 16-character password, not your normal one):")
    print("  1. Turn on 2-Step Verification: https://myaccount.google.com/security")
    print("  2. Create an app password:      https://myaccount.google.com/apppasswords")
    if yes("Set up email sending now?", default=True):
        email["sender"] = ask("Gmail address to send from", email.get("sender") or email["to"][0],
                              lambda t: check_emails(t)[0])
        password = getpass.getpass("Gmail App Password (typing is hidden; Enter = keep existing): ").strip()
        email["enabled"] = True
    else:
        email["enabled"] = False

    print()
    save_json(CONFIG_PATH, config)
    print(f"  ✓ Saved {CONFIG_PATH}")
    if password:
        store_password(password)
        print(f"  ✓ App Password stored in your Windows user environment ({PASSWORD_ENV_VAR})")
    install_logger(config)
    schedule_task(email["send_time"])

    from dashboard import write_dashboard, write_plan
    from track import build_report
    report = build_report(config, curriculum)
    plan_path = write_plan(config, curriculum)
    write_dashboard(report)

    if email["enabled"] and yes("Send a test email now?", default=True):
        from emailer import progress_email, send_email
        subject, html_body, text_body = progress_email(report)
        try:
            send_email(config, "[Test] " + subject, html_body, text_body, password or None)
            print(f"  ✓ Test email sent to {', '.join(email['to'])}")
        except Exception as error:
            print(f"  ✗ Test email failed: {error}")
            print("    Check the Gmail address and App Password, then re-run setup.py.")

    print(f"\n✅ All set! Your {curriculum['plans'][config['plan']]['label']} plan runs "
          f"{report['start_date']} → {report['planned_finish']}.")
    print("   Write and run code in your folder as usual; it's tracked automatically.")
    print("   Refresh the dashboard any time with:  python tracker\\track.py\n")
    webbrowser.open(plan_path.as_uri())


def uninstall():
    target = Path(site.getusersitepackages()) / "usercustomize.py"
    if target.exists() and LOGGER_MARKER in target.read_text(encoding="utf-8", errors="ignore"):
        target.unlink()
        print("  ✓ Run logger removed")
    result = powershell(f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false")
    print("  ✓ Daily task removed" if result.returncode == 0 else "  - No daily task found")
    remove_password()
    print("  ✓ App Password removed")
    print(f"Your data and config are still in {TRACKER_DIR}")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        setup()
