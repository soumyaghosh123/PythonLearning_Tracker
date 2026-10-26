"""Python pack: analysis via the built-in ast module."""

import site
from pathlib import Path

import settings
from languages.base import LanguagePack
from languages.python.analyzer import analyze_source


LOGGER_MARKER = "Python Learning Tracker: run logger"


def _target(target_dir=None):
    """usercustomize.py in the user site-packages (the folder is injectable for tests)."""
    return Path(target_dir or site.getusersitepackages()) / "usercustomize.py"


def _is_ours(target):
    return LOGGER_MARKER in target.read_text(encoding="utf-8", errors="ignore")


class PythonPack(LanguagePack):
    key = "python"
    label = "Python"
    icon = "🐍"
    editor = "VS Code"
    extensions = {".py"}
    dir = Path(__file__).parent

    def analyze(self, source, path=None):
        result = analyze_source(source, path)
        result["syntax_ok"] = result["parsed"]
        return result

    def install(self, lang_config, data_dir, target_dir=None):
        target = _target(target_dir)
        # Never overwrite a usercustomize.py that someone else wrote.
        if target.exists() and not _is_ours(target):
            return False, f"{target} already exists and isn't ours, so the run logger was NOT installed"
        try:
            code = (self.dir / "run_logger.py").read_text(encoding="utf-8")
            code = (code.replace("__DATA_DIR__", str(data_dir))
                        .replace("__CODE_FOLDER__", lang_config["code_folder"])
                        .replace("__TRACKER_DIR__", str(settings.TRACKER_DIR)))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(code, encoding="utf-8")
            Path(data_dir).mkdir(parents=True, exist_ok=True)
        except OSError as error:
            return False, f"Run logger not installed: {error}"
        return True, f"Run logger installed ({target})"

    def uninstall(self, target_dir=None):
        target = _target(target_dir)
        if target.exists() and _is_ours(target):
            target.unlink()
            return "Run logger removed"
        return "Run logger was not installed"

    def hook_installed(self, target_dir=None):
        target = _target(target_dir)
        return target.exists() and _is_ours(target)


PACK = PythonPack()
