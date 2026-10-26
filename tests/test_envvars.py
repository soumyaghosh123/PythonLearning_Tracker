import tests.helpers  # noqa: F401
import unittest
from unittest import mock

from languages import envvars
from languages.envvars import add_token, remove_token, remove_tokens_matching

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

    def test_unbalanced_quote_leaves_value_unchanged(self):
        bad = '-Dfoo="bar -Xmx1g'
        self.assertEqual(add_token(bad, NODE), bad)
        self.assertEqual(remove_token(bad, NODE), bad)
        self.assertEqual(remove_token(bad + " " + NODE, NODE), bad + " " + NODE)

    def test_remove_absent_token_keeps_whitespace(self):
        self.assertEqual(remove_token('-Xmx1g  -Dy=2', 'zzz'), '-Xmx1g  -Dy=2')

    def test_backslashes_preserved(self):
        opt = r'-Djava.io.tmpdir=C:\Temp -Xmx1g'
        self.assertEqual(add_token(opt, NODE), opt + " " + NODE)

    def test_every_duplicate_removed_others_intact(self):
        value = "-A " + NODE + " -B " + NODE + " -C"
        self.assertEqual(remove_token(value, NODE), "-A -B -C")

    def test_partial_match_not_removed(self):
        self.assertEqual(remove_token("--require x", "--require"), "x")


def _flag_pairs(tokens, i):
    return 2 if tokens[i] == "--require" and i + 1 < len(tokens) else 0


def _javaagents(tokens, i):
    return 1 if tokens[i].startswith("-javaagent:") else 0


class RemoveMatchingTests(unittest.TestCase):
    def test_removes_multi_token_run_keeps_others(self):
        value = '-a --require "C:/x y/h.js" -b'
        self.assertEqual(remove_tokens_matching(value, _flag_pairs), "-a -b")

    def test_single_tokens_and_all_matches(self):
        self.assertEqual(remove_tokens_matching("-javaagent:a.jar -Xmx1g -javaagent:b.jar", _javaagents), "-Xmx1g")

    def test_no_match_keeps_spacing(self):
        self.assertEqual(remove_tokens_matching("-Xmx1g   -Xms1g", _javaagents), "-Xmx1g   -Xms1g")
        self.assertEqual(remove_tokens_matching(None, _javaagents), "")

    def test_unbalanced_quote_unchanged(self):
        self.assertEqual(remove_tokens_matching('-javaagent:a "x', _javaagents), '-javaagent:a "x')


class NonTextValueTests(unittest.TestCase):
    """REG_DWORD / REG_MULTI_SZ values must be treated as unmanageable and never overwritten."""

    def run_with(self, value, func, *args):
        with mock.patch("winreg.QueryValueEx", return_value=(value, 4)), mock.patch("winreg.OpenKey"), \
                mock.patch.object(envvars, "set_user_env") as setter:
            return func(*args), setter

    def test_get_returns_none_for_int_and_list(self):
        for value in (5, ["a", "b"]):
            result, _ = self.run_with(value, envvars.get_user_env, "X")
            self.assertIsNone(result)

    def test_get_returns_text(self):
        result, _ = self.run_with("-Xmx1g", envvars.get_user_env, "X")
        self.assertEqual(result, "-Xmx1g")

    def test_add_and_remove_skip_non_text(self):
        for value in (5, ["a", "b"]):
            result, setter = self.run_with(value, envvars.user_env_add, "X", "-javaagent:a.jar")
            self.assertFalse(result)
            setter.assert_not_called()
            result, setter = self.run_with(value, envvars.user_env_remove, "X", "-javaagent:a.jar")
            self.assertFalse(result)
            setter.assert_not_called()
            result, setter = self.run_with(value, envvars.user_env_remove_matching, "X", _javaagents)
            self.assertFalse(result)
            setter.assert_not_called()

    def test_add_still_works_when_unset(self):
        with mock.patch("winreg.OpenKey", side_effect=FileNotFoundError), \
                mock.patch.object(envvars, "set_user_env") as setter:
            self.assertTrue(envvars.user_env_add("X", "-javaagent:a.jar"))
        setter.assert_called_once_with("X", "-javaagent:a.jar")


if __name__ == "__main__":
    unittest.main()
