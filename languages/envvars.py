r"""Add/remove the tracker's part of per-user environment variables (HKCU\Environment).

Hooks live in values such as NODE_OPTIONS and JAVA_TOOL_OPTIONS that the learner
may already use, so we only ever add or remove our own whitespace-separated token.
"""

import ctypes


def _split(value):
    """Split on spaces outside double quotes; quotes and backslashes are kept as-is."""
    tokens, current, in_quotes = [], [], False
    for ch in value or "":
        if ch == '"':
            in_quotes = not in_quotes
            current.append(ch)
        elif ch.isspace() and not in_quotes:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    if in_quotes:
        raise ValueError("unterminated quote")
    return tokens


def _find(tokens, want):
    """Index of the first run of tokens equal to `want` (a token may be '--flag "quoted path"')."""
    n = len(want)
    for i in range(len(tokens) - n + 1):
        if tokens[i:i + n] == want:
            return i
    return -1


def add_token(value, token):
    try:
        tokens = _split(value)
    except ValueError:
        return value  # never guess inside a user's broken value
    if _find(tokens, _split(token)) >= 0:
        return value
    return " ".join(tokens + [token])


def remove_token(value, token):
    try:
        tokens, want = _split(value), _split(token)
    except ValueError:
        return value or ""
    if _find(tokens, want) < 0:
        return value or ""  # nothing of ours: leave the user's spacing alone
    while want:
        i = _find(tokens, want)
        if i < 0:
            break
        del tokens[i:i + len(want)]
    return " ".join(tokens)


def get_user_env(name):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def _broadcast_change():
    # Lets new processes see the change; a failure must never break setup.
    try:
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 5000, None)
    except Exception:
        pass


def set_user_env(name, value):
    """Write (or, for an empty value, delete) a user variable and broadcast the change."""
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        if not value:
            try:
                winreg.DeleteValue(key, name)
            except OSError:
                pass
        else:
            # Keep an existing value's type; new values are REG_SZ so %...% is never expanded.
            try:
                value_type = winreg.QueryValueEx(key, name)[1]
            except OSError:
                value_type = winreg.REG_SZ
            winreg.SetValueEx(key, name, 0, value_type, value)
    _broadcast_change()


def user_env_add(name, token):
    current = get_user_env(name)
    new = add_token(current, token)
    if new == (current or ""):
        return False
    set_user_env(name, new)
    return True


def user_env_remove(name, token):
    current = get_user_env(name)
    if current is None:
        return False
    new = remove_token(current, token)
    if new == current:
        return False
    set_user_env(name, new)
    return True
