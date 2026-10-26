import unittest
from datetime import date

from tests.helpers import fresh_home, write_runs

JAVA_CURRICULUM = {
    "language": "java", "editor": "Eclipse", "extensions": [".java"],
    "plans": {"standard": {"label": "Standard", "daily_runs_target": 2, "weekly_lines_target": 150,
                           "streak_target_days": 30}},
    "levels": [{"id": 1, "name": "Basics", "tier": "Beginner", "days": {"standard": 7}, "project": "p",
                "links": [], "topics": [{"id": "class", "title": "Class"}, {"id": "println", "title": "println"}]}],
}
FAKE = {"topics": ["println"], "score": 1, "level": "Beginner", "lines": 3, "syntax_ok": True}


def make_config(py_start="2026-10-01", java_start="2026-11-01"):
    return {
        "learner_name": "S",
        "languages": {
            "python": {"enabled": True, "start_date": py_start, "plan": "standard", "code_folder": r"C:\Python"},
            "java": {"enabled": True, "start_date": java_start, "plan": "standard", "code_folder": r"C:\nowhere",
                     "extra_workspaces": [], "exclude_folders": []},
            "javascript": {"enabled": False, "start_date": "", "plan": "standard", "code_folder": r"C:\nowhere"},
        },
    }


def jrun(day, status, sha, **extra):
    run = {"time": f"2026-{day}T10:00:00", "file": r"C:\ws\A.java", "status": status, "error": None,
           "error_count": None, "duration": 1, "source": "javac", "files": [{"file": r"C:\ws\A.java", "sha": sha}]}
    run.update(extra)
    return run


def prun(day, sha="p1", status="success"):
    return {"time": f"2026-{day}T10:00:00", "file": r"C:\Python\a.py", "status": status, "error": None,
            "duration": 1, "source": "hook", "files": [{"file": r"C:\Python\a.py", "sha": sha}]}


class TrackTests(unittest.TestCase):
    def setUp(self):
        self.home = fresh_home()
        from languages import get_pack
        import track
        self.track = track
        self.java = get_pack("java")
        self.old = (self.java.analyze, getattr(self.java, "_curriculum", None))
        self.java.analyze = lambda source, path=None: dict(FAKE)
        self.java._curriculum = JAVA_CURRICULUM
        self.addCleanup(self.restore)
        self.config = make_config()

    def restore(self):
        del self.java.analyze
        if self.old[1] is None:
            del self.java._curriculum
        else:
            self.java._curriculum = self.old[1]

    def snap(self, key, sha, ext, text="x"):
        d = self.home / "data" / key / "snapshots"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{sha}{ext}").write_text(text)

    def java_runs(self, entries):
        write_runs(self.home / "data" / "java" / "runs.jsonl", entries)

    def test_compiled_counts_and_compile_error_does_not(self):
        self.java_runs([jrun("11-02", "compiled", "a"), jrun("11-03", "compile_error", "b", error_count=2)])
        self.snap("java", "a", ".java")
        self.snap("java", "b", ".java")
        rep = self.track.build_report(self.config, today=date(2026, 11, 3))["languages"]["java"]
        self.assertEqual(rep["stats"]["streak"], 1)
        self.assertTrue(rep["levels"][0]["topics"][1]["done"])
        self.assertEqual(rep["errors"][0]["error"], "2 compile errors")
        self.assertEqual(rep["language"], "java")
        self.assertEqual(rep["curriculum_levels"], 1)
        self.assertEqual(rep["recent"][0]["source"], "javac")
        self.assertEqual(rep["recent"][0]["folder"], r"C:\ws")

    def test_language_start_dates_are_separate(self):
        self.java_runs([jrun("10-15", "compiled", "a")])
        self.snap("java", "a", ".java")
        rep = self.track.build_report(self.config, today=date(2026, 11, 3))
        self.assertEqual(rep["languages"]["java"]["stats"]["total_runs"], 0)

    def test_one_language_failing_keeps_others(self):
        def boom(source, path=None):
            raise RuntimeError("boom")
        self.java.analyze = boom
        self.java_runs([jrun("11-02", "compiled", "a")])
        self.snap("java", "a", ".java")
        write_runs(self.home / "data" / "python" / "runs.jsonl", [prun("10-02")])
        self.snap("python", "p1", ".py", "print(1)\n")
        rep = self.track.build_report(self.config, today=date(2026, 11, 3))
        self.assertEqual(rep["languages"]["java"]["error"], "boom")
        self.assertIn("levels", rep["languages"]["python"])
        self.assertTrue((self.home / "data" / "send_report.log").exists())

    def test_saved_counts_only_when_syntax_ok(self):
        self.java_runs([jrun("11-02", "saved", "a", source="saved")])
        self.snap("java", "a", ".java")
        rep = self.track.build_report(self.config, today=date(2026, 11, 3))["languages"]["java"]
        self.assertTrue(rep["levels"][0]["topics"][1]["done"])
        self.java.analyze = lambda s, path=None: {**FAKE, "syntax_ok": False}
        rep = self.track.build_report(self.config, today=date(2026, 11, 3))["languages"]["java"]
        self.assertFalse(rep["levels"][0]["topics"][1]["done"])
        self.assertEqual(rep["stats"]["streak"], 0)

    def test_overall_any_streak_spans_languages(self):
        write_runs(self.home / "data" / "python" / "runs.jsonl", [prun("11-02")])
        self.snap("python", "p1", ".py", "print(1)\n")
        self.java_runs([jrun("11-03", "compiled", "a")])
        self.snap("java", "a", ".java")
        rep = self.track.build_report(self.config, today=date(2026, 11, 3))
        self.assertEqual(rep["overall"]["any_streak"], 2)
        self.assertEqual(len(rep["overall"]["daily_by_language"]), 14)
        last = rep["overall"]["daily_by_language"][-1]
        self.assertEqual((last["date"], last["java"], last["python"]), ("2026-11-03", 1, 0))
        self.assertEqual(rep["enabled"], ["python", "java"])

    def test_python_migrated_entries_still_analysed(self):
        from settings import save_json, load_config
        save_json(self.home / "config.json", {"learner_name": "S", "start_date": "2026-10-01", "plan": "standard",
                                              "code_folder": r"C:\Python", "email": {}, "alerts": {}})
        write_runs(self.home / "data" / "runs.jsonl", [{"time": "2026-10-02T10:00:00", "file": r"C:\Python\a.py",
                                                        "status": "success", "error": None, "duration": 1,
                                                        "sha": "abc"}])
        (self.home / "data" / "snapshots").mkdir(parents=True)
        (self.home / "data" / "snapshots" / "abc.py").write_text("print('hi')\n")
        config = load_config()
        rep = self.track.build_report(config, today=date(2026, 10, 3))["languages"]["python"]
        self.assertGreater(rep["topics_done"], 0)

    def test_collect_sees_pre_start_runs_every_build(self):
        self.java_runs([jrun("10-15", "compiled", "pre")])
        seen = []
        self.java.collect = lambda cfg, d, runs: seen.append([f["sha"] for r in runs for f in r["files"]]) or []
        self.addCleanup(lambda: delattr(self.java, "collect"))
        for _ in range(2):
            rep = self.track.build_report(self.config, today=date(2026, 11, 3))["languages"]["java"]
        self.assertEqual(seen, [["pre"], ["pre"]])
        self.assertEqual(rep["stats"]["total_runs"], 0)

    def test_saved_not_run_skips_dependency_folders(self):
        import datetime as dt, time
        code = self.home / "code"
        for rel in ("good.java", "node_modules/x.java", ".git/y.java", "bin/z.java"):
            p = code / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")
        today = dt.date.fromtimestamp(time.time())
        names = self.track.saved_not_run(code, {".java"}, [], today)
        self.assertEqual(names, ["good.java"])

    def test_counts(self):
        t = self.track
        self.assertTrue(t.counts({"status": "compiled"}))
        self.assertFalse(t.counts({"status": "compile_error"}))
        self.assertFalse(t.counts({"status": "saved", "analysis": None}))
        self.assertTrue(t.counts({"status": "saved", "analysis": {"syntax_ok": True}}))


if __name__ == "__main__":
    unittest.main()
