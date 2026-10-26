"""Registry of language packs (python, java, javascript)."""

from pathlib import Path

from languages.java.pack import PACK as _JAVA
from languages.javascript.pack import PACK as _JAVASCRIPT
from languages.python.pack import PACK as _PYTHON

_PACKS = [_PYTHON, _JAVA, _JAVASCRIPT]


def all_packs():
    return list(_PACKS)


def get_pack(key):
    for pack in _PACKS:
        if pack.key == key:
            return pack
    raise KeyError(key)


def pack_for_path(path):
    ext = Path(str(path)).suffix.lower()
    for pack in _PACKS:
        if ext in pack.extensions:
            return pack
    return None
