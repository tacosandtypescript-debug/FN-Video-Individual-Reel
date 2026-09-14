"""Checks the repository layout and activation contract expected by Hermes."""
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parents[1]


class HermesPackageTest(unittest.TestCase):
    def test_skill_is_under_hermes_tap_directory(self):
        self.assertEqual(SKILL_DIR.name, "vertical-video-editor")
        self.assertEqual(SKILL_DIR.parent.name, "skills")
        self.assertTrue((SKILL_DIR / "SKILL.md").is_file())
        self.assertTrue((SKILL_DIR / "scripts").is_dir())
        self.assertTrue((SKILL_DIR / "references").is_dir())

    def test_frontmatter_exposes_video_command(self):
        content = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = content.split("---", 2)[1]
        self.assertRegex(frontmatter, r"(?m)^name:\s+video\s*$")
        self.assertRegex(frontmatter, r"(?m)^description:\s+\"[^\"]+\"\s*$")
        self.assertIn("tags:", frontmatter)
        self.assertIn("/video", content)

    def test_old_root_skill_is_not_used_as_the_tap_entrypoint(self):
        self.assertFalse((REPO_ROOT / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
