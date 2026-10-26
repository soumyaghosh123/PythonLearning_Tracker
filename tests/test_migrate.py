import json
import unittest

from tests import helpers
from tests.helpers import fresh_home, write_runs


def read_jsonl(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def old_layout(home):
    from settings import save_json
    save_json(home / "config.json", {"learner_name": "S", "start_date": "2026-10-01",
                                     "plan": "aggressive", "code_folder": r"C:\Python", "email": {}, "alerts": {}})
    write_runs(home / "data" / "runs.jsonl", [{"time": "2026-10-02T10:00:00", "file": r"C:\Python\a.py",
                                               "status": "success", "error": None, "duration": 1, "sha": "abc"}])
    (home / "data" / "snapshots").mkdir(parents=True)
    (home / "data" / "snapshots" / "abc.py").write_text("print(1)")
    save_json(home / "data" / "email_state.json", {"last_progress_sent": "2026-10-20T08:00:00",
                                                   "alerts": {"4": "2026-10-19"}, "last_inactive_sent": None})


def snapshot(home):
    return {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}


class MigrateTests(unittest.TestCase):
    def test_old_layout_is_migrated(self):
        home = fresh_home()
        from settings import load_config, load_json
        old_layout(home)
        config = load_config()
        self.assertEqual(config["languages"]["python"],
                         {"enabled": True, "start_date": "2026-10-01", "plan": "aggressive", "code_folder": r"C:\Python"})
        self.assertNotIn("start_date", config)
        [entry] = read_jsonl(home / "data" / "python" / "runs.jsonl")
        self.assertEqual(entry["files"], [{"file": r"C:\Python\a.py", "sha": "abc"}])
        self.assertEqual(entry["source"], "hook")
        self.assertNotIn("sha", entry)
        self.assertTrue((home / "data" / "python" / "snapshots" / "abc.py").exists())
        self.assertFalse((home / "data" / "runs.jsonl").exists())
        state = load_json(home / "data" / "email_state.json")
        self.assertEqual(state["languages"]["python"]["alerts"], {"4": "2026-10-19"})
        self.assertIsNone(state["languages"]["python"]["last_inactive_sent"])
        self.assertNotIn("alerts", state)
        self.assertEqual(state["last_progress_sent"], "2026-10-20T08:00:00")

    def test_migration_is_idempotent(self):
        home = fresh_home()
        from settings import load_config
        import migrate
        old_layout(home)
        first = load_config()
        before = snapshot(home)
        self.assertEqual(load_config(), first)
        self.assertEqual(snapshot(home), before)
        self.assertFalse(migrate.migrate_if_needed())

    def test_leftover_old_runs_are_appended(self):
        home = fresh_home()
        from settings import load_config
        old_layout(home)
        load_config()
        write_runs(home / "data" / "runs.jsonl", [{"time": "2026-10-03T10:00:00", "file": "b.py",
                                                   "status": "error", "error": "X", "duration": 1, "sha": "def"}])
        load_config()
        entries = read_jsonl(home / "data" / "python" / "runs.jsonl")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["files"], [{"file": "b.py", "sha": "def"}])
        self.assertFalse((home / "data" / "runs.jsonl").exists())

    def test_defaults_fill_partial_language_block(self):
        home = fresh_home()
        from settings import load_config, save_json, enabled_languages
        save_json(home / "config.json", {"learner_name": "S", "languages": {"java": {"enabled": True}}})
        config = load_config()
        java = config["languages"]["java"]
        self.assertEqual(java["plan"], "standard")
        self.assertEqual(java["exclude_folders"], [])
        self.assertEqual(java["extra_workspaces"], [])
        self.assertFalse(config["languages"]["python"]["enabled"])
        self.assertEqual(enabled_languages(config), ["java"])

    def test_convert_entry_keeps_new_shape(self):
        import migrate
        new = {"files": [{"file": "a", "sha": "x"}], "source": "agent"}
        self.assertIs(migrate.convert_entry(new), new)

    def test_paths(self):
        home = fresh_home()
        import settings
        self.assertEqual(settings.runs_path("java"), home / "data" / "java" / "runs.jsonl")
        self.assertEqual(settings.snapshot_dir("java"), home / "data" / "java" / "snapshots")
        self.assertFalse(hasattr(settings, "load_curriculum"))
