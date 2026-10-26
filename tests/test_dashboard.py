import json
import re
import unittest
from datetime import date

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from tests.helpers import fresh_home, write_runs
from tests.test_track import make_config


def embedded(path, var):
    html = path.read_text(encoding="utf-8")
    return json.loads(re.search(rf"const {var} = (.*?);\n", html).group(1)), html


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.home = fresh_home()
        import dashboard
        import track
        self.dashboard, self.track = dashboard, track
        self.config = make_config(py_start="2026-10-01", java_start="2026-10-01")

    def report(self):
        return self.track.build_report(self.config, today=date(2026, 10, 5))

    def test_dashboard_embeds_each_enabled_language(self):
        data, _ = embedded(self.dashboard.write_dashboard(self.report(), self.home / "d.html"), "R")
        self.assertEqual(sorted(data["languages"]), ["java", "python"])
        self.assertEqual(data["enabled"], ["python", "java"])
        self.assertNotIn('"_runs"', json.dumps(data))  # plan has daily_runs_target, so test the key

    def test_error_language_still_renders_page(self):
        report = self.report()
        report["languages"]["java"] = {"language": "java", "label": "Java", "icon": "☕", "error": "boom"}
        data, html = embedded(self.dashboard.write_dashboard(report, self.home / "d.html"), "R")
        self.assertEqual(data["languages"]["java"]["error"], "boom")
        self.assertIn("send_report.log", html)

    def test_plan_has_all_three_courses(self):
        self.config["languages"]["java"]["enabled"] = False
        data, _ = embedded(self.dashboard.write_plan(self.config, self.home / "p.html"), "D")
        self.assertEqual(sorted(data["courses"]), ["java", "javascript", "python"])
        self.assertEqual(list(data["mine"]), ["python"])
        self.assertEqual(data["mine"]["python"]["start"], "2026-10-01")
        self.assertEqual(data["courses"]["java"]["editor"], "Eclipse")

    def test_plan_note_for_language_not_enabled_points_to_setup(self):
        html = self.dashboard.write_plan(self.config, self.home / "p.html").read_text(encoding="utf-8")
        self.assertIn(r"To learn it, re-run python tracker\\setup.py and choose it.", html)   # JS source escapes the backslash
        self.assertIn("Preview only. To switch, edit", html)   # enabled-language wording is kept

    def test_script_close_tag_escaped(self):
        write_runs(self.home / "data" / "python" / "runs.jsonl", [
            {"time": "2026-10-02T10:00:00", "file": r"C:\Python.py", "status": "error", "error": "</script><b>",
             "duration": 1, "source": "hook", "files": []}])
        path = self.dashboard.write_dashboard(self.report(), self.home / "d.html")
        html = path.read_text(encoding="utf-8")
        self.assertEqual(html.count("</script>"), 2)  # Chart.js tag + the page script only
        data, _ = embedded(path, "R")
        self.assertEqual(data["languages"]["python"]["errors"][0]["error"], "</script><b>")

    def test_errors_container_scrolls_inside_card(self):
        html = self.dashboard.write_dashboard(self.report(), self.home / "d.html").read_text(encoding="utf-8")
        self.assertIn('<div class="table-wrap" id="${k}-errors">', html)


if __name__ == "__main__":
    unittest.main()
