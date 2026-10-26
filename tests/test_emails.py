import datetime as dt
import json
import unittest
from datetime import date
from unittest import mock

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from tests.helpers import fresh_home
from tests.test_track import make_config

TODAY = date(2026, 10, 26)


class EmailTests(unittest.TestCase):
    def setUp(self):
        self.home = fresh_home()
        import emailer
        import send_report
        import settings
        import track
        self.emailer, self.send_report, self.settings, self.track = emailer, send_report, settings, track

    def config(self, py_start="2026-10-01", java_start="2026-10-01", java=True):
        config = make_config(py_start, java_start)
        config["languages"]["python"]["code_folder"] = r"C:\nowhere"
        config["languages"]["java"]["enabled"] = java
        config["email"] = {"enabled": True, "to": ["x@example.com"], "sender": "", "send_days": [], "send_time": "08:00"}
        config["alerts"] = {"stuck_enabled": True, "reminder_every_days": 3, "inactive_after_days": 5}
        return config

    def report(self, config=None, **levels):
        """A real report, with the current level / days behind overridden per language: key=(id, name, behind)."""
        report = self.track.build_report(config or self.config(), today=TODAY)
        for key, (level_id, name, behind) in levels.items():
            rep = report["languages"][key]
            rep["current_level"] = dict(rep["current_level"], id=int(level_id[1:]), name=name)
            rep["days_behind"] = behind
        return report

    def test_progress_subject_lists_languages(self):
        report = self.report(python=("L4", "Functions", 0), java=("L2", "Control Flow", 3))
        report["overall"]["any_streak"] = 15
        subject, html, text = self.emailer.progress_email(report)
        self.assertEqual(subject, "📚 Progress: 🐍 L4 Functions · ☕ L2 Control Flow (3 days behind) · 🔥 15-day streak")
        self.assertNotIn("def ", html)
        self.assertNotIn("Python Progress", html)

    def test_progress_subject_all_done(self):
        report = self.report()
        report["languages"]["java"]["current_level"] = None
        subject, html, _ = self.emailer.progress_email(report)
        self.assertIn("☕ all done", subject)
        self.assertIn(f"All {len(report['languages']['java']['levels'])} levels complete", html)

    def test_single_language_progress_email(self):
        config = self.config(java=False)
        subject, html, _ = self.emailer.progress_email(self.report(config))
        self.assertTrue(subject.startswith("📚 Progress: 🐍 L"))
        self.assertNotIn("Java", html)
        self.assertNotIn("couldn't read", html)

    def test_error_language_gets_one_line_row(self):
        report = self.report()
        report["languages"]["java"] = {"language": "java", "label": "Java", "icon": "☕", "error": "boom"}
        subject, html, text = self.emailer.progress_email(report)
        self.assertIn("couldn't read", html)
        self.assertNotIn("☕", subject)
        self.assertNotIn("boom", html)

    def test_learner_text_is_escaped(self):
        report = self.report()
        report["learner"] = "<script>x</script>"
        _, html, _ = self.emailer.progress_email(report)
        self.assertNotIn("<script>x", html)

    def test_from_header_name(self):
        sent = {}

        class Server:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def login(self, *a): pass
            def send_message(self, message): sent["from"] = message["From"]

        with mock.patch.object(self.emailer.smtplib, "SMTP_SSL", Server):
            self.emailer.send_email({"email": {"to": ["a@b.c"], "sender": "me@b.c"}}, "s", "<p>h</p>", "t", password="pw")
        self.assertEqual(sent["from"], "Learning Tracker <me@b.c>")

    def overdue(self):
        report = self.report()
        return report["languages"]["python"], report["languages"]["java"]

    def test_stuck_single_has_icon_in_front(self):
        py, _ = self.overdue()
        subject, html, _ = self.emailer.stuck_email([(py, False)])
        self.assertTrue(subject.startswith("🐍 ⚠️ Stuck on Level"))
        subject, _, _ = self.emailer.stuck_email([(py, True)])
        self.assertTrue(subject.startswith("🐍 ⚠️ Reminder: still stuck on Level"))

    def test_stuck_combined(self):
        py, java = self.overdue()
        subject, html, _ = self.emailer.stuck_email([(py, False), (java, True)])
        self.assertTrue(subject.startswith("⚠️ Stuck in 2 languages: 🐍 L"))
        self.assertIn(" · ☕ L", subject)
        self.assertIn("🐍", html)
        self.assertIn("☕", html)

    def test_inactive_subjects(self):
        py, java = self.overdue()
        days = py["stats"]["days_inactive"]
        subject, html, _ = self.emailer.inactive_email([py])
        self.assertEqual(subject, f"🐍 {days} days without Python, time for a quick session?")
        subject, html, text = self.emailer.inactive_email([py, java])
        self.assertEqual(subject, "👋 2 languages need a quick session")
        self.assertIn("Java", html)
        self.assertIn("Python", text)

    # ---------- the daily check ----------

    def run_daily(self, config, state=None, argv=(), mutate=None):
        """Run send_report.main() with email sending recorded (never sent) and today fixed."""
        self.settings.save_json(self.settings.CONFIG_PATH, config)
        if state is not None:
            self.settings.save_json(self.settings.EMAIL_STATE_PATH, state)
        real_build = self.track.build_report
        sent = []

        def build(cfg):
            report = real_build(cfg, today=TODAY)
            if mutate:
                mutate(report)
            return report
        with mock.patch.object(self.send_report, "send_email", lambda cfg, subject, h, t: sent.append(subject)), \
                mock.patch.object(self.send_report, "build_report", build), \
                mock.patch.object(self.emailer, "log_line", lambda text: None), \
                mock.patch.object(self.send_report, "log_line", lambda text: None), \
                mock.patch.object(self.send_report, "log", lambda text: None), \
                mock.patch.object(self.send_report.sys, "argv", ["send_report.py", *argv]):
            self.send_report.main()
        return sent

    def stuck_subjects(self, sent):
        return [s for s in sent if "Stuck" in s or "stuck" in s]

    def test_daily_check_alert_state_per_language(self):
        config = self.config(java_start="2026-11-01")           # java not started, python overdue
        level = str(self.track.build_report(config, today=TODAY)["languages"]["python"]["current_level"]["id"])
        first = self.run_daily(config)
        self.assertEqual(len(self.stuck_subjects(first)), 1)
        state = json.loads(self.settings.EMAIL_STATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(state["languages"]["python"]["alerts"], {level: TODAY.isoformat()})
        self.assertNotIn("java", state["languages"])
        second = self.run_daily(config)
        self.assertEqual(self.stuck_subjects(second), [])

    def test_two_overdue_languages_one_combined_email(self):
        sent = self.run_daily(self.config())
        stuck = self.stuck_subjects(sent)
        self.assertEqual(len(stuck), 1)
        self.assertTrue(stuck[0].startswith("⚠️ Stuck in 2 languages"))
        inactive = [s for s in sent if "language" in s and "quick session" in s]
        self.assertEqual(len(inactive), 1)
        state = json.loads(self.settings.EMAIL_STATE_PATH.read_text(encoding="utf-8"))
        for key in ("python", "java"):
            self.assertEqual(state["languages"][key]["last_inactive_sent"], TODAY.isoformat())
            self.assertEqual(len(state["languages"][key]["alerts"]), 1)

    def test_migrated_state_keeps_reminder_timing(self):
        config = self.config(java_start="2026-11-01")
        level = str(self.track.build_report(config, today=TODAY)["languages"]["python"]["current_level"]["id"])
        yesterday = (TODAY - dt.timedelta(days=1)).isoformat()
        # The old flat shape is migrated by load_config on start.
        old = {"last_progress_sent": None, "alerts": {level: yesterday}, "last_inactive_sent": None}
        sent = self.run_daily(config, old)
        self.assertEqual(self.stuck_subjects(sent), [])
        state = json.loads(self.settings.EMAIL_STATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(state["languages"]["python"]["alerts"], {level: yesterday})

    def test_broken_language_does_not_stop_the_others(self):
        def break_java(report):
            del report["languages"]["java"]["current_level"]["topics"]
        sent = self.run_daily(self.config(), argv=["--send-now"], mutate=break_java)
        progress = [s for s in sent if s.startswith("📚 Progress")]
        self.assertEqual(len(progress), 1)
        self.assertNotIn("☕ L", progress[0])
        stuck = self.stuck_subjects(sent)
        self.assertEqual(len(stuck), 1)
        self.assertTrue(stuck[0].startswith("🐍 ⚠️ Stuck on Level"))
        state = json.loads(self.settings.EMAIL_STATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(len(state["languages"]["python"]["alerts"]), 1)
        self.assertEqual(state["languages"].get("java", {}).get("alerts", {}), {})
        self.assertIsNone(state["languages"].get("java", {}).get("last_inactive_sent"))
        self.assertEqual(state["languages"]["python"]["last_inactive_sent"], TODAY.isoformat())

    def test_broken_language_row_in_progress_email(self):
        report = self.report()
        del report["languages"]["java"]["current_level"]["topics"]
        subject, html, _ = self.emailer.progress_email(report)
        self.assertIn("couldn't read", html)
        self.assertNotIn("☕ L", subject)

    def saved_run(self, name, ok):
        analysis = {"lines": 7, "score": 3, "level": "Beginner", "syntax_ok": ok, "topics": []}
        return {"status": "saved", "analysis": analysis, "file": "C:\\w\\" + name, "dt": dt.datetime(2026, 10, 20, 10, 0)}

    def test_files_table_uses_engine_counting_rule(self):
        report = self.report()
        report["languages"]["python"]["_runs"] = [self.saved_run("GoodSaved.py", True), self.saved_run("BadSaved.py", False)]
        _, html, _ = self.emailer.progress_email(report)
        self.assertIn("GoodSaved.py", html)
        self.assertNotIn("BadSaved.py", html)

    def test_failed_send_does_not_record_state(self):
        config = self.config(java_start="2026-11-01")
        self.settings.save_json(self.settings.CONFIG_PATH, config)
        real_build = self.track.build_report

        def boom(*a, **k):
            raise RuntimeError("smtp down")
        with mock.patch.object(self.send_report, "send_email", boom), \
                mock.patch.object(self.send_report, "build_report", lambda cfg: real_build(cfg, today=TODAY)), \
                mock.patch.object(self.send_report, "log", lambda text: None), \
                mock.patch.object(self.send_report.sys, "argv", ["send_report.py"]):
            self.send_report.main()
        state = json.loads(self.settings.EMAIL_STATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(state.get("languages", {}).get("python", {}).get("alerts", {}), {})


if __name__ == "__main__":
    unittest.main()
