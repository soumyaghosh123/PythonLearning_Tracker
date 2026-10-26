"""The shared shape of a language pack.

A pack knows how to analyse one language's source code, load its course
(curriculum.json) and, optionally, install a run hook and collect runs.
"""

import json
from pathlib import Path


def complexity_level(score):
    if score <= 10:
        return "Beginner"
    if score <= 30:
        return "Intermediate"
    return "Advanced"


class LanguagePack:
    key = ""
    label = ""
    icon = ""
    editor = ""
    extensions = set()
    dir = Path(__file__).parent

    def curriculum(self):
        # Cached per instance so the JSON is read once.
        if not hasattr(self, "_curriculum"):
            self._curriculum = json.loads((self.dir / "curriculum.json").read_text(encoding="utf-8"))
        return self._curriculum

    def analyze(self, source, path=None):
        raise NotImplementedError

    def install(self, lang_config, data_dir):
        return False, "not supported"

    def uninstall(self):
        return "nothing to remove"

    def self_test(self, lang_config):
        return False, "not supported"

    def collect(self, lang_config, data_dir, runs):
        return []

    def hook_installed(self):
        return False
