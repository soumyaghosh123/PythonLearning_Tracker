import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tests import helpers
from tests.helpers import fresh_home

import setup
from languages import get_pack
from languages.python.pack import LOGGER_MARKER, PythonPack


class FakePack:
    """Records install/uninstall calls; takes its text from the real pack of the same key."""

    def __init__(self, key, installed=False):
        real = get_pack(key)
        self.key, self.label, self.icon, self.editor = real.key, real.label, real.icon, real.editor
        self.curriculum = real.curriculum
        self.installed, self.calls = installed, []

    def install(self, lang_config, data_dir):
        self.calls.append(("install", lang_config["code_folder"], data_dir))
        self.installed = True
        return True, f"{self.label} hook installed"

    def uninstall(self):
        self.calls.append(("uninstall",))
        self.installed = False
        return f"{self.label} hook removed"

    def hook_installed(self):
        return self.installed


class ParseChoiceTests(unittest.TestCase):
    def test_parse_language_choice(self):
        self.assertEqual(setup.parse_language_choice("3, 1", []), ["python", "javascript"])
        self.assertEqual(setup.parse_language_choice("1,3", []), ["python", "javascript"])
        self.assertEqual(setup.parse_language_choice("", ["java"]), ["java"])
        for bad in ("4", "0", "a", "1,x", ","):
            with self.assertRaises(ValueError) as ctx:
                setup.parse_language_choice(bad, [])
            self.assertEqual(str(ctx.exception), "Enter numbers 1-3, comma-separated")


class SetupFlowTests(unittest.TestCase):
    def run_setup(self, answers, packs, config=None):
        home = fresh_home()
        if config is not None:
            (home / "config.json").write_text(json.dumps(config), encoding="utf-8")
        by_key = {p.key: p for p in packs}
        feed = iter(answers)
        out = io.StringIO()

        def fake_input(prompt=""):
            print(prompt)
            return next(feed)

        with mock.patch("builtins.input", fake_input), \
             mock.patch("getpass.getpass", lambda prompt="": ""), \
             mock.patch.object(setup, "all_packs", lambda: packs), \
             mock.patch.object(setup, "get_pack", lambda k: by_key[k]), \
             mock.patch("languages.all_packs", lambda: packs), \
             mock.patch.object(setup, "schedule_task") as schedule, \
             mock.patch.object(setup, "powershell") as ps, \
             mock.patch.object(setup, "store_password"), \
             mock.patch.object(setup, "remove_password"), \
             mock.patch("webbrowser.open"), \
             mock.patch("track.build_report", return_value={"enabled": []}), \
             mock.patch("dashboard.write_plan", return_value=home / "plan.html"), \
             mock.patch("dashboard.write_dashboard"), \
             redirect_stdout(out):
            setup.setup()
        return home, out.getvalue(), schedule, ps

    def test_setup_installs_chosen_and_removes_dropped(self):
        code = tempfile.mkdtemp(prefix="setup_code_")
        folder = str(Path(code).resolve())
        packs = [FakePack("python"), FakePack("java"), FakePack("javascript", installed=True)]
        # name, email, languages, python(date, plan, folder), java(date, plan, folder), days, time, no email
        answers = ["Sam", "sam@example.com", "1,2", "2026-10-25", "2", code, "2026-11-01", "1", code, "", "", "n"]
        home, out, schedule, ps = self.run_setup(answers, packs)
        python, java, js = packs
        self.assertEqual(python.calls, [("install", folder, setup.DATA_DIR)])
        self.assertEqual(java.calls, [("install", folder, setup.DATA_DIR)])
        self.assertEqual(js.calls, [("uninstall",)])
        config = json.loads((home / "config.json").read_text(encoding="utf-8"))
        self.assertFalse(config["languages"]["javascript"]["enabled"])
        self.assertTrue(config["languages"]["python"]["enabled"] and config["languages"]["java"]["enabled"])
        self.assertEqual(config["languages"]["python"]["plan"], "aggressive")
        schedule.assert_called_once_with("08:00")
        self.assertTrue(any("PythonLearningTracker" in c.args[0] for c in ps.call_args_list))
        self.assertIn("📚 Learning Tracker: setup", out)
        self.assertIn("── ☕ Java ──", out)
        self.assertIn("Code folder (your Eclipse workspace)", out)
        self.assertIn("1) 🐍 Python (VS Code)", out)
        self.assertIn("✅ All set! 🐍 Python (Aggressive) from 25 Oct · ☕ Java (Standard) from 1 Nov", out)
        self.assertIn("Restart Eclipse and VS Code", out)       # the javascript hook was removed: env changed

    def test_no_restart_message_when_environment_unchanged(self):
        code = tempfile.mkdtemp(prefix="setup_code_")
        packs = [FakePack("python"), FakePack("java"), FakePack("javascript")]
        answers = ["Sam", "sam@example.com", "1", "2026-10-25", "", code, "", "", "n"]
        _, out, _, _ = self.run_setup(answers, packs)
        self.assertNotIn("Restart Eclipse", out)
        self.assertEqual(packs[1].calls, [])
        self.assertEqual(packs[2].calls, [])

    def test_migrated_config_reinstalls_python_logger(self):
        code = tempfile.mkdtemp(prefix="setup_code_")
        old = {"learner_name": "Sam", "start_date": "2026-10-01", "plan": "aggressive", "code_folder": code,
               "email": {"to": ["sam@example.com"]}, "alerts": {}}
        packs = [FakePack("python", installed=True), FakePack("java"), FakePack("javascript")]
        answers = ["", "", "", "", "", "", "", "", "n"]       # keep everything
        home, out, _, _ = self.run_setup(answers, packs, config=old)
        self.assertEqual([c[0] for c in packs[0].calls], ["install"])
        self.assertIn("upgraded", out)
        config = json.loads((home / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["languages"]["python"]["plan"], "aggressive")

    def test_uninstall_removes_everything_and_keeps_data(self):
        home = fresh_home()
        (home / "data").mkdir()
        packs = [FakePack("python", True), FakePack("java", True), FakePack("javascript", True)]
        out = io.StringIO()
        with mock.patch.object(setup, "all_packs", lambda: packs), \
             mock.patch.object(setup, "powershell") as ps, \
             mock.patch.object(setup, "remove_password") as remove, \
             redirect_stdout(out):
            ps.return_value.returncode = 0
            setup.uninstall()
        self.assertTrue(all(p.calls == [("uninstall",)] for p in packs))
        names = " ".join(c.args[0] for c in ps.call_args_list)
        self.assertIn("'LearningTracker'", names)
        self.assertIn("'PythonLearningTracker'", names)
        remove.assert_called_once()
        self.assertTrue((home / "data").exists())


class PythonPackHookTests(unittest.TestCase):
    def setUp(self):
        self.target_dir = Path(tempfile.mkdtemp(prefix="usersite_"))
        self.pack = PythonPack()

    def test_install_writes_filled_template_and_uninstall_removes_it(self):
        data = Path(tempfile.mkdtemp(prefix="data_")) / "data"
        ok, msg = self.pack.install({"code_folder": r"C:\My Code"}, data, target_dir=self.target_dir)
        self.assertTrue(ok, msg)
        text = (self.target_dir / "usercustomize.py").read_text(encoding="utf-8")
        self.assertIn(LOGGER_MARKER, text)
        self.assertIn(str(data), text)
        self.assertIn(r"C:\My Code", text)
        self.assertNotIn("__DATA_DIR__", text)
        self.assertNotIn("__TRACKER_DIR__", text)
        self.assertTrue(self.pack.hook_installed(target_dir=self.target_dir))
        self.assertEqual(self.pack.uninstall(target_dir=self.target_dir), "Run logger removed")
        self.assertFalse((self.target_dir / "usercustomize.py").exists())
        self.assertFalse(self.pack.hook_installed(target_dir=self.target_dir))

    def test_foreign_usercustomize_is_never_touched(self):
        foreign = self.target_dir / "usercustomize.py"
        foreign.write_text("print('mine')\n", encoding="utf-8")
        ok, msg = self.pack.install({"code_folder": "x"}, self.target_dir / "d", target_dir=self.target_dir)
        self.assertFalse(ok)
        self.assertIn("isn't ours", msg)
        self.pack.uninstall(target_dir=self.target_dir)
        self.assertEqual(foreign.read_text(encoding="utf-8"), "print('mine')\n")
        self.assertFalse(self.pack.hook_installed(target_dir=self.target_dir))


if __name__ == "__main__":
    unittest.main()
