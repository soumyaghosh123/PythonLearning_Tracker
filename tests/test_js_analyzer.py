import unittest
from pathlib import Path

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from languages import get_pack
from languages.javascript.analyzer import TOPIC_RULES, analyze_js, extract_scripts

FIX = Path(__file__).parent / "fixtures" / "javascript"


def read(name):
    return (FIX / name).read_text(encoding="utf-8-sig", errors="replace")


def topics(src):
    return set(analyze_js(src)["topics"])


class JsAnalyzerTests(unittest.TestCase):
    def test_each_level_fixture_finds_its_topics(self):
        pack = get_pack("javascript")
        for level in pack.curriculum()["levels"]:
            if level["id"] == 5:
                found = set(pack.analyze(read("l5_dom.html"), "l5_dom.html")["topics"])
            else:
                (path,) = FIX.glob(f"l{level['id']}_*.js")
                found = set(pack.analyze(read(path.name), path.name)["topics"])
            for t in level["topics"]:
                self.assertIn(t["id"], found, f"{t['id']} not detected in level {level['id']}")

    def test_every_topic_has_a_rule(self):
        ids = {t["id"] for lv in get_pack("javascript").curriculum()["levels"] for t in lv["topics"]}
        self.assertEqual(ids, set(TOPIC_RULES))

    def test_course_totals(self):
        levels = get_pack("javascript").curriculum()["levels"]
        self.assertEqual(sum(lv["days"]["standard"] for lv in levels), 132)
        self.assertEqual(sum(lv["days"]["aggressive"] for lv in levels), 65)

    def test_curriculum_metadata(self):
        c = get_pack("javascript").curriculum()
        self.assertEqual((c["language"], c["editor"]), ("javascript", "VS Code"))
        self.assertEqual(c["extensions"], [".js", ".mjs", ".cjs", ".html"])
        self.assertEqual(c["levels"][4]["project"], "To-do list page: add, tick off and delete items.")

    def test_html_inline_scripts_only(self):
        code, srcs = extract_scripts('<p>class</p><script src="app.js"></script><script>document.querySelector("p")</script>')
        self.assertEqual(srcs, ["app.js"])
        self.assertIn("querySelector", code)
        self.assertNotIn("<p>", code)

    def test_html_analysis_ignores_markup(self):
        r = get_pack("javascript").analyze("<p>class Foo while (x)</p><script>let a = 1;</script>", "p.html")
        self.assertNotIn("classes", r["topics"])
        self.assertEqual(r["classes"], 0)
        self.assertIn("let_const", r["topics"])

    def test_relative_and_builtin_modules_are_not_npm(self):
        r = analyze_js('const fs = require("fs"); const u = require("./util"); import x from "node:path";')
        self.assertNotIn("npm_package", r["topics"])
        self.assertIn("npm_package", analyze_js('const chalk = require("chalk");')["topics"])

    def test_scoped_and_subpath_packages(self):
        self.assertIn("npm_package", topics('import x from "@scope/pkg";'))
        self.assertNotIn("npm_package", topics('import { readFile } from "fs/promises";'))
        self.assertNotIn("npm_package", topics('// const c = require("chalk");\nconst a = "chalk";'))

    def test_result_keys_and_syntax(self):
        r = get_pack("javascript").analyze("console.log(1);\n", "a.js")
        for key in ("parsed", "lines", "functions", "classes", "loops", "conditions",
                    "tries", "imports", "score", "level", "topics", "syntax_ok"):
            self.assertIn(key, r)
        self.assertTrue(r["syntax_ok"])
        self.assertFalse(analyze_js("function f() {")["syntax_ok"])

    def test_keywords_in_comments_and_strings_ignored(self):
        t = topics('// while (x) {}\nconsole.log("class A extends B { catch (e) }");\nconst re = /for\\s*\\(/;')
        for tid in ("while_loop", "classes", "class_extends", "try_catch", "for_loop"):
            self.assertNotIn(tid, t)

    def test_score_formula(self):
        r = analyze_js(read("l6_errors_json_modules.js"))
        expected = (r["lines"] // 10 + r["functions"] * 2 + r["classes"] * 4 + r["loops"]
                    + r["conditions"] + r["tries"] * 2 + r["imports"])
        self.assertEqual(r["score"], expected)
        self.assertGreaterEqual(r["tries"], 1)
        self.assertEqual(r["imports"], 3)  # two imports and one require

    def test_functions_count_keyword_arrows_and_class_methods(self):
        src = ("function a() {}\nconst b = function () {};\nconst c = () => 1;\n"
               "class K { constructor(x = f(1)) { this.x = x; } get v() { return 1; } static s() {} async m() {} }")
        r = analyze_js(src)
        self.assertEqual(r["functions"], 2 + 1 + 4)
        self.assertEqual(r["classes"], 1)

    def test_hello_world_is_beginner_with_no_functions(self):
        r = analyze_js('console.log("hi");')
        self.assertEqual((r["functions"], r["classes"], r["level"]), (0, 0, "Beginner"))

    def test_strict_ternary_needs_both(self):
        self.assertIn("strict_ternary", topics("const a = x === 1 ? 'a' : 'b';"))
        self.assertNotIn("strict_ternary", topics("const a = x === 1;"))
        self.assertNotIn("strict_ternary", topics("const a = x ? 'a' : 'b';"))

    def test_loops_in_ordinary_layouts(self):
        t = topics("for (let i = arr.length - 1; i >= 0; i--) {\n  total += arr[i];\n}\n"
                   "for (const x of xs) { if (x) continue }\nwhile(\n  n < 3\n) { n++; break\n}")
        self.assertTrue({"for_loop", "while_loop", "break_continue"} <= t)

    def test_scope_needs_block_declaration_and_closure(self):
        closure = "function make() {\n  const n = 0;\n  return () => n;\n}"
        self.assertIn("scope", topics(closure))
        self.assertNotIn("scope", topics("function f() { const n = 0; return n; }"))
        self.assertNotIn("scope", topics("const n = 1; const f = () => n;"))
        self.assertIn("scope", topics("const mk = async () => {\n  let n = 0;\n  return async (x) => x + n;\n};"))

    def test_default_params_forms(self):
        self.assertIn("default_params", topics("function f(a, b = 2) {}"))
        self.assertIn("default_params", topics("const f = (a, b = 2) => a + b;"))
        self.assertIn("default_params", topics("const f = async (a = 1) => a;"))
        self.assertIn("default_params", topics("class A { constructor(n = 'x') {} }"))
        self.assertNotIn("default_params", topics("function f(a, b) { if (a == b) {} }"))
        self.assertNotIn("default_params", topics("const x = 1; if (x) { y = 2; }"))

    def test_return_needs_a_value(self):
        self.assertIn("return", topics("function f() {\n  return x;\n}"))
        self.assertNotIn("return", topics("function f() {\n  return;\n}"))

    def test_destructuring_and_spread(self):
        self.assertIn("destructuring", topics("const { a, b } = o;"))
        self.assertIn("destructuring", topics("let [x, y] = p;"))
        self.assertIn("spread", topics("const c = [...a, 1];"))
        self.assertNotIn("destructuring", topics("const a = 1;"))
        self.assertNotIn("spread", topics("const a = 1.5;"))

    def test_dom_content_is_assignment_only(self):
        self.assertIn("dom_content", topics("el.textContent = 'x';"))
        self.assertIn("dom_content", topics("el.innerHTML += x;"))
        self.assertNotIn("dom_content", topics("if (el.textContent === 'x') {}"))
        self.assertNotIn("dom_content", topics("console.log(el.textContent);"))

    def test_forms_needs_value_and_submit_or_input_event(self):
        ok = 'form.addEventListener("submit", (e) => { e.preventDefault(); log(input.value); });'
        self.assertIn("forms", topics(ok))
        self.assertIn("forms", topics("box.addEventListener('input', () => log(box.value));"))
        self.assertNotIn("forms", topics('b.addEventListener("click", () => log(1)); const v = x.value;'))
        self.assertNotIn("forms", topics('form.addEventListener("submit", () => log(1));'))

    def test_event_listener_and_create_element_need_calls(self):
        self.assertNotIn("event_listener", topics('const s = "addEventListener";'))
        self.assertIn("event_listener", topics("btn.onclick = () => 1;"))
        self.assertNotIn("event_listener", topics("if (a.onclick == null) {}"))
        self.assertIn("create_element", topics("const li = document.createElement('li');"))

    def test_node_modules_need_usage_not_just_import(self):
        self.assertNotIn("fs_files", topics('const fs = require("fs");'))
        self.assertIn("fs_files", topics('const { readFileSync } = require("fs");\nreadFileSync("a");'))
        self.assertIn("fs_files", topics('import fs from "node:fs/promises";\nawait fs.readFile("a");'))
        self.assertNotIn("http_server", topics('const http = require("http");'))
        self.assertIn("http_server", topics('const http = require("http");\nhttp.createServer(() => {});'))

    def test_node_test_needs_module_and_test_call(self):
        self.assertIn("node_test", topics('import test from "node:test";\ntest("a", () => {});'))
        self.assertIn("node_test", topics('const assert = require("assert");\nit("a", () => {});'))
        self.assertNotIn("node_test", topics('const assert = require("assert");\nassert.ok(/a/.test(x));'))
        self.assertNotIn("node_test", topics('const assert = require("assert");'))

    def test_async_and_fetch(self):
        self.assertIn("async_await", topics("async function f() { await g(); }"))
        self.assertIn("async_await", topics("const f = async () => { await g(); };"))
        self.assertNotIn("async_await", topics("const await_ = 1;"))
        self.assertIn("fetch", topics("const r = await fetch(url);"))
        self.assertNotIn("fetch", topics("function fetchUser() {}"))
        self.assertNotIn("fetch", topics("const s = 'fetch(';"))

    def test_classes_getters_and_optional_chaining(self):
        self.assertIn("getters_static", topics("class A { static make() {} get n() { return 1; } }"))
        self.assertNotIn("getters_static", topics("const x = o.get('a');"))
        self.assertIn("optional_chaining", topics("const c = a?.b;"))
        self.assertNotIn("optional_chaining", topics("const c = a ?.5 : 1;"))
        self.assertIn("class_extends", topics("class A extends B {}"))
        self.assertNotIn("class_extends", topics("class A {}"))

    def test_es_modules_and_require(self):
        self.assertIn("es_modules", topics('import { a,\n  b } from "./x.js";'))
        self.assertIn("es_modules", topics("export default function f() {}"))
        self.assertNotIn("es_modules", topics("const m = await import('./x.js');\nconst e = 'export const';"))
        self.assertIn("require", topics("const p = require(\"path\");"))

    def test_try_catch_ignores_promise_catch(self):
        self.assertNotIn("try_catch", topics("x.then(r => r).catch(e => log(e));"))
        self.assertNotIn("try_catch", topics("p.catch(console.error);"))
        self.assertNotIn("try_catch", topics(read("l7_async.js")))
        self.assertIn("try_catch", topics("try { f(); } catch (e) { g(); }"))
        self.assertIn("try_catch", topics("try { f(); } catch { g(); }"))

    def test_operators_common_beginner_forms(self):
        for src in ('const t = "Total: " + total;', 'const s = "a" + "b";', "n += 1;", "i++;",
                    "i--;", "if (a < b) {}", "if (a > b) {}", "const x = a ** 2;", "const y = a - b;"):
            self.assertIn("operators", topics(src), src)
        self.assertNotIn("operators", topics("const f = () => 1;"))

    def test_strict_ternary_branches_may_contain_dots(self):
        self.assertIn("strict_ternary", topics('const a = x === 1 ? user.name : "x";'))
        self.assertIn("strict_ternary", topics("const a = a === b ? 1.5 : 2;"))
        self.assertNotIn("strict_ternary", topics("a === b; const n = obj?.x ?? 0;"))


if __name__ == "__main__":
    unittest.main()
