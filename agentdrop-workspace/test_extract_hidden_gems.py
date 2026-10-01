"""python3 -m unittest -q test_extract_hidden_gems"""
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location("gems", os.path.join(os.path.dirname(__file__), "extract_hidden_gems.py"))
gems = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gems)


class ExtractGems(unittest.TestCase):
    def test_keywords_match_whole_words_only(self):
        # 'api' inside 'rapid'/'capital', 'node' inside 'anode', 'learn' inside 'unlearned', 'repo' inside 'report'
        text = "This rapid growth needs capital and patience. The anode corroded. He unlearned it. Read the report."
        self.assertEqual(gems.extract_gems(text), [])

    def test_real_keywords_still_found(self):
        out = gems.extract_gems("Check out this GitHub repo for agents. It uses the OpenAI API in Python.")
        self.assertEqual(len(out), 2)

    def test_db_path_points_at_the_live_command_center_db(self):
        self.assertTrue(gems.DB_PATH.endswith("command-center/mission-control/data/mission.db"), gems.DB_PATH)
        self.assertTrue(os.path.exists(gems.DB_PATH), gems.DB_PATH)

    def test_report_uses_real_newlines(self):
        src = open(os.path.join(os.path.dirname(__file__), "extract_hidden_gems.py")).read()
        self.assertNotIn('\\\\n', src, "report text writes a literal backslash-n instead of a newline")


if __name__ == "__main__":
    unittest.main()
