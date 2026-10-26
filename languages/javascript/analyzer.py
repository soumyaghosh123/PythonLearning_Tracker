"""Pattern-based JavaScript analyser: topic rules and complexity score over cleaned code.

Source goes through the shared tokenizer first, so keywords inside comments,
strings, template text and regex literals never count toward a topic. Module
names (`require("x")`, `import ... from "x"`) are the one thing read from the
original string contents.
"""
import re
from dataclasses import dataclass, field, fields

from languages.base import complexity_level
from languages.clike import Cleaned, tokenize

_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.I | re.S)
_SRC = re.compile(r"""\bsrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)

_BUILTIN_MODULES = {"fs", "path", "http", "https", "os", "url", "util", "events", "assert",
                    "child_process", "crypto", "readline", "stream", "test"}
_MODULE_SPEC = [
    re.compile(r"""\brequire\s*\(\s*(['"])([^'"\n]+)\1\s*\)"""),
    re.compile(r"""\bfrom\s*(['"])([^'"\n]+)\1"""),
    re.compile(r"""\bimport\s*(['"])([^'"\n]+)\1"""),
    re.compile(r"""\bimport\s*\(\s*(['"])([^'"\n]+)\1\s*\)"""),
]
_MODULE_IN_CODE = re.compile(r'\brequire\s*\(\s*""|\bfrom\s*""|\bimport\s*\(?\s*""')


@dataclass
class JsCleaned(Cleaned):
    """Cleaned code plus the module names the file loads."""
    modules: set = field(default_factory=set)


def extract_scripts(html):
    """(inline <script> bodies joined by newlines, list of src values)."""
    bodies, srcs = [], []
    for attrs, body in _SCRIPT.findall(html):
        m = _SRC.search(attrs)
        if m:
            srcs.append(m.group(1) or m.group(2) or m.group(3) or "")
        bodies.append(body)
    return "\n".join(bodies), srcs


def _modules(source, cleaned):
    """Module specifiers that are real string literals (so not commented-out
    ones) in a real require/import (so not a lone string with the same text)."""
    if not _MODULE_IN_CODE.search(cleaned.code):
        return set()
    literal = set(cleaned.strings)
    found = set()
    for rx in _MODULE_SPEC:
        found.update(m.group(2) for m in rx.finditer(source) if m.group(2) in literal)
    return found


def _body(code, open_idx):
    """Text between the `{` at open_idx and its matching `}`."""
    depth = 0
    for i in range(open_idx, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[open_idx + 1:i]
    return code[open_idx + 1:]


def _top_level(text):
    """text with the inside of every nested {...} blanked, keeping the braces."""
    out, depth = [], 0
    for ch in text:
        if ch == "{":
            depth += 1
            if depth == 1:
                out.append(ch)
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append(ch)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


_PARAMS = r"(?:[^()]|\([^()]*\))*"
_CLASS_DECL = re.compile(r"\bclass\s+(?!extends\b)([A-Za-z_$][\w$]*)")
_METHOD_HEAD = re.compile(
    r"(?:^|[;}\s])(?:static\s+)?(?:async\s+)?(?:[gs]et\s+)?\*?\s*#?[\w$]+\s*\(" + _PARAMS + r"\)\s*\{\}")


def _class_methods(code):
    """Number of method declarations directly inside class bodies."""
    total = 0
    for m in _CLASS_DECL.finditer(code):
        brace = code.find("{", m.end())
        if brace >= 0:
            total += len(_METHOD_HEAD.findall(_top_level(_body(code, brace))))
    return total


_FUNC_BLOCK = re.compile(r"\bfunction\b[^{;]*\{|=>\s*\{")
_CLOSURE = re.compile(r"return\s+(?:async\s+)?(?:function\b|\(?[\w,\s]*\)?\s*=>)")


def _has_scope(c):
    """let/const declared inside a function body, plus a function returning a function."""
    scoped = any(re.search(r"\b(?:let|const)\s+[\w$\[{]", _body(c.code, m.end() - 1))
                 for m in _FUNC_BLOCK.finditer(c.code))
    return scoped and bool(_CLOSURE.search(c.code))


def _strict_ternary(c):
    return bool(re.search(r"===|!==", c.code)) and bool(re.search(r"(?<!\?)\?(?![.?])[^?:]+:", c.code))


_DEFAULT_PARAM = [
    re.compile(r"\bfunction\b\s*\*?\s*[\w$]*\s*\((?:[^()=]|\([^()]*\))*[\w$\]}]\s*=(?![=>])"),
    re.compile(r"\((?:[^()=]|\([^()]*\))*[\w$\]}]\s*=(?![=>])(?:[^()]|\([^()]*\))*\)\s*=>"),
    re.compile(r"(?<![\w$.])(?!(?:if|for|while|switch|catch|with|function|return)\b)[\w$]+\s*\("
               r"(?:[^()=]|\([^()]*\))*[\w$\]}]\s*=(?![=>])(?:[^()]|\([^()]*\))*\)\s*\{"),
]


def _has_default_param(c):
    return any(p.search(c.code) for p in _DEFAULT_PARAM)


def _forms(c):
    return (bool(re.search(r"\.value\b", c.code)) and bool(re.search(r'addEventListener\s*\(\s*""', c.code))
            and bool({"submit", "input"} & set(c.strings)))


def _npm_package(c):
    for name in c.modules:
        if name.startswith((".", "/", "node:")):
            continue
        if name.split("/")[0] not in _BUILTIN_MODULES:
            return True
    return False


def _uses_module(c, *names):
    wanted = set(names) | {"node:" + n for n in names}
    return any(m in wanted or m.split("/")[0] in wanted or m.removeprefix("node:").split("/")[0] in wanted
               for m in c.modules)


_FS_CALL = (r"\b(?:readFile|writeFile|appendFile|readdir|existsSync|createReadStream|createWriteStream|"
            r"mkdir|unlink|stat|copyFile|rename)(?:Sync)?\s*\(")
_TEST_CALL = r"(?<![\w$.])(?:test|it|describe)\s*\("


def _fs_files(c):
    return _uses_module(c, "fs") and bool(re.search(_FS_CALL, c.code))


def _node_test(c):
    if not re.search(_TEST_CALL, c.code):
        return False
    return "node:test" in c.modules or _uses_module(c, "assert")


def _http_server(c):
    if _uses_module(c, "http", "https") and re.search(r"\.createServer\s*\(", c.code):
        return True
    return _uses_module(c, "express") and bool(re.search(r"\.listen\s*\(", c.code))


def _rx(*patterns):
    return [re.compile(p, re.M) for p in patterns]


# One entry per topic id, in course order. A list of regexes matches when any
# regex matches the cleaned code; a callable gets the whole JsCleaned result.
TOPIC_RULES = {
    "console_log": _rx(r"\bconsole\s*\.\s*(?:log|info|warn|error|table)\s*\("),
    "let_const": _rx(r"\b(?:let|const)\s+[\w$\[{]"),
    "numbers_strings": _rx(r"\b(?:let|const|var)\s+[\w$]+\s*=\s*(?:-?\d|\"\")",
                           r"\.\s*(?:toUpperCase|toLowerCase|toFixed|trim|substring|slice|split|"
                           r"replace|includes|indexOf|charAt|padStart)\s*\(",
                           r"\b(?:Number|parseInt|parseFloat|String)\s*\("),
    "template_literals": lambda c: c.has_template,
    "operators": _rx(r"[\w$)\]\"]\s*(?:\*\*|[-+*/%])\s*[\w$(\"]", r"[\w$)\]]\s*[-+*/%]=(?!=)",
                     r"\+\+|--", r"(?<![=<>])[<>](?![=<>])", r"[=!]==?|<=|>=|&&|\|\|"),
    "comments": lambda c: c.has_comment,
    "if_else": _rx(r"\bif\s*\("),
    "switch": _rx(r"\bswitch\s*\("),
    "for_loop": _rx(r"\bfor\s*(?:await\s*)?\("),
    "while_loop": _rx(r"\bwhile\s*\(", r"\bdo\s*\{"),
    "strict_ternary": _strict_ternary,
    "break_continue": _rx(r"\b(?:break|continue)(?:[ \t]+[\w$]+)?[ \t]*(?:;|$|\})"),
    "function_decl": _rx(r"\bfunction\b\s*\*?\s*[\w$]+\s*\(",
                         r"\b(?:const|let|var)\s+[\w$]+\s*=\s*(?:async\s+)?function\b"),
    "default_params": _has_default_param,
    "return": _rx(r"\breturn\b[ \t]*[^\s;}]"),
    "arrow_functions": _rx(r"=>"),
    "scope": _has_scope,
    "arrays": _rx(r"(?<![=!<>])=\s*\[", r"\bnew\s+Array\b", r"\bArray\s*\.\s*(?:from|of|isArray)\b",
                  r"\.\s*(?:push|pop|shift|unshift|splice)\s*\("),
    "map_filter_reduce": _rx(r"\.\s*(?:map|filter|reduce)\s*\("),
    "objects": _rx(r"(?<![=!<>])=\s*\{", r"\breturn\s*\{", r"\bObject\s*\.\s*(?:keys|values|entries|assign)\b"),
    "destructuring": _rx(r"(?:const|let|var)\s*[\[{]"),
    "spread": _rx(r"\.\.\.\w"),
    "query_selector": _rx(r"\b(?:querySelector(?:All)?|getElementById|getElementsBy\w+)\s*\("),
    "dom_content": _rx(r"\.(?:textContent|innerHTML|innerText)\s*\+?=(?!=)"),
    "event_listener": _rx(r"\.\s*addEventListener\s*\(",
                          r"\.\s*on(?:click|submit|input|change|keydown|keyup|load|mouse\w+)\s*=(?!=)"),
    "create_element": _rx(r"\.\s*(?:createElement|createTextNode|createDocumentFragment|insertAdjacentHTML)\s*\("),
    "forms": _forms,
    "try_catch": _rx(r"(?<![\w$.])catch\s*[({]"),
    "throw": _rx(r"\bthrow\s+[\w$(\"]"),
    "json": _rx(r"\bJSON\s*\.\s*(?:parse|stringify)\s*\("),
    "es_modules": _rx(r"^\s*import\s+(?:[\w$*{][^;()]*\bfrom\s*\"\"|\"\")",
                      r"^\s*export\s+(?:default\b|const\b|let\b|var\b|function\b|class\b|async\b|\{|\*)"),
    "require": _rx(r"\brequire\s*\("),
    "timers_callbacks": _rx(r"\b(?:setTimeout|setInterval)\s*\("),
    "promises": _rx(r"\bnew\s+Promise\s*\(", r"\.\s*then\s*\(",
                    r"\bPromise\s*\.\s*(?:all|allSettled|any|race|resolve|reject)\b"),
    "async_await": _rx(r"\bawait\s+[\w$(\[]", r"\basync\s+(?:function\b|\(|[\w$]+\s*(?:=>|\())"),
    "fetch": _rx(r"(?:(?<![\w$.])|(?<=window\.)|(?<=globalThis\.))(?<!function )fetch\s*\("),
    "classes": _rx(r"\bclass\s+(?!extends\b)[\w$]+"),
    "class_extends": _rx(r"\bclass\s+[\w$]+\s+extends\s+[\w$.]+"),
    "getters_static": _rx(r"\b(?:get|set|static)\s+\w+\s*\("),
    "map_set": _rx(r"\bnew\s+(?:Map|Set|WeakMap|WeakSet)\s*\("),
    "optional_chaining": _rx(r"\?\.(?!\d)"),
    "fs_files": _fs_files,
    "process_argv": _rx(r"\bprocess\s*\.\s*argv\b"),
    "npm_package": _npm_package,
    "node_test": _node_test,
    "http_server": _http_server,
}


def _topic_found(rule, cleaned):
    if callable(rule):
        return bool(rule(cleaned))
    return any(p.search(cleaned.code) for p in rule)


def analyze_js(source, path=None):
    base = tokenize(source, "javascript")
    cleaned = JsCleaned(**{f.name: getattr(base, f.name) for f in fields(base)})
    cleaned.modules = _modules(source, base)
    code = cleaned.code

    functions = len(re.findall(r"\bfunction\b", code)) + code.count("=>") + _class_methods(code)
    classes = len(_CLASS_DECL.findall(code))
    loops = len(re.findall(r"\b(?:for|while|do)\b", code))
    conditions = len(re.findall(r"\b(?:if|case)\b", code))
    tries = len(re.findall(r"\btry\b", code))
    imports = len(re.findall(r"^\s*import\s*[\w$*{\"]", code, re.M)) + len(re.findall(r"\brequire\s*\(", code))
    score = cleaned.lines // 10 + functions * 2 + classes * 4 + loops + conditions + tries * 2 + imports

    return {
        "parsed": cleaned.syntax_ok,
        "lines": cleaned.lines,
        "functions": functions,
        "classes": classes,
        "loops": loops,
        "conditions": conditions,
        "tries": tries,
        "imports": imports,
        "score": score,
        "level": complexity_level(score),
        "topics": [tid for tid, rule in TOPIC_RULES.items() if _topic_found(rule, cleaned)],
        "syntax_ok": cleaned.syntax_ok,
    }
