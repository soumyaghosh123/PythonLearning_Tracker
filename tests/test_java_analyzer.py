import unittest
from pathlib import Path

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from languages import get_pack
from languages.java.analyzer import TOPIC_RULES, analyze_java

FIX = Path(__file__).parent / "fixtures" / "java"


def read(name):
    return (FIX / name).read_text(encoding="utf-8-sig", errors="replace")


def fixture(level):
    (path,) = FIX.glob(f"l{level['id']}_*.java")
    return path.read_text(encoding="utf-8-sig", errors="replace")


class JavaAnalyzerTests(unittest.TestCase):
    def test_each_level_fixture_finds_its_topics(self):
        for level in get_pack("java").curriculum()["levels"]:
            found = set(analyze_java(fixture(level))["topics"])
            for t in level["topics"]:
                self.assertIn(t["id"], found, f"{t['id']} not detected in level {level['id']}")

    def test_every_topic_has_a_rule(self):
        ids = {t["id"] for lv in get_pack("java").curriculum()["levels"] for t in lv["topics"]}
        self.assertEqual(ids, set(TOPIC_RULES))

    def test_hello_world_is_beginner(self):
        r = analyze_java(read("hello.java"))
        self.assertEqual((r["classes"], r["functions"], r["level"]), (0, 0, "Beginner"))

    def test_keywords_in_comments_and_strings_ignored(self):
        r = analyze_java('class A { public static void main(String[] a) { // extends Foo\n System.out.println("while"); } }')
        self.assertNotIn("extends", r["topics"])
        self.assertNotIn("while_loop", r["topics"])

    def test_non_utf8_source_does_not_crash(self):
        src = (FIX / "cp1252.java").read_bytes().decode("utf-8", errors="replace")
        self.assertIn("println", analyze_java(src)["topics"])

    def test_course_totals(self):
        levels = get_pack("java").curriculum()["levels"]
        self.assertEqual(sum(lv["days"]["standard"] for lv in levels), 132)
        self.assertEqual(sum(lv["days"]["aggressive"] for lv in levels), 65)

    def test_pack_analyze_and_result_keys(self):
        r = get_pack("java").analyze(read("hello.java"))
        for key in ("parsed", "lines", "functions", "classes", "loops", "conditions",
                    "tries", "imports", "score", "level", "topics", "syntax_ok"):
            self.assertIn(key, r)
        self.assertTrue(r["syntax_ok"])
        self.assertEqual(r["parsed"], r["syntax_ok"])

    def test_unbalanced_source_is_not_syntax_ok(self):
        self.assertFalse(analyze_java("class A { void f() {")["syntax_ok"])

    def test_main_class_and_main_not_counted(self):
        r = analyze_java(read("l4_methods.java"))
        self.assertEqual(r["classes"], 0)
        self.assertGreaterEqual(r["functions"], 4)

    def test_score_formula(self):
        r = analyze_java(read("l7_exceptions.java"))
        expected = (r["lines"] // 10 + r["functions"] * 2 + r["classes"] * 4 + r["loops"]
                    + r["conditions"] + r["tries"] * 2 + r["imports"])
        self.assertEqual(r["score"], expected)
        self.assertGreaterEqual(r["tries"], 2)
        self.assertGreaterEqual(r["imports"], 1)

    def test_overloading_needs_different_parameters(self):
        same = "class A { void f(int a) {} void f(int a) {} }"
        diff = "class A { void f(int a) {} void f(String a) {} }"
        self.assertNotIn("overloading", analyze_java(same)["topics"])
        self.assertIn("overloading", analyze_java(diff)["topics"])

    def test_recursion_needs_self_call_in_body(self):
        self.assertIn("recursion", analyze_java("class A { int f(int n) { return n <= 1 ? 1 : n * f(n - 1); } }")["topics"])
        self.assertNotIn("recursion", analyze_java("class A { int f(int n) { return n; } int g() { return f(1); } }")["topics"])

    def test_polymorphism_declared_vs_created_type(self):
        self.assertIn("polymorphism", analyze_java("class A { void m() { Animal a = new Dog(); } }")["topics"])
        self.assertNotIn("polymorphism", analyze_java("class A { void m() { Dog a = new Dog(); } }")["topics"])

    def test_polymorphism_override_clause(self):
        src = ("class Dog extends Animal { @Override void speak() {} }\n"
               "class M { void m() { List<Animal> l = new ArrayList<>(); l.add(new Dog()); } }")
        self.assertIn("polymorphism", analyze_java(src)["topics"])

    def test_encapsulation_needs_getter_declaration(self):
        calls = "class A { private int x; void f(Exception e) { e.getMessage(); } }"
        decl = "class A { private int x; int getX() { return x; } }"
        self.assertNotIn("encapsulation", analyze_java(calls)["topics"])
        self.assertIn("encapsulation", analyze_java(decl)["topics"])

    def test_nested_class_and_external_class(self):
        nested = ("public class Main { static class Person { Person(String n) {} }\n"
                  " public static void main(String[] a) { Person p = new Person(\"x\"); } }")
        t = analyze_java(nested)["topics"]
        self.assertIn("class_new", t)
        self.assertIn("constructors", t)
        external = "public class Main { public static void main(String[] a) { Dog d = new Dog(\"x\"); } }"
        self.assertIn("class_new", analyze_java(external)["topics"])
        jdk = "public class Main { public static void main(String[] a) { Scanner s = new Scanner(System.in); } }"
        self.assertNotIn("class_new", analyze_java(jdk)["topics"])

    def test_strings_ignores_main_args(self):
        self.assertNotIn("strings", analyze_java(read("hello.java"))["topics"])
        self.assertIn("strings", analyze_java(read("l1_basics.java"))["topics"])
        src = "class A { int f(String s) { return s.length(); } }"
        self.assertIn("strings", analyze_java(src)["topics"])

    def test_overload_delegation_is_not_recursion(self):
        src = "class A { int add(int a) { return add(a, 0); } int add(int a, int b) { return a + b; } }"
        self.assertNotIn("recursion", analyze_java(src)["topics"])
        self.assertIn("recursion", analyze_java(read("l4_methods.java"))["topics"])

    def test_junit_and_packages(self):
        r = analyze_java("package app.core;\nimport org.junit.jupiter.api.Test;\nclass T { @Test void t() {} }")
        self.assertIn("junit", r["topics"])
        self.assertIn("packages", r["topics"])
        self.assertNotIn("packages", analyze_java("import java.lang.Math;\nclass T {}")["topics"])


if __name__ == "__main__":
    unittest.main()
