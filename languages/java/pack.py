"""Java pack (stub; filled in later)."""

from pathlib import Path

from languages.base import LanguagePack


class JavaPack(LanguagePack):
    key = "java"
    label = "Java"
    icon = "☕"
    editor = "Eclipse"
    extensions = {".java"}
    dir = Path(__file__).parent


PACK = JavaPack()
