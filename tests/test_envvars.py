import tests.helpers  # noqa: F401
import unittest

from languages.envvars import add_token, remove_token

NODE = r'--require "C:\Python\tracker\languages\javascript\node_hook.js"'


class TokenTests(unittest.TestCase):
    def test_add_keeps_existing(self):
        self.assertEqual(add_token("--max-old-space-size=4096", NODE), "--max-old-space-size=4096 " + NODE)

    def test_add_is_idempotent(self):
        self.assertEqual(add_token(NODE, NODE), NODE)

    def test_add_to_empty(self):
        self.assertEqual(add_token(None, NODE), NODE)
        self.assertEqual(add_token("  ", NODE), NODE)

    def test_remove_only_ours(self):
        self.assertEqual(remove_token("-Xmx1g " + NODE + " -Dx=1", NODE), "-Xmx1g -Dx=1")
        self.assertEqual(remove_token(NODE, NODE), "")

    def test_remove_missing_and_none(self):
        self.assertEqual(remove_token(None, NODE), "")
        self.assertEqual(remove_token("-Xmx1g", NODE), "-Xmx1g")

    def test_quoted_path_with_space_is_one_token(self):
        tok = r'-javaagent:"C:\my dir\a.jar"'
        self.assertEqual(remove_token("-Xmx1g " + tok, tok), "-Xmx1g")
        self.assertEqual(add_token(tok, tok), tok)

    def test_partial_match_not_removed(self):
        self.assertEqual(remove_token("--require x", "--require"), "x")


if __name__ == "__main__":
    unittest.main()
