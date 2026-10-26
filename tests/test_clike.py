import unittest

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from languages.clike import tokenize


class ClikeTests(unittest.TestCase):
    def test_comments_and_strings_removed(self):
        c = tokenize('int x = 1; // class Foo\n/* while */ String s = "for (;;)";', "java")
        self.assertNotIn("class", c.code)
        self.assertNotIn("while", c.code)
        self.assertNotIn("for", c.code)
        self.assertTrue(c.has_comment)
        self.assertTrue(c.syntax_ok)
        self.assertEqual(c.strings, ["for (;;)"])

    def test_template_keeps_expressions(self):
        c = tokenize("const s = `hi ${name.map(x => x)} class`;", "javascript")
        self.assertIn("name.map(x => x)", c.code)
        self.assertNotIn("class", c.code)
        self.assertTrue(c.has_template)
        self.assertTrue(c.syntax_ok)

    def test_nested_template(self):
        c = tokenize("const s = `a ${ f(`b ${x} while`) } c`;", "javascript")
        self.assertTrue(c.syntax_ok)
        self.assertNotIn("while", c.code)
        self.assertIn("f(", c.code)

    def test_regex_literal_vs_division(self):
        self.assertNotIn("class", tokenize("const r = /class/g; const h = a / b / c;", "javascript").code)
        self.assertTrue(tokenize("const h = a / b / c;", "javascript").syntax_ok)
        self.assertNotIn("while", tokenize("x = s.split(/[/]while/);", "javascript").code)

    def test_java_text_block(self):
        c = tokenize('String t = """\n  while "x"\n""";', "java")
        self.assertNotIn("while", c.code)
        self.assertTrue(c.syntax_ok)

    def test_unbalanced_and_unclosed(self):
        self.assertFalse(tokenize("if (x { }", "java").syntax_ok)
        self.assertFalse(tokenize('let s = "abc;', "javascript").syntax_ok)
        self.assertFalse(tokenize("/* never closed", "java").syntax_ok)
        self.assertFalse(tokenize("(]", "java").syntax_ok)
        self.assertFalse(tokenize("let s = `abc", "javascript").syntax_ok)

    def test_java_char_literals_and_escapes(self):
        c = tokenize("char q = '\"'; String s = \"a\\\"b\"; // done", "java")
        self.assertTrue(c.syntax_ok)
        self.assertEqual(c.strings, ['a\\"b'])

    def test_module_names_kept_in_strings(self):
        c = tokenize("const fs = require('fs'); el.addEventListener(\"submit\", f);", "javascript")
        self.assertEqual(c.strings, ["fs", "submit"])
        self.assertIn("require(", c.code)

    def test_line_count_ignores_blank_and_comment_lines(self):
        self.assertEqual(tokenize("// a\n\nint x;\n/* b\n c */\nint y;\n", "java").lines, 2)


if __name__ == "__main__":
    unittest.main()
