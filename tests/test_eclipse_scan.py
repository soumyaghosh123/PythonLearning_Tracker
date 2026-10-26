import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from languages.java import eclipse_scan
from languages.java import pack as javapack
from languages.java.eclipse_scan import (is_excluded_factory, project_dirs, prune_excluded, recent_workspaces,
                                         scan_workspaces, src_and_output)

REAL_EXCLUDES = javapack.BUILTIN_EXCLUDES
FIXTURES = Path(__file__).parent / "fixtures" / "java"


def sha16(raw):
    return hashlib.sha256(raw).hexdigest()[:16]


class EclipseScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eclscan_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.ws = self.tmp / "ws"
        shutil.copytree(FIXTURES / "eclipse_ws", self.ws)
        self.data = self.tmp / "data" / "java"
        self.data.mkdir(parents=True)
        # The temp folder lives under AppData, which is a built-in exclusion.
        patch = mock.patch.object(javapack, "BUILTIN_EXCLUDES", ("node_modules",))
        patch.start()
        self.addCleanup(patch.stop)

    def runs_lines(self):
        path = self.data / "runs.jsonl"
        return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def test_reads_recent_workspaces(self):
        home = self.tmp / "home"
        ws1, ws2 = self.tmp / "ws1", self.tmp / "ws2"
        ws1.mkdir()
        ws2.mkdir()
        settings = home / ".eclipse" / "123_x" / "configuration" / ".settings"
        settings.mkdir(parents=True)
        value = "\\n".join(str(p).replace("\\", "\\\\").replace(":", "\\:") for p in (ws1, ws2, self.tmp / "gone"))
        (settings / "org.eclipse.ui.ide.prefs").write_text(f"RECENT_WORKSPACES={value}\n", encoding="utf-8")
        # the same workspace again, from an install folder and from the Eclipse Installer's default place
        inst = self.tmp / "inst"
        (inst / "configuration" / ".settings").mkdir(parents=True)
        shutil.copy(settings / "org.eclipse.ui.ide.prefs", inst / "configuration" / ".settings")
        other = home / "eclipse" / "java-2026" / "eclipse" / "configuration" / ".settings"
        other.mkdir(parents=True)
        shutil.copy(settings / "org.eclipse.ui.ide.prefs", other)
        self.assertEqual(recent_workspaces(home=home, installs=[inst]), [ws1, ws2])

    def test_fixture_prefs_unescape(self):
        text = (FIXTURES / "org.eclipse.ui.ide.prefs").read_text(encoding="utf-8")
        self.assertEqual(eclipse_scan.parse_recent(text), [r"C:\Users\x\ws1", r"C:\Users\x\ws2"])

    def test_project_dirs_skip_metadata(self):
        hidden = self.ws / ".metadata" / ".plugins" / "p"
        hidden.mkdir(parents=True)
        (hidden / ".classpath").write_text("<classpath/>", encoding="utf-8")
        self.assertEqual(project_dirs(self.ws), [self.ws / "Proj"])

    def test_compiled_and_compile_error(self):
        new = scan_workspaces([self.ws], self.data, [], lambda p: False)
        by = {Path(e["file"]).name: e for e in new}
        self.assertEqual(by["Main.java"]["status"], "compiled")
        self.assertEqual((by["Broken.java"]["status"], by["Broken.java"]["error_count"]), ("compile_error", 2))
        self.assertIsNone(by["Main.java"]["error_count"])
        self.assertEqual(by["Main.java"]["source"], "eclipse")
        raw = (self.ws / "Proj" / "src" / "app" / "Main.java").read_bytes()
        self.assertEqual(by["Main.java"]["files"][0]["sha"], sha16(raw))
        self.assertEqual((self.data / "snapshots" / (sha16(raw) + ".java")).read_bytes(), raw)
        self.assertEqual(len(self.runs_lines()), 2)

    def test_second_scan_records_nothing_new(self):
        scan_workspaces([self.ws], self.data, [], lambda p: False)
        self.assertEqual(scan_workspaces([self.ws], self.data, [], lambda p: False), [])
        self.assertEqual(len(self.runs_lines()), 2)

    def test_sha_already_logged_by_agent_is_skipped(self):
        raw = (self.ws / "Proj" / "src" / "app" / "Main.java").read_bytes()
        runs = [{"file": "x", "source": "agent", "files": [{"file": "x", "sha": sha16(raw)}]}]
        new = scan_workspaces([self.ws], self.data, runs, lambda p: False)
        self.assertEqual([Path(e["file"]).name for e in new], ["Broken.java"])

    def test_old_class_file_is_ignored_after_last_scan(self):
        (self.data / "eclipse_seen.json").write_text(json.dumps({"last_scan": 4102444800, "shas": []}))
        self.assertEqual(scan_workspaces([self.ws], self.data, [], lambda p: False), [])

    def test_source_without_class_is_ignored(self):
        (self.ws / "Proj" / "bin" / "app" / "Main.class").unlink()
        new = scan_workspaces([self.ws], self.data, [], lambda p: False)
        self.assertEqual([Path(e["file"]).name for e in new], ["Broken.java"])

    def test_custom_classpath_folders(self):
        proj = self.tmp / "ws2" / "Custom"
        (proj / "source").mkdir(parents=True)
        (proj / "classes").mkdir()
        (proj / ".classpath").write_text(
            '<classpath><classpathentry kind="src" path="source"/>'
            '<classpathentry kind="src" path="/Other"/>'
            '<classpathentry combineaccessrules="false" kind="src" path="/Dep"/>'
            '<classpathentry kind="output" path="classes"/></classpath>', encoding="utf-8")
        self.assertEqual(src_and_output(proj), [(proj / "source", proj / "classes")])
        (proj / "source" / "A.java").write_text("class A {}", encoding="utf-8")
        (proj / "classes" / "A.class").write_bytes(b"\xca\xfe")
        new = scan_workspaces([self.tmp / "ws2"], self.data, [], lambda p: False)
        self.assertEqual([Path(e["file"]).name for e in new], ["A.java"])

    def _project(self, name, entries, built):
        proj = self.tmp / "ws3" / name
        proj.mkdir(parents=True)
        (proj / ".classpath").write_text(f"<classpath>{entries}</classpath>", encoding="utf-8")
        for src, out in built:
            (proj / src).mkdir(parents=True)
            (proj / out).mkdir(parents=True)
            (proj / src / "A.java").write_text(f"class A {{ /* {src} */ }}", encoding="utf-8")
            (proj / out / "A.class").write_bytes(bytes([0xCA, 0xFE]))
        return proj

    def test_buildship_per_source_output(self):
        entries = ('<classpathentry kind="src" output="bin/main" path="src/main/java"/>'
                   '<classpathentry kind="src" output="bin/test" path="src/test/java"/>'
                   '<classpathentry kind="output" path="bin/default"/>')
        proj = self._project("G", entries, [("src/main/java", "bin/main"), ("src/test/java", "bin/test")])
        self.assertEqual(src_and_output(proj), [(proj / "src/main/java", proj / "bin/main"),
                                                (proj / "src/test/java", proj / "bin/test")])
        new = scan_workspaces([self.tmp / "ws3"], self.data, [], lambda p: False)
        self.assertEqual(len(new), 2)

    def test_m2e_per_source_output(self):
        entries = ('<classpathentry kind="src" output="target/classes" path="src/main/java"/>'
                   '<classpathentry kind="src" output="target/test-classes" path="src/test/java"/>'
                   '<classpathentry kind="output" path="target/classes"/>')
        self._project("M", entries, [("src/main/java", "target/classes"), ("src/test/java", "target/test-classes")])
        new = scan_workspaces([self.tmp / "ws3"], self.data, [], lambda p: False)
        self.assertEqual(len(new), 2)

    def test_source_without_own_output_uses_project_output(self):
        entries = ('<classpathentry kind="src" path="src"/><classpathentry kind="src" output="bin/t" path="tst"/>'
                   '<classpathentry kind="output" path="out"/>')
        proj = self._project("P", entries, [("src", "out"), ("tst", "bin/t")])
        self.assertEqual(src_and_output(proj), [(proj / "src", proj / "out"), (proj / "tst", proj / "bin/t")])

    def test_default_classpath_folders(self):
        proj = self.tmp / "p"
        proj.mkdir()
        (proj / ".classpath").write_text("not xml", encoding="utf-8")
        self.assertEqual(src_and_output(proj), [(proj / "src", proj / "bin")])

    def test_skips_metadata(self):
        plug = self.ws / ".metadata" / ".plugins" / "p"
        (plug / "src").mkdir(parents=True)
        (plug / "bin").mkdir()
        (plug / ".classpath").write_text("<classpath/>", encoding="utf-8")
        (plug / "src" / "X.java").write_text("class X {}", encoding="utf-8")
        (plug / "bin" / "X.class").write_bytes(b"\xca\xfe")
        new = scan_workspaces([self.ws], self.data, [], lambda p: False)
        self.assertNotIn("X.java", [Path(e["file"]).name for e in new])
        self.assertEqual(len(new), 2)

    def test_skips_nested_git_and_node_modules_in_sources(self):
        for skip in (".git", "node_modules"):
            d = self.ws / "Proj" / "src" / skip
            d.mkdir()
            (d / "Y.java").write_text("class Y {}", encoding="utf-8")
            (self.ws / "Proj" / "bin" / skip).mkdir()
            (self.ws / "Proj" / "bin" / skip / "Y.class").write_bytes(b"\xca\xfe")
        new = scan_workspaces([self.ws], self.data, [], lambda p: False)
        self.assertEqual(sorted(Path(e["file"]).name for e in new), ["Broken.java", "Main.java"])

    def test_excluded_files_are_not_recorded(self):
        new = scan_workspaces([self.ws], self.data, [], lambda p: p.name == "Broken.java")
        self.assertEqual([Path(e["file"]).name for e in new], ["Main.java"])

    def test_exclusion_rule_matches_agent(self):
        with mock.patch.object(eclipse_scan.settings, "TRACKER_DIR", Path(r"C:\Python\tracker")), \
                mock.patch.object(javapack, "BUILTIN_EXCLUDES", REAL_EXCLUDES):
            ex = is_excluded_factory({"exclude_folders": [r"C:\work", "D:/other/"]})
            self.assertTrue(ex(Path(r"C:\Users\x\AppData\Local\a.java")))
            self.assertTrue(ex(Path(r"c:\users\x\APPDATA\a.java")))
            self.assertTrue(ex(Path(r"C:\Program Files (x86)\a\A.java")))
            self.assertTrue(ex(Path(r"C:\proj\node_modules\a\A.java")))
            self.assertFalse(ex(Path(r"C:\proj\AppDataX\A.java")))
            self.assertTrue(ex(Path(r"C:\Work\A.java")))
            self.assertTrue(ex(Path(r"C:\work\sub\A.java")))
            self.assertFalse(ex(Path(r"C:\workshop\A.java")))
            self.assertTrue(ex(Path(r"D:\other\A.java")))
            self.assertTrue(ex(Path(r"C:\Python\tracker\tests\A.java")))
            self.assertFalse(ex(Path(r"C:\Python\mine\A.java")))

    def entry(self, file, sha):
        return {"time": "2026-10-01T10:00:00", "file": file, "status": "compiled", "error": None,
                "error_count": None, "duration": 0, "source": "eclipse", "files": [{"file": file, "sha": sha}]}

    def test_prune_when_exclude_changes(self):
        work, keep = self.tmp / "work" / "A.java", self.tmp / "keep" / "B.java"
        snaps = self.data / "snapshots"
        snaps.mkdir()
        (snaps / "aaaa.java").write_text("a")
        (snaps / "bbbb.java").write_text("b")
        helpers.write_runs(self.data / "runs.jsonl", [self.entry(str(work), "aaaa"), self.entry(str(keep), "bbbb")])
        cfg = {"code_folder": str(self.tmp / "nowhere"), "exclude_folders": [str(self.tmp / "work")]}
        with mock.patch.object(javapack, "AGENT_DIR", self.tmp / "agent"), \
                mock.patch.object(eclipse_scan, "recent_workspaces", return_value=[]):
            javapack.PACK.collect(cfg, self.data, [])
        self.assertEqual([e["file"] for e in self.runs_lines()], [str(keep)])
        self.assertFalse((snaps / "aaaa.java").exists())
        self.assertTrue((snaps / "bbbb.java").exists())
        # unchanged list: nothing pruned the second time, even for an entry added since
        helpers.write_runs(self.data / "runs.jsonl", [self.entry(str(work), "aaaa")])
        with mock.patch.object(eclipse_scan, "recent_workspaces", return_value=[]):
            javapack.PACK.collect(cfg, self.data, [])
        self.assertEqual(len(self.runs_lines()), 1)

    def test_prune_keeps_snapshot_still_referenced(self):
        work, keep = self.tmp / "work" / "A.java", self.tmp / "keep" / "A.java"
        snaps = self.data / "snapshots"
        snaps.mkdir()
        (snaps / "aaaa.java").write_text("a")
        helpers.write_runs(self.data / "runs.jsonl", [self.entry(str(work), "aaaa"), self.entry(str(keep), "aaaa")])
        removed = prune_excluded(self.data, lambda p: "work" in p.parts)
        self.assertEqual(removed, 1)
        self.assertTrue((snaps / "aaaa.java").exists())

    def test_collect_rewrites_live_properties_when_exclusions_change(self):
        agent = self.tmp / "agent"
        agent.mkdir()
        props = agent / "agent.properties"
        props.write_text("old", encoding="utf-8")
        cfg = {"code_folder": str(self.ws), "exclude_folders": [r"C:\work"]}
        with mock.patch.object(javapack, "AGENT_DIR", agent), \
                mock.patch.object(eclipse_scan, "recent_workspaces", return_value=[]):
            javapack.PACK.collect(cfg, self.data, [])
            text = props.read_text(encoding="utf-8")
            self.assertIn("C:\\\\work", text)
            self.assertIn("node_modules", text)
            props.write_text("again", encoding="utf-8")
            javapack.PACK.collect(cfg, self.data, [])
            self.assertEqual(props.read_text(encoding="utf-8"), "again")  # unchanged list: left alone

    def test_collect_scans_code_folder_and_extra_workspaces_once(self):
        extra = self.tmp / "extra"
        shutil.copytree(FIXTURES / "eclipse_ws", extra)
        cfg = {"code_folder": str(self.ws), "extra_workspaces": [str(self.ws), str(extra)], "exclude_folders": []}
        with mock.patch.object(javapack, "AGENT_DIR", self.tmp / "agent"), \
                mock.patch.object(eclipse_scan, "recent_workspaces", return_value=[self.ws]):
            new = javapack.PACK.collect(cfg, self.data, [])
        # identical sources in the extra workspace share shas, so only the first copy counts
        self.assertEqual(len(new), 2)

    def test_extra_report_groups_by_source_root(self):
        runs = [
            {"file": r"C:\ws\Proj\src\app\Main.java", "dt": __import__("datetime").datetime(2026, 10, 2, 9),
             "files": [{"file": r"C:\ws\Proj\src\app\Main.java", "sha": "a"},
                       {"file": r"C:\ws\Proj\src\app\Util.java", "sha": "b"}]},
            {"file": r"C:\ws\Proj\src\app\Main.java", "dt": __import__("datetime").datetime(2026, 10, 3, 9),
             "files": [{"file": r"C:\ws\Proj\src\app\Main.java", "sha": "c"}]},
            {"file": r"C:\loose\Hello.java", "dt": __import__("datetime").datetime(2026, 10, 5, 9), "files": []},
        ]
        self.assertEqual(javapack.PACK.extra_report(runs)["java_folders"], [
            {"folder": r"C:\loose", "files": 1, "last_seen": "2026-10-05"},
            {"folder": r"C:\ws\Proj", "files": 2, "last_seen": "2026-10-03"},
        ])

    def test_extra_report_default_is_empty(self):
        from languages.base import LanguagePack
        self.assertEqual(LanguagePack().extra_report([]), {})


if __name__ == "__main__":
    unittest.main()
