"""Python pack: analysis via the built-in ast module."""

from pathlib import Path

from languages.base import LanguagePack
from languages.python.analyzer import analyze_source


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


PACK = PythonPack()
