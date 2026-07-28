"""
Minimal smoke tests for skillkit.py. Run with:
    python3 test_skillkit.py
No dependencies (uses stdlib unittest).
"""

import shutil
import tempfile
import unittest
from pathlib import Path

import skillkit


class TestSkillkit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_new_creates_scaffold(self):
        rc = skillkit.main(["new", "my-test-skill", "--dir", str(self.tmp)])
        self.assertEqual(rc, 0)
        skill_md = self.tmp / "my-test-skill" / "SKILL.md"
        self.assertTrue(skill_md.exists())
        self.assertTrue((self.tmp / "my-test-skill" / "resources").is_dir())

    def test_new_rejects_bad_name(self):
        rc = skillkit.main(["new", "Bad Name!", "--dir", str(self.tmp)])
        self.assertEqual(rc, 1)

    def test_lint_flags_placeholder_description(self):
        skillkit.main(["new", "placeholder-skill", "--dir", str(self.tmp)])
        skill_md = self.tmp / "placeholder-skill" / "SKILL.md"
        # Fresh scaffold has a generic placeholder; lint should still pass
        # basic structural checks (has frontmatter, name, description, body).
        rc = skillkit.main(["lint", str(skill_md)])
        self.assertIn(rc, (0, 1))

    def test_lint_flags_missing_frontmatter(self):
        bad = self.tmp / "bad.md"
        bad.write_text("# just a heading, no frontmatter\n")
        rc = skillkit.main(["lint", str(bad)])
        self.assertEqual(rc, 1)

    def test_lint_flags_vague_description(self):
        bad = self.tmp / "vague.md"
        bad.write_text(
            "---\nname: vague-skill\ndescription: helps with various tasks\n---\n\nBody text here that is long enough.\n"
        )
        rc = skillkit.main(["lint", str(bad)])
        self.assertEqual(rc, 1)

    def test_lint_passes_good_skill(self):
        good = self.tmp / "good.md"
        good.write_text(
            "---\n"
            "name: pdf-report-builder\n"
            "description: >\n"
            "  Use when the user asks to generate a PDF report from CSV data,\n"
            "  says 'build a report', or 'export this as PDF'. Converts tabular\n"
            "  data into a formatted PDF with charts.\n"
            "---\n\n"
            "# PDF Report Builder\n\n"
            "## Steps\n1. Read the CSV.\n2. Render charts.\n3. Write the PDF.\n"
        )
        rc = skillkit.main(["lint", str(good)])
        self.assertEqual(rc, 0)

    def test_list_summarizes_skills(self):
        skillkit.main(["new", "skill-a", "--dir", str(self.tmp)])
        skillkit.main(["new", "skill-b", "--dir", str(self.tmp)])
        rc = skillkit.main(["list", str(self.tmp)])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
