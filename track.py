"""Builds the progress report for each enabled language, plus an overall summary.

Run it any time to see where you are:
    python tracker\\track.py
"""

import datetime as dt
import json
import os
import traceback
from collections import Counter
from pathlib import Path

from languages import get_pack
from settings import enabled_languages, lang_dir, load_config, log_line, runs_path, snapshot_dir

DAY = dt.timedelta(days=1)
COUNTING = {"success", "compiled"}


def counts(run):
    """Does this run count toward topics, streaks and the daily target?"""
    if run["status"] in COUNTING:
        return True
    analysis = run.get("analysis")
    return run["status"] == "saved" and bool(analysis and analysis.get("syntax_ok"))


# ---------- loading runs ----------

def parse_run(run):
    run["dt"] = dt.datetime.fromisoformat(run["time"])
    return run


def load_runs(key, start_date=None):
    """Logged runs of one language on or after its start date (None = all), oldest first."""
    runs = []
    path = runs_path(key)
    if not path.exists():
        return runs
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                run = parse_run(json.loads(line))
            except (ValueError, KeyError, TypeError):
                continue  # skip a damaged line rather than crash
            if start_date is None or run["dt"].date() >= start_date:
                runs.append(run)
    runs.sort(key=lambda r: r["dt"])
    return runs


def run_files(run):
    """The [{"file", "sha"}] list of a run (very old entries only have file + sha)."""
    files = run.get("files")
    if files is None and run.get("sha"):
        files = [{"file": run.get("file", ""), "sha": run["sha"]}]
    return files or []


def attach_analysis(pack, key, runs):
    """Analyse the snapshots of each run (each unique version only once)."""
    cache = {}
    folder = snapshot_dir(key)
    for run in runs:
        results = []
        for item in run_files(run):
            ck = (item["sha"], item["file"])
            if ck not in cache:
                snapshot = folder / f"{item['sha']}{Path(item['file']).suffix.lower()}"
                if snapshot.exists():
                    source = snapshot.read_text(encoding="utf-8-sig", errors="replace")
                    cache[ck] = pack.analyze(source, item["file"])
                else:
                    cache[ck] = None
            if cache[ck] is not None:
                results.append(cache[ck])
        if not results:
            run["analysis"] = None
            continue
        best = max(results, key=lambda a: a["score"])
        topics = []
        for a in results:
            topics += [t for t in a["topics"] if t not in topics]
        run["analysis"] = {"topics": topics, "score": best["score"], "level": best["level"],
                           "lines": sum(a["lines"] for a in results),
                           "syntax_ok": all(a.get("syntax_ok", True) for a in results)}


# ---------- schedule & levels ----------

def build_levels(curriculum, plan, start_date, today, runs):
    """Work out each level's dates, topic progress and status."""
    # The first date each topic appeared in a counting run.
    topic_first = {}
    for run in runs:
        if counts(run) and run["analysis"]:
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
    """The most recent counting run of each file (its latest version)."""
    latest = {}
    for run in runs:
        if counts(run) and run["analysis"]:
            latest[run["file"]] = run
    return latest


SKIP_DIRS = {"node_modules", ".git", ".metadata", ".vscode", ".idea", "bin", "build", "dist",
             "target", "__pycache__"}


def saved_not_run(code_folder, extensions, runs, today):
    """Source files saved in the last 7 days that were never run."""
    ran = {r["file"].lower() for r in runs} | {f["file"].lower() for r in runs for f in run_files(r)}
    since = dt.datetime.combine(today - 6 * DAY, dt.time())
    names = []
    tracker_dir = Path(__file__).resolve().parent
    for root, dirs, files in os.walk(code_folder):
        # Prune dependency/build folders and the tracker itself so we never descend into them.
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and (Path(root) / d).resolve() != tracker_dir]
        for name in files:
            path = Path(root) / name
            if path.suffix.lower() not in extensions:
                continue
            try:
                modified = dt.datetime.fromtimestamp(path.stat().st_mtime)
            except OSError:
                continue
            if modified >= since and str(path.resolve()).lower() not in ran:
                names.append(path.name)
    return sorted(names)[:15]


# ---------- the reports ----------

def build_language_report(key, config, today):
    pack = get_pack(key)
    lang_config = config["languages"][key]
    curriculum = pack.curriculum()
    plan_key = lang_config["plan"]
    plan = curriculum["plans"][plan_key]
    start_date = dt.date.fromisoformat(lang_config["start_date"])

    # Collectors (agent logs, saved-file scans...) append to this language's runs.jsonl.
    # Collectors dedupe against ALL runs (not just those after the start date).
    collected = pack.collect(lang_config, lang_dir(key), load_runs(key)) or []
    runs = [r for r in load_runs(key, start_date) if r["dt"].date() <= today]
    seen = {(r["time"], r.get("file"), r["status"]) for r in runs}
    for entry in collected:
        try:
            entry = parse_run(dict(entry))
        except (ValueError, KeyError, TypeError):
            continue
        if start_date <= entry["dt"].date() <= today and (entry["time"], entry.get("file"), entry["status"]) not in seen:
            runs.append(entry)
    runs.sort(key=lambda r: r["dt"])
    attach_analysis(pack, key, runs)
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
    success_days = {r["dt"].date() for r in runs if counts(r)}
    streak, best_streak = streaks(success_days, today)
    today_runs = [r for r in runs if r["dt"].date() == today]
    week_runs = [r for r in runs if r["dt"].date() >= week_start]
    week_success = [r for r in week_runs if counts(r)]
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
        scores = [r["analysis"]["score"] for r in day_runs if counts(r) and r["analysis"]]
        daily.append({
            "date": day.isoformat(),
            "success": sum(counts(r) for r in day_runs),
            "error": sum(not counts(r) for r in day_runs),
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
        if r["status"] in ("error", "compile_error") and r["dt"].date() > today - 30 * DAY:
            label = r.get("error")
            if not label:
                label = f"{r.get('error_count') or 0} compile errors" if r["status"] == "compile_error" else "error"
            error_counts[label] += 1
            error_last[label] = r["dt"].date().isoformat()
    errors = [{"error": e, "count": c, "last_seen": error_last[e]} for e, c in error_counts.most_common(6)]

    recent = []
    for r in reversed(runs[-15:]):
        a = r["analysis"] or {}
        recent.append({"time": r["dt"].isoformat(timespec="minutes"), "file": Path(r["file"]).name,
                       "folder": str(Path(r["file"]).parent), "source": r.get("source"),
                       "status": r["status"], "error": r.get("error"),
                       "score": a.get("score"), "level": a.get("level"), "lines": a.get("lines")})

    scores = [r["analysis"]["score"] for r in latest.values()]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return {
        "language": key, "label": pack.label, "icon": pack.icon, "editor": pack.editor,
        "curriculum_levels": len(curriculum["levels"]),
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
            "success_today": sum(counts(r) for r in today_runs),
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
        "saved_not_run": saved_not_run(lang_config["code_folder"], pack.extensions, runs, today),
        "_runs": runs,  # raw runs for the emailer (not shown on the dashboard)
    }


def build_report(config=None, today=None):
    config = config or load_config()
    today = today or dt.date.today()
    keys = enabled_languages(config)

    languages = {}
    for key in keys:
        try:
            languages[key] = build_language_report(key, config, today)
        except Exception as exc:
            pack = get_pack(key)
            log_line(f"ERROR building the {key} report\n" + traceback.format_exc())
            languages[key] = {"language": key, "label": pack.label, "icon": pack.icon, "error": str(exc)}

    # Overall: streaks and the chart use counting runs; week_activity counts every run.
    counting_days = set()
    per_day = Counter()
    week_start = today - dt.timedelta(days=today.weekday())
    week_activity = 0
    for key, rep in languages.items():
        if "error" in rep:
            continue
        for r in rep["_runs"]:
            week_activity += r["dt"].date() >= week_start
            if counts(r):
                counting_days.add(r["dt"].date())
                per_day[(r["dt"].date(), key)] += 1
    daily_by_language = []
    for i in range(13, -1, -1):
        day = today - i * DAY
        daily_by_language.append({"date": day.isoformat(), **{k: per_day[(day, k)] for k in keys}})

    return {
        "generated": dt.datetime.now().isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "learner": config["learner_name"],
        "languages": languages,
        "overall": {"any_streak": streaks(counting_days, today)[0], "week_activity": week_activity,
                    "daily_by_language": daily_by_language},
        "enabled": keys,
    }


def main():
    report = build_report()
    for rep in report["languages"].values():
        if "error" in rep:
            print(f"{rep['icon']} {rep['label']}: could not build the report ({rep['error']})")
            continue
        cur = rep["current_level"]
        print(f"{rep['icon']} {rep['label']}: day {rep['day_number']} of {rep['total_days']} · "
              f"{rep['levels_done']}/{rep['curriculum_levels']} levels · "
              f"{'all levels complete!' if not cur else 'current: ' + cur['name']}")


if __name__ == "__main__":
    main()
