from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from src.skills.group_roster_skill import GroupRosterSkill


class GroupRosterSkillTests(unittest.TestCase):
    def test_reads_group_size_from_class_file(self):
        with TemporaryDirectory() as directory:
            class_dir = Path(directory)
            folder = class_dir / "HN-KS25-CNTT4"
            folder.mkdir()
            (folder / "HN-KS25-CNTT4.txt").write_text(
                "G1: 5 Sinh viên\nG2: 6 Sinh viên\nG3: 7 Sinh viên\n",
                encoding="utf-8",
            )
            skill = GroupRosterSkill(
                config=SimpleNamespace(CLASS_DIR=class_dir)
            )

            result = skill.expected_speakers("HN-KS25-CNTT4-G3")

            self.assertEqual(result, 7)

    def test_returns_none_for_missing_class_file(self):
        with TemporaryDirectory() as directory:
            skill = GroupRosterSkill(
                config=SimpleNamespace(CLASS_DIR=Path(directory))
            )
            self.assertIsNone(
                skill.expected_speakers("HN-K25-CNTT3-G3")
            )


if __name__ == "__main__":
    unittest.main()
