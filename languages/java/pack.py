"""Java pack: pattern-based analysis over comment- and string-free code."""

from pathlib import Path

from languages.base import LanguagePack
from languages.java.analyzer import analyze_java


class JavaPack(LanguagePack):
    key = "java"
    label = "Java"
    icon = "☕"
    editor = "Eclipse"
    extensions = {".java"}
    dir = Path(__file__).parent

    def analyze(self, source, path=None):
        return analyze_java(source, path)


PACK = JavaPack()
