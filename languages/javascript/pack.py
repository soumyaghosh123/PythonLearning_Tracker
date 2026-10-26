"""JavaScript pack: pattern-based analysis; .html files analyse their inline scripts."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import settings
from languages import envvars
from languages.base import LanguagePack
from languages.javascript.analyzer import analyze_js, extract_scripts
from languages.javascript.saved_scan import collect_saved

HOOK_PATH = Path(__file__).parent / "node_hook.js"
# Forward slashes: Node treats backslashes inside quoted NODE_OPTIONS as escapes.
HOOK_TOKEN = '--require "' + str(HOOK_PATH).replace("\\", "/") + '"'
HOOK_JSON = HOOK_PATH.with_name("hook.json")


class JavaScriptPack(LanguagePack):
    key = "javascript"
    label = "JavaScript"
    icon = "🟨"
    editor = "VS Code"
    extensions = {".js", ".mjs", ".cjs", ".html"}
    dir = Path(__file__).parent

    def analyze(self, source, path=None):
        if path and str(path).lower().endswith(".html"):
            source = extract_scripts(source)[0]
        return analyze_js(source, path)

    def install(self, lang_config, data_dir):
        _write_hook_json(lang_config, data_dir)
        if not shutil.which("node"):
            return False, "node not found: JavaScript will use saved-file tracking only"
        # A dangling --require breaks every Node program, so only set it once the hook works.
        ok, message = self.self_test(lang_config)
        if not ok:
            envvars.user_env_remove("NODE_OPTIONS", HOOK_TOKEN)
            return False, f"Node hook not installed: {message}"
        envvars.user_env_add("NODE_OPTIONS", HOOK_TOKEN)
        return True, "Node hook installed"

    def uninstall(self):
        removed = envvars.user_env_remove("NODE_OPTIONS", HOOK_TOKEN)
        return "Node hook removed" if removed else "Node hook was not set"

    def self_test(self, lang_config, data_dir=None):
        """Run a throwaway script through the hook (--require given explicitly, not via the env var)."""
        node = shutil.which("node")
        if not node:
            return False, "node not found"
        try:
            with tempfile.TemporaryDirectory(prefix="jstracker_selftest_") as tmp:
                code, data = Path(tmp) / "code", Path(tmp) / "data"
                code.mkdir()
                script = code / "selftest.js"
                script.write_text("console.log('ok')\n", encoding="utf-8")
                settings_file = Path(tmp) / "hook.json"
                _write_hook_json({"code_folder": str(code)}, data, settings_file)
                # Exactly what install will add to NODE_OPTIONS, so a token Node can't parse fails here.
                env = dict(os.environ, NODE_OPTIONS=HOOK_TOKEN, JSTRACKER_HOOK_JSON=str(settings_file))
                result = subprocess.run([node, str(script)], capture_output=True, text=True,
                                        timeout=30, env=env)
                if result.returncode != 0 or result.stderr.strip():
                    return False, (result.stderr.strip().splitlines() or [f"node exited with code {result.returncode}"])[0]
                runs = data / "javascript" / "runs.jsonl"
                lines = runs.read_text(encoding="utf-8").splitlines() if runs.exists() else []
                if len(lines) == 1 and json.loads(lines[0]).get("status") == "success":
                    return True, "Node hook works"
                return False, "the hook did not log the test run"
        except Exception as e:
            return False, f"self-test failed: {e}"

    def hook_installed(self):
        value = envvars.get_user_env("NODE_OPTIONS")
        try:
            return envvars._find(envvars._split(value), envvars._split(HOOK_TOKEN)) >= 0
        except ValueError:
            return False

    def collect(self, lang_config, data_dir, runs):
        return collect_saved(lang_config, data_dir, runs, hook_on=self.hook_installed())


def _write_hook_json(lang_config, data_dir, path=None):
    (path or HOOK_JSON).write_text(json.dumps({
        "data_dir": str(data_dir),
        "code_folder": lang_config["code_folder"],
        "tracker_dir": str(settings.TRACKER_DIR),
    }, indent=2), encoding="utf-8")


PACK = JavaScriptPack()
