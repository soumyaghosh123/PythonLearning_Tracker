"""Pattern-based Java analyser: topic rules and complexity score over cleaned code.

Source goes through the shared tokenizer first, so keywords inside comments,
strings and char literals never count toward a topic.
"""
import re

from languages.base import complexity_level
from languages.clike import tokenize

_TYPE = r"[\w.]+(?:<[^<>]*(?:<[^<>]*>[^<>]*)*>)?(?:\[\])*"
_NOT_KEYWORD = r"(?!(?:return|new|else|throw|case|if|for|while|switch|catch|synchronized|do|try)\b)"
_METHOD = re.compile(
    r"(?<![\w.])" + _NOT_KEYWORD + "(" + _TYPE + r")\s+" + _NOT_KEYWORD +
    r"(\w+)\s*\(([^()]*)\)\s*(?:throws\s+[\w.,\s]+)?\{"
)
_CLASS = re.compile(r"(?<![\w.@])(class|interface|enum|record)\s+(\w+)")
_MAIN = re.compile(r"public\s+static\s+void\s+main\s*\(")


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


def _methods(code):
    """(return type, name, params, body) for each method declaration."""
    found = []
    for m in _METHOD.finditer(code):
        found.append((m.group(1), m.group(2), " ".join(m.group(3).split()), _body(code, m.end() - 1)))
    return found


def _declared_classes(code):
    """(kind, name, start) of every class-like declaration, minus the one holding main."""
    decls = [(m.group(1), m.group(2), m.start()) for m in _CLASS.finditer(code)]
    main = _MAIN.search(code)
    if main:
        before = [d for d in decls if d[2] < main.start()]
        if before:
            decls.remove(before[-1])
    return decls


def _is_overloaded(c):
    seen = {}
    for _type, name, params, _body_text in _methods(c.code):
        if name[0].isupper():
            continue  # constructors are not overloads of a method
        seen.setdefault(name, set()).add(params)
    return any(len(p) > 1 for p in seen.values())


def _is_recursive(c):
    for _type, name, _params, body in _methods(c.code):
        if not name[0].isupper() and re.search(r"(?<![\w.])(?:this\.)?" + name + r"\s*\(", body):
            return True
    return False


def _returns_value(c):
    return any(t != "void" and p and re.search(r"\breturn\s+\S", body)
               for t, name, p, body in _methods(c.code) if name != "main")


def _uses_own_class(c):
    return any(kind == "class" and re.search(r"\bnew\s+" + name + r"\s*\(", c.code)
               for kind, name, _ in _declared_classes(c.code))


def _has_constructor(c):
    for kind, name, _ in _declared_classes(c.code):
        if kind != "class":
            continue
        for m in re.finditer(r"(?<![\w.])" + name + r"\s*\([^()]*\)\s*(?:throws\s+[\w.,\s]+)?\{", c.code):
            if not re.search(r"\bnew\s*$", c.code[:m.start()]):
                return True
    return False


def _all(*patterns):
    compiled = [re.compile(p, re.M) for p in patterns]
    return lambda c: all(p.search(c.code) for p in compiled)


def _rx(*patterns):
    return [re.compile(p, re.M) for p in patterns]


_FIELD = r"\bprivate\s+(?:static\s+)?(?:final\s+)?[\w.<>\[\],]+\s+\w+\s*(?:=[^;]*)?;"

# One entry per topic id, in course order. A list of regexes matches when any
# regex matches the cleaned code; a callable gets the whole Cleaned result.
TOPIC_RULES = {
    "main_method": _rx(r"public\s+static\s+void\s+main\s*\("),
    "println": _rx(r"System\s*\.\s*out\s*\.\s*print(?:ln|f)?\s*\("),
    "primitives": _rx(r"\b(?:int|long|double|float|boolean|char|byte|short)\s+\w+\s*(?:=|;|,)"),
    "strings": lambda c: bool(re.search(r"\bString\b", c.code)) and bool(c.strings),
    "scanner": _rx(r"new\s+Scanner\s*\(\s*System\.in"),
    "operators": _rx(r"\w\s*[-+*/%]\s*\w", r"==|!=|<=|>=|&&|\|\|"),
    "comments": lambda c: c.has_comment,
    "if_else": _rx(r"\bif\s*\("),
    "switch": _rx(r"\bswitch\s*\("),
    "for_loop": _rx(r"\bfor\s*\([^)]*;"),
    "while_loop": _rx(r"\bwhile\s*\(", r"\bdo\s*\{"),
    "break_continue": _rx(r"\b(?:break|continue)\s*;"),
    "arrays": _rx(r"\b(?!String\s*\[\s*\]\s*args\b)\w+\s*\[\s*\]\s*\w+", r"\bnew\s+\w+\s*\["),
    "enhanced_for": _rx(r"for\s*\(\s*(final\s+)?[\w<>\[\],\s]+\s+\w+\s*:"),
    "arrays_2d": _rx(r"\[\s*\]\s*\[\s*\]", r"new\s+\w+\s*\[[^\]]*\]\s*\["),
    "string_methods": _rx(r"\.\s*(?:length|charAt|substring|indexOf|toUpperCase|toLowerCase|trim|"
                          r"equals|equalsIgnoreCase|split|replace|contains|startsWith|endsWith|isEmpty)\s*\("),
    "string_builder": _rx(r"\bStringBuilder\b", r"\bStringBuffer\b"),
    "static_methods": _rx(r"\bstatic\s+(?!void\s+main\b)[\w.<>\[\]]+\s+\w+\s*\("),
    "params_return": _returns_value,
    "overloading": _is_overloaded,
    "recursion": _is_recursive,
    "class_new": _uses_own_class,
    "constructors": _has_constructor,
    "this_keyword": _rx(r"\bthis\b"),
    "encapsulation": _all(_FIELD, r"\bget[A-Z]\w*\s*\("),
    "static_members": _rx(r"\bstatic\s+(?:final\s+)?[\w.<>\[\]]+\s+\w+\s*(?:=|;)"),
    "extends": _rx(r"\bclass\s+\w+(?:<[^>]*>)?\s+extends\s+\w+"),
    "super_call": _rx(r"\bsuper\s*(?:\(|\.)"),
    "override": _rx(r"@Override\b"),
    "abstract_class": _rx(r"\babstract\s+class\b"),
    "interfaces": _rx(r"\binterface\s+\w+", r"\bimplements\s+\w+"),
    "polymorphism": _rx(r"\b([A-Z]\w*)\s+\w+\s*=\s*new\s+(?!\1\b)[A-Z]\w*\s*\("),
    "try_catch": _rx(r"\bcatch\s*\("),
    "throw_throws": _rx(r"\bthrows?\s+\w+"),
    "custom_exception": _rx(r"class\s+\w+\s+extends\s+\w*(?:Exception|Error)\b"),
    "try_with_resources": _rx(r"\btry\s*\("),
    "read_file": _rx(r"FileReader", r"BufferedReader", r"Files\.read\w*", r"Files\.lines",
                     r"new\s+Scanner\s*\(\s*new\s+File"),
    "write_file": _rx(r"FileWriter", r"PrintWriter", r"BufferedWriter", r"Files\.write\w*"),
    "array_list": _rx(r"\bArrayList\b"),
    "hash_map": _rx(r"\bHashMap\b"),
    "hash_set": _rx(r"\bHashSet\b"),
    "generics": _rx(r"\b[A-Z]\w*\s*<\s*[A-Z]\w*(?:\s*,\s*[A-Z]\w*)*\s*>", r"<\s*[A-Z]\w*\s*>\s+\w"),
    "comparator": _rx(r"\bComparator\b", r"\bComparable\b"),
    "lambdas": _rx(r"\)\s*->", r"\b(?!case\b|default\b)[a-z_]\w*\s*->"),
    "streams": _rx(r"\.\s*stream\s*\(", r"\bStream\s*\.", r"\bIntStream\b"),
    "enums_records": _rx(r"(?<![\w.@])enum\s+\w+", r"(?<![\w.])record\s+\w+\s*\("),
    "packages": _rx(r"^\s*package\s+[\w.]+\s*;", r"^\s*import\s+(?:static\s+)?(?!java\.lang\.[\w*]+\s*;)[\w.*]+\s*;"),
    "junit": _rx(r"import\s+(?:static\s+)?org\.junit", r"@Test\b"),
}


def _topic_found(rule, cleaned):
    if callable(rule):
        return bool(rule(cleaned))
    return any(p.search(cleaned.code) for p in rule)


def analyze_java(source, path=None):
    cleaned = tokenize(source, "java")
    code = cleaned.code

    methods = _methods(code)
    functions = len(methods) - (1 if any(name == "main" for _t, name, _p, _b in methods) else 0)
    classes = len(_declared_classes(code))
    loops = len(re.findall(r"\b(?:for|while|do)\b", code))
    conditions = len(re.findall(r"\b(?:if|case)\b", code))
    tries = len(re.findall(r"\btry\b", code))
    imports = len(re.findall(r"^\s*import\s", code, re.M))
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
