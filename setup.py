"""First-time setup for the Learning Tracker (Python, Java, JavaScript).

    python tracker\\setup.py              # set up, or change settings (re-run any time)
    python tracker\\setup.py --uninstall  # stop tracking (keeps your data)

It asks a few questions, then:
  1. saves config.json
  2. installs each chosen language's hook (and removes the hooks of languages you dropped)
  3. schedules a daily Windows task that refreshes the dashboard and sends emails
  4. optionally sends a test email
  5. opens your full learning plan
"""

import datetime as dt
import getpass
import json
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

from languages import all_packs, get_pack
from settings import (CONFIG_PATH, DATA_DIR, DEFAULT_CONFIG, OLD_TASK_NAME, PASSWORD_ENV_VAR, TASK_NAME,
                      TRACKER_DIR, enabled_languages, load_config, load_json, save_json)

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


def parse_language_choice(text, current):
    """'1,3' -> ['python', 'javascript'] in registry order; '' keeps `current`."""
    if not text.strip():
        return list(current)
    packs = all_packs()
    try:
        numbers = {int(part) for part in text.split(",")}
    except ValueError:
        numbers = set()
    if not numbers or not all(1 <= n <= len(packs) for n in numbers):
        raise ValueError(f"Enter numbers 1-{len(packs)}, comma-separated")
    return [p.key for i, p in enumerate(packs, 1) if i in numbers]


def yes(question, default=True):
    answer = input(f"{question} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    return default if not answer else answer.startswith("y")


# ---------- installing pieces ----------

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
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings -Description 'Learning Tracker: daily dashboard refresh and emails' -Force | Out-Null
"""
    result = powershell(script)
    if result.returncode == 0:
        print(f"  ✓ Daily task '{TASK_NAME}' scheduled at {send_time} (runs later if the PC was off)")
        return True
    print(f"  ✗ Could not schedule the daily task:\n{result.stderr.strip()}")
    return False


def store_password(password):
    from languages.envvars import set_user_env
    set_user_env(PASSWORD_ENV_VAR, password)


def remove_password():
    from languages.envvars import set_user_env
    set_user_env(PASSWORD_ENV_VAR, "")




# ---------- main flows ----------

HOOK_ENV_PACKS = ("javascript", "java")      # the packs whose hook lives in a user environment variable


def old_layout_on_disk():
    """True when config.json still has the single-language layout (load_config will migrate it)."""
    raw = load_json(CONFIG_PATH)
    return isinstance(raw, dict) and ("languages" not in raw or any(k in raw for k in ("start_date", "plan", "code_folder")))


def short_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {d:%b}"


def ask_language(pack, block):
    """Ask the per-language questions and store the answers in `block`."""
    print(f"\n── {pack.icon} {pack.label} ──")
    block["start_date"] = ask("Start date (YYYY-MM-DD)", block.get("start_date") or dt.date.today().isoformat(),
                              check_date)
    curriculum = pack.curriculum()
    keys = list(curriculum["plans"])
    print("Choose a plan:")
    for i, key in enumerate(keys, 1):
        plan = curriculum["plans"][key]
        total = sum(level["days"][key] for level in curriculum["levels"])
        print(f"  {i}) {plan['icon']} {plan['label']:<11} {total} days · {plan['daily_effort']}")
    default_plan = str(keys.index(block["plan"]) + 1) if block.get("plan") in keys else "1"

    def check_plan(text):
        if text not in [str(i) for i in range(1, len(keys) + 1)]:
            raise ValueError(f"Enter a number from 1 to {len(keys)}.")
        return keys[int(text) - 1]
    block["plan"] = ask("Plan", default_plan, check_plan)

    java = pack.key == "java"      # Java is tracked anywhere, so a missing workspace is not an error

    def check_folder(text):
        if not java and not Path(text).is_dir():
            raise ValueError("That folder doesn't exist.")
        return str(Path(text).resolve())
    prompt = "Code folder (your Eclipse workspace)" if java else "Code folder"
    block["code_folder"] = ask(prompt, block["code_folder"], check_folder)
    folder = Path(block["code_folder"])
    if java and not folder.is_dir() and yes("That folder doesn't exist yet. Create it now?", default=True):
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            print(f"  ✗ Could not create it: {error}")


def setup():
    print("\n📚 Learning Tracker: setup\n")
    # A migrated config loads as python-enabled, so the Python logger is reinstalled below
    # and starts writing to data/python/.
    migrated = old_layout_on_disk()
    try:
        config = load_config()
        print("Existing settings found. Press Enter to keep the value in [brackets].\n")
        if migrated:
            print("Your settings were upgraded to the multi-language layout.\n")
    except SystemExit:
        config = json.loads(json.dumps(DEFAULT_CONFIG))
    email = config["email"]

    config["learner_name"] = ask("Your name", config["learner_name"], check_name)
    email["to"] = ask("Email(s) for reports (comma separated)", ", ".join(email["to"]), check_emails)

    packs = all_packs()
    current = enabled_languages(config) or ["python"]
    print("\nWhich languages are you learning?")
    for i, pack in enumerate(packs, 1):
        print(f"  {i}) {pack.icon} {pack.label} ({pack.editor})")
    default_choice = ",".join(str(i) for i, p in enumerate(packs, 1) if p.key in current)
    chosen = ask("Languages (numbers, comma-separated)", default_choice, lambda t: parse_language_choice(t, current))

    for pack in packs:
        block = config["languages"][pack.key]
        block["enabled"] = pack.key in chosen
        if block["enabled"]:
            ask_language(pack, block)

    email["send_days"] = ask("\nProgress email days", ",".join(d[:3] for d in email["send_days"]), check_days)
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

    env_before = {k: get_pack(k).hook_installed() for k in HOOK_ENV_PACKS}
    for pack in packs:
        try:
            if pack.key in chosen:
                # install() already self-tests the hooks that change an environment variable.
                ok, message = pack.install(config["languages"][pack.key], DATA_DIR)
                print(f"  {'✓' if ok else '✗'} {pack.icon} {message}")
            elif pack.hook_installed():
                print(f"  ✓ {pack.icon} {pack.uninstall()} (your data is kept)")
        except Exception as error:
            print(f"  ✗ {pack.icon} {pack.label}: {error}")
    if schedule_task(email["send_time"]):
        powershell(f"Unregister-ScheduledTask -TaskName '{OLD_TASK_NAME}' -Confirm:$false")   # old name; may not exist
    else:
        print(f"  - Kept the old task '{OLD_TASK_NAME}' so you still get your daily refresh.")
    if any(get_pack(k).hook_installed() != env_before[k] for k in HOOK_ENV_PACKS):
        print("  ↻ Restart Eclipse and VS Code once so they pick up the tracker.")

    from dashboard import write_dashboard, write_plan
    from track import build_report
    report = build_report(config)
    plan_path = write_plan(config)
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

    summary = " · ".join(
        f"{p.icon} {p.label} ({p.curriculum()['plans'][config['languages'][p.key]['plan']]['label']}) "
        f"from {short_date(config['languages'][p.key]['start_date'])}" for p in packs if p.key in chosen)
    print(f"\n✅ All set! {summary}")
    print("   Write and run code in your folders as usual; it's tracked automatically.")
    print("   Refresh the dashboard any time with:  python tracker\\track.py\n")
    webbrowser.open(plan_path.as_uri())


def uninstall():
    for pack in all_packs():
        try:
            print(f"  ✓ {pack.icon} {pack.uninstall()}")
        except Exception as error:
            print(f"  ✗ {pack.icon} {pack.label}: {error}")
    for name in (TASK_NAME, OLD_TASK_NAME):
        result = powershell(f"Unregister-ScheduledTask -TaskName '{name}' -Confirm:$false")
        print(f"  ✓ Daily task '{name}' removed" if result.returncode == 0 else f"  - No task '{name}' found")
    remove_password()
    print("  ✓ App Password removed")
    print(f"Your data and config are still in {TRACKER_DIR}")


if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        setup()
