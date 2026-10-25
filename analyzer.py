"""Reads Python source code (without running it) and works out:
  - how complex it is (a score and a level: Beginner / Intermediate / Advanced)
  - which curriculum topics it uses (e.g. "for_loop", "default_args", "inheritance")

It uses the built-in `ast` module, which turns code into a tree of nodes
(ast.For, ast.FunctionDef, ast.ClassDef ...) that we can walk through.
"""

import ast
import io
import sys
import tokenize
from pathlib import Path

LIST_METHODS = {"append", "extend", "insert", "remove", "pop", "sort", "reverse", "index", "count", "clear"}
READ_METHODS = {"read", "readline", "readlines", "read_text"}
WRITE_METHODS = {"write", "writelines", "write_text"}
API_MODULES = {"requests", "httpx", "urllib.request", "http.client", "aiohttp"}


def complexity_level(score):
    if score <= 10:
        return "Beginner"
    if score <= 30:
        return "Intermediate"
    return "Advanced"


def count_code_lines(source):
    """Lines that are not blank and not just a comment."""
    return sum(1 for line in source.splitlines() if line.strip() and not line.strip().startswith("#"))


def has_comment(source):
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT and not token.string.startswith("#!"):
                return True
    except (tokenize.TokenError, SyntaxError):
        pass
    return False


def imported_modules(tree):
    """Full names of every module imported, e.g. {'math', 'urllib.request'}.
    Relative imports (from . import x) are returned as '.'."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                names.add(".")
            elif node.module:
                names.add(node.module)
                # "from urllib import request" means urllib.request is used
                names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def is_own_module(name, script_dir):
    if name == ".":
        return True
    if script_dir is None:
        return False
    top = name.split(".")[0]
    return (script_dir / f"{top}.py").exists() or (script_dir / top / "__init__.py").exists()


def method_name(call):
    """For a call like `items.append(x)` return 'append'."""
    return call.func.attr if isinstance(call.func, ast.Attribute) else None


def function_name(call):
    """For a call like `print(x)` return 'print'."""
    return call.func.id if isinstance(call.func, ast.Name) else None


def decorator_name(decorator):
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    if isinstance(decorator, ast.Name):
        return decorator.id
    return None


def is_dunder(name):
    return name.startswith("__") and name.endswith("__")


def find_topics(tree, source, script_dir=None):
    found = set()
    has_number = has_string = has_arithmetic = has_compare = False

    for node in ast.walk(tree):
        # --- Level 1: basics ---
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(n, ast.Name) for t in targets for n in ast.walk(t)):
                found.add("variables")
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                has_number = True
            elif isinstance(node.value, str):
                has_string = True
        if isinstance(node, ast.JoinedStr):
            has_string = True
        if isinstance(node, (ast.BinOp, ast.AugAssign)):
            has_arithmetic = True
        if isinstance(node, ast.Compare):
            has_compare = True

        if isinstance(node, ast.Call):
            name = function_name(node)
            method = method_name(node)
            if name == "print":
                found.add("print")
            elif name == "input":
                found.add("input")
            elif name == "range":
                found.add("range")
            elif name == "list":
                found.add("lists")
            elif name == "dict":
                found.add("dicts")
            elif name == "set":
                found.add("sets")
            if method in LIST_METHODS:
                found.add("list_methods")
            if method in READ_METHODS or (method == "load" and isinstance(node.func.value, ast.Name) and node.func.value.id == "json"):
                found.add("read_file")
            if method in WRITE_METHODS or (method == "dump" and isinstance(node.func.value, ast.Name) and node.func.value.id == "json"):
                found.add("write_file")

        # --- Level 2: control flow ---
        if isinstance(node, ast.If):
            found.add("if_else")
            if (isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__"):
                found.add("main_guard")
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            found.add("for_loop")
        elif isinstance(node, ast.While):
            found.add("while_loop")
        elif isinstance(node, (ast.Break, ast.Continue)):
            found.add("break_continue")

        # --- Level 3: data structures ---
        elif isinstance(node, ast.List):
            found.add("lists")
        elif isinstance(node, ast.Tuple) and isinstance(node.ctx, ast.Load):
            found.add("tuples")
        elif isinstance(node, (ast.Dict, ast.DictComp)):
            found.add("dicts")
        elif isinstance(node, (ast.Set, ast.SetComp)):
            found.add("sets")
        elif isinstance(node, ast.Slice):
            found.add("slicing")

        # --- Level 4: functions ---
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.add("def_function")
            args = node.args
            all_args = args.posonlyargs + args.args + args.kwonlyargs
            if [a for a in all_args if a.arg not in ("self", "cls")] or args.vararg or args.kwarg:
                found.add("parameters")
            if args.defaults or any(d is not None for d in args.kw_defaults):
                found.add("default_args")
            if args.vararg or args.kwarg:
                found.add("args_kwargs")
            if node.returns or any(a.annotation for a in all_args):
                found.add("type_hints")
            for decorator in node.decorator_list:
                found.add("decorators")
                if decorator_name(decorator) == "contextmanager":
                    found.add("context_managers")
        elif isinstance(node, ast.Return) and node.value is not None:
            found.add("return_value")
        elif isinstance(node, ast.Lambda):
            found.add("lambda")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            found.add("scope")

        # --- Level 5: files & errors ---
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                call = item.context_expr
                if isinstance(call, ast.Call) and (function_name(call) == "open" or method_name(call) == "open"):
                    found.add("with_open")
        elif isinstance(node, ast.Try) or (hasattr(ast, "TryStar") and isinstance(node, ast.TryStar)):
            if node.handlers:
                found.add("try_except")
        elif isinstance(node, ast.Raise):
            found.add("raise_error")

        # --- Level 7: classes ---
        if isinstance(node, ast.ClassDef):
            found.add("class_def")
            if [b for b in node.bases if not (isinstance(b, ast.Name) and b.id == "object")]:
                found.add("inheritance")
            if node.decorator_list:
                found.add("decorators")
            method_names = set()
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_names.add(item.name)
                    if item.name == "__init__":
                        if item.args.args and item.args.args[0].arg == "self":
                            found.add("init_self")
                    elif is_dunder(item.name):
                        found.add("special_methods")
                    else:
                        found.add("methods")
                elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                    found.add("class_attributes")
            if {"__enter__", "__exit__"} <= method_names:
                found.add("context_managers")

        # --- Level 8: advanced ---
        if isinstance(node, (ast.ListComp, ast.DictComp, ast.SetComp)):
            found.add("comprehensions")
        if isinstance(node, (ast.Yield, ast.YieldFrom, ast.GeneratorExp)):
            found.add("generators")
        if isinstance(node, ast.AnnAssign):
            found.add("type_hints")
        if isinstance(node, ast.Lambda) and (node.args.vararg or node.args.kwarg):
            found.add("args_kwargs")

        # --- Level 9: testing & projects ---
        if isinstance(node, ast.Assert):
            found.add("assert_stmt")
        if isinstance(node, ast.Attribute) and node.attr == "argv":
            found.add("cli_args")

    if has_number and has_string:
        found.add("numbers_strings")
    if has_arithmetic and has_compare:
        found.add("operators")
    if has_comment(source):
        found.add("comments")

    # --- Level 6: modules (and import-based topics from other levels) ---
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.add("import_module")
        elif isinstance(node, ast.ImportFrom):
            found.add("from_import")
            if node.module == "sys" and any(a.name == "argv" for a in node.names):
                found.add("cli_args")

    stdlib = getattr(sys, "stdlib_module_names", frozenset())
    for name in imported_modules(tree):
        top = name.split(".")[0]
        if name in API_MODULES:
            found.add("apis")
        if top == "json":
            found.add("json_module")
        if top in ("unittest", "pytest"):
            found.add("unittest")
        if top == "argparse":
            found.add("cli_args")
        if is_own_module(name, script_dir):
            found.add("own_module")
        elif top in stdlib:
            if top != "__future__":
                found.add("stdlib")
        else:
            found.add("third_party")

    return found


def analyze_source(source, script_path=None):
    """Return a dict of metrics and topics for one piece of source code."""
    script_dir = Path(script_path).parent if script_path else None
    lines = count_code_lines(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"parsed": False, "lines": lines, "functions": 0, "classes": 0, "loops": 0,
                "conditions": 0, "tries": 0, "imports": 0, "score": lines // 10,
                "level": complexity_level(lines // 10), "topics": []}

    nodes = list(ast.walk(tree))
    functions = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in nodes)
    classes = sum(isinstance(n, ast.ClassDef) for n in nodes)
    loops = sum(isinstance(n, (ast.For, ast.AsyncFor, ast.While)) for n in nodes)
    conditions = sum(isinstance(n, ast.If) for n in nodes)
    tries = sum(isinstance(n, ast.Try) or (hasattr(ast, "TryStar") and isinstance(n, ast.TryStar)) for n in nodes)
    imports = sum(len(n.names) if isinstance(n, ast.Import) else 1
                  for n in nodes if isinstance(n, (ast.Import, ast.ImportFrom)))

    score = lines // 10 + functions * 2 + classes * 4 + loops + conditions + tries * 2 + imports
    return {
        "parsed": True,
        "lines": lines,
        "functions": functions,
        "classes": classes,
        "loops": loops,
        "conditions": conditions,
        "tries": tries,
        "imports": imports,
        "score": score,
        "level": complexity_level(score),
        "topics": sorted(find_topics(tree, source, script_dir)),
    }


if __name__ == "__main__":
    # Try it on a file:  python tracker\analyzer.py welcome.py
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python analyzer.py <file.py>")
    path = Path(sys.argv[1])
    result = analyze_source(path.read_text(encoding="utf-8-sig"), path)
    for key, value in result.items():
        print(f"{key:>11}: {value}")
