import unittest
from pathlib import Path

from tests import helpers  # noqa: F401  (sets up sys.path and PYTRACKER_HOME)
from languages import all_packs, get_pack, pack_for_path

FIXTURES = Path(__file__).parent / "fixtures"


class PackTests(unittest.TestCase):
    def test_registry_order_and_lookup(self):
        self.assertEqual([p.key for p in all_packs()], ["python", "java", "javascript"])
        self.assertEqual(pack_for_path(r"C:\x\Main.JAVA").key, "java")
        self.assertEqual(pack_for_path("page.html").key, "javascript")
        self.assertIsNone(pack_for_path("notes.txt"))

    def test_python_pack_matches_old_analyser(self):
        src = (FIXTURES / "python" / "loops.py").read_text(encoding="utf-8")
        result = get_pack("python").analyze(src, str(FIXTURES / "python" / "loops.py"))
        self.assertTrue(result["syntax_ok"])
        self.assertIn("for_loop", result["topics"])
        self.assertIn("while_loop", result["topics"])

    def test_python_syntax_error(self):
        result = get_pack("python").analyze("def broken(:\n")
        self.assertFalse(result["syntax_ok"])
        self.assertEqual(result["topics"], [])

    def test_python_curriculum_unchanged(self):
        cur = get_pack("python").curriculum()
        self.assertEqual(len(cur["levels"]), 9)
        self.assertEqual(sum(l["days"]["standard"] for l in cur["levels"]), 132)


if __name__ == "__main__":
    unittest.main()
