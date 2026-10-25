"""Builds the full progress report from the run log, then writes the dashboard.

Run it any time to refresh your dashboard:
    python tracker\\track.py
"""

import datetime as dt
import json
import sys
import webbrowser
from collections import Counter
from pathlib import Path

from analyzer import analyze_source
from settings import RUNS_PATH, SNAPSHOT_DIR, load_config, load_curriculum

DAY = dt.timedelta(days=1)


# ---------- loading runs ----------

def load_runs(start_date):
    """All logged runs on or after the start date, oldest first."""
    runs = []
    if not RUNS_PATH.exists():
        return runs
    with open(RUNS_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                run = json.loads(line)
                run["dt"] = dt.datetime.fromisoformat(run["time"])
            except (ValueError, KeyError):
                continue  # skip a damaged line rather than crash
            if run["dt"].date() >= start_date:
                runs.append(run)
    runs.sort(key=lambda r: r["dt"])
    return runs


def attach_analysis(runs):
    """Analyse the code snapshot of each run (each unique version only once)."""
    cache = {}
    for run in runs:
        key = (run.get("sha"), run["file"])
        if key not in cache:
            snapshot = SNAPSHOT_DIR / f"{run.get('sha')}.py"
            if snapshot.exists():
                source = snapshot.read_text(encoding="utf-8-sig", errors="replace")
                cache[key] = analyze_source(source, run["file"])
            else:
                cache[key] = None
        run["analysis"] = cache[key]


# ---------- schedule & levels ----------

def build_levels(curriculum, plan, start_date, today, runs):
    """Work out each level's dates, topic progress and status."""
    # The first date each topic appeared in a successful run.
    topic_first = {}
    for run in runs:
        if run["status"] == "success" and run["analysis"]:
            for topic in run["analysis"]["topics"]:
                if topic not in topic_first:
                    topic_first[topic] = (run["dt"].date(), Path(run["file"]).name)

    levels = []
    day_offset = 0
    previous_done_on = start_date
    current_found = False
    for level in curriculum["levels"]:
        days = level["days"][plan]
        starts = start_date + dt.timedelta(days=day_offset)
        due = start_date + dt.timedelta(days=day_offset + days - 1)
        day_offset += days

        topics = []
        for t in level["topics"]:
            done = topic_first.get(t["id"])
            topics.append({**t, "done": done is not None,
                           "done_on": done[0].isoformat() if done else None,
                           "file": done[1] if done else None})
        all_done = all(t["done"] for t in topics)

        # Levels complete in order: a level finishes when all its topics are
        # done AND the level before it is finished.
        done_on = None
        if all_done and previous_done_on is not None:
            done_on = max([previous_done_on] + [dt.date.fromisoformat(t["done_on"]) for t in topics])
        previous_done_on = done_on

        if done_on:
            status = "done"
        elif not current_found:
            current_found = True
            status = "overdue" if today > due else "current"
        else:
            status = "upcoming"

        levels.append({
            "id": level["id"], "name": level["name"], "tier": level["tier"],
            "days": days, "starts": starts.isoformat(), "due": due.isoformat(),
            "status": status, "done_on": done_on.isoformat() if done_on else None,
            "late_by": (done_on - due).days if done_on and done_on > due else 0,
            "overdue_days": (today - due).days if status == "overdue" else 0,
            "topics": topics, "topics_done": sum(t["done"] for t in topics),
            "links": level["links"], "project": level["project"],
        })
    return levels


# ---------- activity stats ----------

def streaks(success_days, today):
    """Current streak (ending today or yesterday) and best streak ever."""
    current = 0
    day = today if today in success_days else today - DAY
    while day in success_days:
        current += 1
        day -= DAY

    best = run = 0
    previous = None
    for day in sorted(success_days):
        run = run + 1 if previous and day - previous == DAY else 1
        best = max(best, run)
        previous = day
    return current, best


def latest_per_file(runs):
    """The most recent successful run of each file (its latest version)."""
    latest = {}
    for run in runs:
        if run["status"] == "success" and run["analysis"]:
            latest[run["file"]] = run
    return latest


def saved_not_run(code_folder, runs, today):
    """.py files saved in the last 7 days that were never run."""
    ran = {r["file"].lower() for r in runs}
    since = dt.datetime.combine(today - 6 * DAY, dt.time())
    names = []
    tracker_dir = Path(__file__).resolve().parent
    for path in Path(code_folder).rglob("*.py"):
        if tracker_dir in path.resolve().parents:
            continue
        try:
            modified = dt.datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if modified >= since and str(path.resolve()).lower() not in ran:
            names.append(path.name)
    return sorted(names)[:15]


# ---------- the report ----------

def build_report(config=None, curriculum=None, today=None):
    config = config or load_config()
    curriculum = curriculum or load_curriculum()
    today = today or dt.date.today()
    plan_key = config["plan"]
    plan = curriculum["plans"][plan_key]
    start_date = dt.date.fromisoformat(config["start_date"])

    runs = [r for r in load_runs(start_date) if r["dt"].date() <= today]
    attach_analysis(runs)
    levels = build_levels(curriculum, plan_key, start_date, today, runs)

    total_days = sum(l["days"] for l in levels)
    planned_finish = start_date + dt.timedelta(days=total_days - 1)
    current = next((l for l in levels if l["status"] in ("current", "overdue")), None)
    behind = current["overdue_days"] if current else 0
    levels_done = sum(l["status"] == "done" for l in levels)
    topics_total = sum(len(l["topics"]) for l in levels)
    topics_done = sum(l["topics_done"] for l in levels)

    # Activity
    week_start = today - dt.timedelta(days=today.weekday())  # Monday
    success_days = {r["dt"].date() for r in runs if r["status"] == "success"}
    streak, best_streak = streaks(success_days, today)
    today_runs = [r for r in runs if r["dt"].date() == today]
    week_runs = [r for r in runs if r["dt"].date() >= week_start]
    week_success = [r for r in week_runs if r["status"] == "success"]
    latest = latest_per_file(runs)
    week_lines = sum(r["analysis"]["lines"] for r in latest_per_file(week_runs).values())
    last_run = runs[-1]["dt"].date() if runs else None
    if today < start_date:
        days_inactive = 0
    else:
        days_inactive = (today - (last_run or start_date)).days

    # Charts: last 14 days
    chart_days = [today - dt.timedelta(days=i) for i in range(13, -1, -1)]
    daily = []
    for day in chart_days:
        day_runs = [r for r in runs if r["dt"].date() == day]
        scores = [r["analysis"]["score"] for r in day_runs if r["status"] == "success" and r["analysis"]]
        daily.append({
            "date": day.isoformat(),
            "success": sum(r["status"] == "success" for r in day_runs),
            "error": sum(r["status"] != "success" for r in day_runs),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        })

    # Plan vs actual: levels finished by each week since the start
    plan_vs_actual = []
    if today >= start_date:
        point = start_date
        while True:
            planned = sum(dt.date.fromisoformat(l["due"]) <= point for l in levels)
            actual = sum(bool(l["done_on"]) and dt.date.fromisoformat(l["done_on"]) <= point for l in levels)
            plan_vs_actual.append({"date": point.isoformat(), "planned": planned, "actual": actual})
            if point >= today:
                break
            point = min(point + 7 * DAY, today)

    # Errors in the last 30 days
    error_counts = Counter()
    error_last = {}
    for r in runs:
        if r["status"] == "error" and r["dt"].date() > today - 30 * DAY:
            error_counts[r["error"]] += 1
            error_last[r["error"]] = r["dt"].date().isoformat()
    errors = [{"error": e, "count": c, "last_seen": error_last[e]} for e, c in error_counts.most_common(6)]

    recent = []
    for r in reversed(runs[-15:]):
        a = r["analysis"] or {}
        recent.append({"time": r["dt"].isoformat(timespec="minutes"), "file": Path(r["file"]).name,
                       "status": r["status"], "error": r.get("error"),
                       "score": a.get("score"), "level": a.get("level"), "lines": a.get("lines")})

    scores = [r["analysis"]["score"] for r in latest.values()]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "generated": dt.datetime.now().isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "learner": config["learner_name"],
        "plan_key": plan_key,
        "plan": plan,
        "start_date": start_date.isoformat(),
        "day_number": (today - start_date).days + 1,
        "total_days": total_days,
        "planned_finish": planned_finish.isoformat(),
        "expected_finish": (planned_finish + dt.timedelta(days=behind)).isoformat(),
        "days_behind": behind,
        "levels": levels,
        "current_level": current,
        "levels_done": levels_done,
        "topics_done": topics_done,
        "topics_total": topics_total,
        "stats": {
            "streak": streak, "best_streak": best_streak,
            "runs_today": len(today_runs),
            "success_today": sum(r["status"] == "success" for r in today_runs),
            "runs_week": len(week_runs), "success_week": len(week_success),
            "week_lines": week_lines,
            "files_total": len(latest),
            "lines_total": sum(r["analysis"]["lines"] for r in latest.values()),
            "avg_score": avg_score,
            "avg_level": "Beginner" if avg_score <= 10 else "Intermediate" if avg_score <= 30 else "Advanced",
            "last_run": last_run.isoformat() if last_run else None,
            "days_inactive": days_inactive,
            "total_runs": len(runs),
        },
        "daily": daily,
        "plan_vs_actual": plan_vs_actual,
        "errors": errors,
        "recent": recent,
        "saved_not_run": saved_not_run(config["code_folder"], runs, today),
        "_runs": runs,  # raw runs for the emailer (not shown on the dashboard)
    }


def main():
    from dashboard import write_dashboard, write_plan

    report = build_report()
    write_plan(load_config(), load_curriculum())
    path = write_dashboard(report)
    cur = report["current_level"]
    print(f"Day {report['day_number']} of {report['total_days']} · "
          f"{report['levels_done']}/9 levels done · "
          f"{'all levels complete!' if not cur else 'current: ' + cur['name']}")
    print(f"Dashboard: {path}")
    if "--no-open" not in sys.argv:
        webbrowser.open(path.as_uri())


if __name__ == "__main__":
    main()
