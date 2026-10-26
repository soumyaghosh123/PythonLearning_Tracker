import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from languages import get_pack
from languages.javascript import pack as jspack
from languages.javascript.saved_scan import collect_saved

NODE = shutil.which("node")


def fwd(path):
    return str(path).replace("\\", "/")


class SavedScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jscap_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.code = self.tmp / "code"
        self.data = self.tmp / "data"
        self.code.mkdir()
        self.cfg = {"code_folder": str(self.code)}
        (self.code / "index.html").write_text(
            '<script src="app.js"></script><script>console.log(1)</script>', encoding="utf-8")
        (self.code / "app.js").write_text("console.log('app');\n", encoding="utf-8")
        (self.code / "other.js").write_text("console.log('other');\n", encoding="utf-8")

    def names(self, entries):
        return sorted(Path(e["file"]).name for e in entries)

    def test_html_and_linked_js_are_saved_unlinked_is_not(self):
        new = collect_saved(self.cfg, self.data, [], hook_on=True)
        self.assertEqual(self.names(new), ["app.js", "index.html"])
        self.assertEqual({e["status"] for e in new}, {"saved"})
        lines = (self.data / "runs.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        for e in new:
            self.assertTrue(list((self.data / "snapshots").glob(e["files"][0]["sha"] + ".*")))

    def test_seen_sha_not_recorded_twice(self):
        collect_saved(self.cfg, self.data, [], hook_on=True)
        self.assertEqual(collect_saved(self.cfg, self.data, [], hook_on=True), [])

    def test_sha_already_run_is_skipped(self):
        first = collect_saved(self.cfg, self.tmp / "d2", [], hook_on=True)
        app = next(e for e in first if e["file"].endswith("app.js"))
        runs = [{"files": app["files"]}]
        new = collect_saved(self.cfg, self.data, runs, hook_on=True)
        self.assertEqual(self.names(new), ["index.html"])

    def test_hook_off_saves_every_js(self):
        new = collect_saved(self.cfg, self.data, [], hook_on=False)
        self.assertEqual(self.names(new), ["app.js", "index.html", "other.js"])

    def test_syntax_error_logged_as_error(self):
        (self.code / "index.html").write_text("<script>if (x {</script>", encoding="utf-8")
        new = collect_saved(self.cfg, self.data, [], hook_on=True)
        html = next(e for e in new if e["file"].endswith("index.html"))
        self.assertEqual((html["status"], html["error"]), ("error", "SyntaxError"))

    def test_skips_node_modules(self):
        lib = self.code / "node_modules" / "lib"
        lib.mkdir(parents=True)
        (lib / "index.html").write_text("<p>x</p>", encoding="utf-8")
        new = collect_saved(self.cfg, self.data, [], hook_on=False)
        self.assertNotIn("node_modules", " ".join(e["file"] for e in new))

    def test_bom_file_and_remote_src(self):
        (self.code / "index.html").write_bytes(
            b'\xef\xbb\xbf<script src="https://x.test/a.js"></script><script src="/abs.js"></script>')
        new = collect_saved(self.cfg, self.data, [], hook_on=True)
        self.assertEqual(self.names(new), ["index.html"])
        self.assertEqual(new[0]["status"], "saved")


class PackTests(unittest.TestCase):
    def hook_json(self):
        return mock.patch.object(jspack, "HOOK_JSON", Path(tempfile.mkdtemp()) / "hook.json")

    def test_install_sets_env_only_after_self_test(self):
        pack = get_pack("javascript")
        cfg = {"code_folder": "C:\\x"}
        with mock.patch.object(jspack.envvars, "user_env_add") as add, \
                mock.patch.object(jspack.envvars, "user_env_remove") as rem, \
                mock.patch.object(jspack.shutil, "which", return_value="node"), \
                mock.patch.object(pack, "self_test", return_value=(False, "boom")), \
                self.hook_json():
            ok, _ = pack.install(cfg, Path("D"))
            self.assertFalse(ok)
            add.assert_not_called()
            rem.assert_called_once_with("NODE_OPTIONS", jspack.HOOK_TOKEN)
        with mock.patch.object(jspack.envvars, "user_env_add") as add, \
                mock.patch.object(jspack.envvars, "user_env_remove_matching"), \
                mock.patch.object(jspack.shutil, "which", return_value="node"), \
                mock.patch.object(pack, "self_test", return_value=(True, "ok")), \
                self.hook_json():
            self.assertEqual(pack.install(cfg, Path("D")), (True, "Node hook installed"))
            add.assert_called_once_with("NODE_OPTIONS", jspack.HOOK_TOKEN)

    def fake_registry(self, start):
        """Patch the pack's envvars so a dict stands in for the user variable (never the registry)."""
        store = {"NODE_OPTIONS": start}
        for p in (mock.patch.object(jspack.envvars, "get_user_env", lambda n: store.get(n)),
                  mock.patch.object(jspack.envvars, "set_user_env", lambda n, v: store.__setitem__(n, v)),
                  mock.patch.object(jspack.envvars, "_read_user_env", lambda n: (store.get(n), True))):
            p.start()
            self.addCleanup(p.stop)
        return store

    def install_ok(self, pack):
        with mock.patch.object(jspack.shutil, "which", return_value="node"), \
                mock.patch.object(pack, "self_test", return_value=(True, "ok")), self.hook_json():
            return pack.install({"code_folder": "C:\\x"}, Path("D"))

    def test_install_replaces_stale_tracker_token(self):
        store = self.fake_registry('--max-old-space-size=4096 --require "C:/old/tracker/languages/javascript/node_hook.js"')
        self.assertTrue(self.install_ok(get_pack("javascript"))[0])
        self.assertEqual(store["NODE_OPTIONS"], "--max-old-space-size=4096 " + jspack.HOOK_TOKEN)

    def test_install_removes_unquoted_stale_and_keeps_other_requires(self):
        store = self.fake_registry('--require C:/old/node_hook.js --require "C:/mine/other.js"')
        self.install_ok(get_pack("javascript"))
        self.assertEqual(store["NODE_OPTIONS"], '--require "C:/mine/other.js" ' + jspack.HOOK_TOKEN)

    def test_install_twice_keeps_one_token(self):
        store = self.fake_registry("--max-old-space-size=4096")
        pack = get_pack("javascript")
        self.install_ok(pack)
        self.install_ok(pack)
        self.assertEqual(store["NODE_OPTIONS"], "--max-old-space-size=4096 " + jspack.HOOK_TOKEN)

    def test_uninstall_removes_stale_tracker_token_too(self):
        store = self.fake_registry('-a --require "C:/old/x/node_hook.js" ' + jspack.HOOK_TOKEN + ' -b')
        self.assertEqual(get_pack("javascript").uninstall(), "Node hook removed")
        self.assertEqual(store["NODE_OPTIONS"], "-a -b")

    def test_install_without_node(self):
        pack = get_pack("javascript")
        with mock.patch.object(jspack.envvars, "user_env_add") as add, \
                mock.patch.object(jspack.shutil, "which", return_value=None), \
                self.hook_json():
            ok, msg = pack.install({"code_folder": "C:\\x"}, Path("D"))
        self.assertFalse(ok)
        self.assertIn("node not found", msg)
        add.assert_not_called()

    @unittest.skipUnless(NODE, "node not installed")
    def test_broken_token_fails_self_test_and_install_skips_env(self):
        pack = get_pack("javascript")
        broken = '--require "' + str(jspack.HOOK_PATH) + '"'   # backslashes inside quotes
        self.assertIn("\\", broken)
        with mock.patch.object(jspack, "HOOK_TOKEN", broken):
            ok, _ = pack.self_test({"code_folder": "C:/x"})
            self.assertFalse(ok)
            with mock.patch.object(jspack.envvars, "user_env_add") as add,                     mock.patch.object(jspack.envvars, "user_env_remove"),                     self.hook_json():
                self.assertFalse(pack.install({"code_folder": "C:/x"}, Path("D"))[0])
                add.assert_not_called()

    def test_uninstall_removes_token(self):
        with mock.patch.object(jspack.envvars, "user_env_remove_matching", return_value=True) as rem:
            get_pack("javascript").uninstall()
        self.assertEqual(rem.call_args.args[0], "NODE_OPTIONS")

    def test_hook_installed_reads_user_env(self):
        pack = get_pack("javascript")
        with mock.patch.object(jspack.envvars, "get_user_env",
                               return_value="--max-old-space-size=100 " + jspack.HOOK_TOKEN):
            self.assertTrue(pack.hook_installed())
        with mock.patch.object(jspack.envvars, "get_user_env", return_value=None):
            self.assertFalse(pack.hook_installed())

    def test_token_uses_forward_slashes(self):
        self.assertNotIn("\\", jspack.HOOK_TOKEN)

    def test_collect_passes_hook_state(self):
        pack = get_pack("javascript")
        with mock.patch.object(pack, "hook_installed", return_value=False), \
                mock.patch.object(jspack, "collect_saved", return_value=[]) as c:
            pack.collect({"code_folder": "x"}, Path("d"), [])
        self.assertFalse(c.call_args.kwargs["hook_on"])


@unittest.skipUnless(NODE, "node not installed")
class NodeHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jshook_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.code = self.tmp / "code"
        self.data = self.tmp / "data"
        self.code.mkdir()
        self.hook_dir = self.tmp / "my hook dir"   # a space, like a real install path
        self.hook_dir.mkdir()
        self.hook = self.hook_dir / "node_hook.js"
        shutil.copy(jspack.HOOK_PATH, self.hook)
        (self.hook_dir / "hook.json").write_text(json.dumps({
            "data_dir": str(self.data), "code_folder": str(self.code),
            "tracker_dir": str(helpers.TRACKER)}), encoding="utf-8")

    def runs(self):
        p = self.data / "javascript" / "runs.jsonl"
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]

    def run_node(self, script, node_options=None):
        env = {k: v for k, v in os.environ.items() if k != "NODE_OPTIONS"}
        if node_options:
            env["NODE_OPTIONS"] = node_options
            args = [NODE, str(script)]
        else:
            args = [NODE, "--require", str(self.hook), str(script)]
        return subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)

    def test_node_hook_end_to_end(self):
        files = {"ok.js": "console.log(1)", "boom.js": "throw new TypeError('x')",
                 "exit3.js": "process.exit(3)"}
        for name, src in files.items():
            (self.code / name).write_text(src, encoding="utf-8")
            self.run_node(self.code / name)
        outside = self.tmp / "outside.js"
        outside.write_text("console.log(1)", encoding="utf-8")
        self.run_node(outside)
        got = {Path(r["file"]).name: r for r in self.runs()}
        self.assertEqual(sorted(got), ["boom.js", "exit3.js", "ok.js"])
        self.assertEqual(got["ok.js"]["status"], "success")
        self.assertEqual((got["boom.js"]["status"], got["boom.js"]["error"]), ("error", "TypeError"))
        self.assertEqual((got["exit3.js"]["status"], got["exit3.js"]["error"]), ("error", "exit code 3"))
        for r in got.values():
            self.assertEqual(r["source"], "hook")
            sha = r["files"][0]["sha"]
            self.assertTrue((self.data / "javascript" / "snapshots" / f"{sha}.js").exists())

    def test_mjs_entry_is_logged(self):
        (self.code / "m.mjs").write_text("console.log(1)\n", encoding="utf-8")
        self.run_node(self.code / "m.mjs")
        self.assertEqual([r["status"] for r in self.runs()], ["success"])

    def test_silent_without_hook_json(self):
        (self.hook_dir / "hook.json").unlink()
        (self.code / "ok.js").write_text("console.log('hi')", encoding="utf-8")
        result = self.run_node(self.code / "ok.js")
        self.assertEqual((result.returncode, result.stdout.strip(), result.stderr), (0, "hi", ""))
        self.assertEqual(self.runs(), [])

    def test_production_token_shape_loads_with_space_in_path(self):
        # HOOK_TOKEN's exact format, built for a hook copy in a folder whose path has a space.
        token = jspack.HOOK_TOKEN.replace(fwd(jspack.HOOK_PATH), fwd(self.hook))
        self.assertIn("my hook dir", token)
        (self.code / "ok.js").write_text("console.log('hi')", encoding="utf-8")
        result = self.run_node(self.code / "ok.js", node_options=token)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.runs()), 1)

    def test_self_test_passes_with_real_token(self):
        ok, msg = get_pack("javascript").self_test({"code_folder": str(self.code)})
        self.assertTrue(ok, msg)

    def test_self_test_never_touches_hook_json(self):
        # Temp copy of the pack dir; its hook.json must stay as found (or absent).
        copy = self.tmp / "pack copy"
        copy.mkdir()
        shutil.copy(jspack.HOOK_PATH, copy / "node_hook.js")
        hook = copy / "node_hook.js"
        token = '--require "' + fwd(hook) + '"'
        pack = get_pack("javascript")
        with mock.patch.object(jspack, "HOOK_PATH", hook), mock.patch.object(jspack, "HOOK_TOKEN", token),                 mock.patch.object(jspack, "HOOK_JSON", self.tmp / "no_such_dir" / "hook.json"):
            ok, msg = pack.self_test({"code_folder": str(self.code)})
            self.assertTrue(ok, msg)
            self.assertFalse((copy / "hook.json").exists())
            (copy / "hook.json").write_bytes(b'{"keep": 1}')
            self.assertTrue(pack.self_test({"code_folder": str(self.code)})[0])
            self.assertEqual((copy / "hook.json").read_bytes(), b'{"keep": 1}')

    def test_sigint_without_handler_is_stopped(self):
        (self.code / "s.js").write_text(
            'setInterval(() => {}, 1000); setTimeout(() => process.emit("SIGINT"), 50);', encoding="utf-8")
        result = self.run_node(self.code / "s.js")
        self.assertEqual(result.returncode, 130)
        self.assertEqual([r["status"] for r in self.runs()], ["stopped"])

    def test_sigint_with_learner_handler_is_not_forced(self):
        (self.code / "g.js").write_text(
            'process.on("SIGINT", () => { console.log("graceful"); process.exit(0); });'
            'setInterval(() => {}, 1000); setTimeout(() => process.emit("SIGINT"), 50);', encoding="utf-8")
        result = self.run_node(self.code / "g.js")
        self.assertIn("graceful", result.stdout)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(self.runs()), 1)


if __name__ == "__main__":
    unittest.main()
