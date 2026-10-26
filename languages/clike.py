"""Comment- and string-aware tokenizer shared by the Java and JavaScript packs.

Topic rules are regexes over `Cleaned.code`, so anything that is not real code
(comments, string/char/regex contents, template text) must never survive into it.
"""
import re
from dataclasses import dataclass, field

_REGEX_PREV_CHARS = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_PREV_WORDS = {"return", "typeof", "case", "do", "else", "in"}
_CLOSERS = {")": "(", "]": "[", "}": "{"}
_TAIL_WORD = re.compile(r"[A-Za-z_$][\w$]*$")


@dataclass
class Cleaned:
    code: str = ""
    has_comment: bool = False
    has_template: bool = False
    strings: list = field(default_factory=list)
    syntax_ok: bool = True
    lines: int = 0


def _regex_allowed(out: list) -> bool:
    """Decide whether a '/' starts a regex literal, from the code emitted so far."""
    text = "".join(out).rstrip()
    if not text:
        return True
    if text.endswith("++") or text.endswith("--"):
        return False  # postfix increment: a following '/' is division
    if text[-1] in _REGEX_PREV_CHARS:
        return True
    m = _TAIL_WORD.search(text)
    return bool(m and m.group(0) in _REGEX_PREV_WORDS)


def _scan_quoted(src: str, i: int, quote: str):
    """Scan a quoted literal that starts after its opening quote.
    Returns (content, next_index), or (None, len) when it is unclosed."""
    n = len(src)
    start = i
    while i < n:
        c = src[i]
        if c == "\\":
            i += 2
            continue
        if c == quote:
            return src[start:i], i + 1
        if c == "\n":
            return None, n
        i += 1
    return None, n


def tokenize(source: str, language: str) -> Cleaned:
    js = language == "javascript"
    res = Cleaned()
    src = source
    n = len(src)
    out: list = []
    brackets: list = []   # "(", "[", "{" or "${" (a template expression)
    spans: list = []      # (start, end) comment spans in the original text
    ok = True
    i = 0
    in_template = False

    while i < n:
        if in_template:
            # Template text runs to the closing backtick or the next `${`.
            start = i
            state = "open"
            while i < n:
                c = src[i]
                if c == "\\":
                    i += 2
                elif c == "`":
                    state = "end"
                    break
                elif c == "$" and src.startswith("${", i):
                    state = "expr"
                    break
                else:
                    i += 1
            i = min(i, n)
            if state == "open":
                ok = False
                continue
            res.strings.append(src[start:i])
            if state == "end":
                in_template = False
                i += 1
            else:
                brackets.append("${")
                out.append(" ")
                in_template = False
                i += 2
            continue

        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            end = src.find("\n", i)
            end = n if end < 0 else end
            spans.append((i, end))
            res.has_comment = True
            out.append(" ")
            i = end
        elif c == "/" and nxt == "*":
            end = src.find("*/", i + 2)
            res.has_comment = True
            if end < 0:
                spans.append((i, n))
                ok = False
                i = n
            else:
                spans.append((i, end + 2))
                i = end + 2
            out.append(" ")
        elif not js and src.startswith('"""', i):
            end = i + 3
            while True:
                end = src.find('"""', end)
                if end < 0:
                    ok = False
                    i = n
                    break
                if src[end - 1] != "\\":
                    res.strings.append(src[i + 3:end])
                    i = end + 3
                    break
                end += 1
            out.append('""')
        elif c == '"' or c == "'":
            content, i2 = _scan_quoted(src, i + 1, c)
            if content is None:
                ok = False
            elif c == '"' or js:
                res.strings.append(content)  # Java chars are not strings
            out.append('""')
            i = i2
        elif js and c == "`":
            res.has_template = True
            out.append('""')
            in_template = True
            i += 1
        elif js and c == "/" and _regex_allowed(out):
            j = i + 1
            in_class = False
            closed = False
            while j < n:
                d = src[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "\n":
                    break
                if d == "[":
                    in_class = True
                elif d == "]":
                    in_class = False
                elif d == "/" and not in_class:
                    closed = True
                    break
                j += 1
            if closed:
                i = j + 1
            else:
                ok = False
                i = min(j, n)
            out.append('""')
        else:
            if c in "([{":
                brackets.append(c)
            elif c in ")]}":
                if c == "}" and brackets and brackets[-1] == "${":
                    # End of a template expression: back to template text.
                    brackets.pop()
                    out.append(" ")
                    in_template = True
                    i += 1
                    continue
                if not brackets or brackets[-1] != _CLOSERS[c]:
                    ok = False
                else:
                    brackets.pop()
            out.append(c)
            i += 1

    if brackets:
        ok = False
    res.code = "".join(out)
    res.syntax_ok = ok

    # Second pass: count lines that hold something besides blanks and comments.
    kept = list(src)
    for a, b in spans:
        for k in range(a, min(b, n)):
            if kept[k] != "\n":
                kept[k] = " "
    res.lines = sum(1 for ln in "".join(kept).splitlines() if ln.strip())
    return res
