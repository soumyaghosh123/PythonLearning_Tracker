"""JavaScript pack (stub; filled in later)."""

from pathlib import Path

from languages.base import LanguagePack


class JavaScriptPack(LanguagePack):
    key = "javascript"
    label = "JavaScript"
    icon = "🟨"
    editor = "VS Code"
    extensions = {".js", ".mjs", ".cjs", ".html"}
    dir = Path(__file__).parent


PACK = JavaScriptPack()
