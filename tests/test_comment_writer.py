import unittest
from unittest.mock import Mock
from pathlib import Path
from tempfile import TemporaryDirectory

from src.skills.comment_writer_skill import CommentWriterSkill


class CommentWriterSkillTests(unittest.TestCase):
    def test_generates_grounded_vietnamese_comment(self):
        with TemporaryDirectory() as directory:
            examples_file = Path(directory) / "examples.txt"
            examples_file.write_text(
                "# ghi chú\n"
                "Nhóm hoạt động tốt, cứ thế phát huy.\n"
                "\n",
                encoding="utf-8",
            )
            llm = Mock()
            llm.generate.return_value = "Nhóm hoạt động tốt, cứ thế phát huy."
            skill = CommentWriterSkill(
                llm_client=llm,
                examples_file=examples_file,
            )

            comment = skill.write_comment(
                {
                    "group_id": "G1",
                    "topic": "Session 28",
                    "transcript_available": False,
                }
            )

            self.assertEqual(
                comment,
                "Nhóm hoạt động tốt, cứ thế phát huy.",
            )
            call = llm.generate.call_args.kwargs
            self.assertIn("không nhắc đến hệ thống", call["instructions"])
            self.assertIn(
                "Nhóm hoạt động tốt, cứ thế phát huy.",
                call["instructions"],
            )
            self.assertNotIn("# ghi chú", call["instructions"])
            self.assertIn('"group_id": "G1"', call["input_text"])


if __name__ == "__main__":
    unittest.main()
