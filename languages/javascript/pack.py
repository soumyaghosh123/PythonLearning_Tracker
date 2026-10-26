"""JavaScript pack: pattern-based analysis; .html files analyse their inline scripts."""

from pathlib import Path

from languages.base import LanguagePack
from languages.javascript.analyzer import analyze_js, extract_scripts


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


PACK = JavaScriptPack()
