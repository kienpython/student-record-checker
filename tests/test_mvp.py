from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from pathlib import Path

from src.agent import (
    Agent,
    CHECKED_STATUS,
    ERROR_STATUS,
    INCOMPLETE_PARTICIPATION_COMMENT,
    MISSING_ROSTER_COMMENT,
    NO_RECORD_COMMENT,
    NOT_YOUTUBE_COMMENT,
)
from src.skills.read_lark_base_skill import ReadLarkBaseSkill
from src.skills.update_lark_base_skill import UpdateLarkBaseSkill


class FakeResponse:
    def __init__(self, body):
        self._body = body
        self.ok = True
        self.status_code = 200
        self.text = ""

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


def make_config():
    return SimpleNamespace(
        LARK_APP_ID="app-id",
        LARK_APP_SECRET="secret",
        LARK_APP_TOKEN="base-token",
        LARK_TABLE_ID="table-id",
        LARK_VIEW_ID="view-id",
        LARK_API_BASE="https://open.larksuite.com/open-apis",
        CACHE_TRANSCRIPTS=Path("cache/transcripts"),
        TOPIC_RULES_FILE=Path("data/topic_rules.txt"),
        ALLOWED_TOPICS_FILE=Path("data/allowed_topics.txt"),
        WHISPER_MODEL="base",
        WHISPER_COMPUTE_TYPE="int8",
        TRANSCRIPT_MAX_CHARS=12000,
    )


class ReadSkillTests(unittest.TestCase):
    def test_reads_pending_records_and_sends_pagination_as_query_params(self):
        session = Mock()
        session.post.return_value = FakeResponse(
            {
                "code": 0,
                "data": {
                    "items": [
                        {
                            "record_id": "rec1",
                            "fields": {"Trạng thái": "Chưa kiểm tra"},
                        }
                    ],
                    "has_more": False,
                },
            }
        )
        auth = Mock()
        auth.get_headers.return_value = {"Authorization": "Bearer token"}
        skill = ReadLarkBaseSkill(
            config=make_config(),
            auth=auth,
            session=session,
        )

        records = skill.fetch_records(limit=1)

        self.assertEqual(records[0]["record_id"], "rec1")
        call = session.post.call_args
        self.assertEqual(call.kwargs["params"]["page_size"], 1)
        self.assertEqual(call.kwargs["json"]["view_id"], "view-id")
        condition = call.kwargs["json"]["filter"]["conditions"][0]
        self.assertEqual(condition["field_name"], "Trạng thái")
        self.assertEqual(condition["value"], ["Đã kiểm tra"])

    def test_extracts_text_and_attachment_shapes(self):
        self.assertEqual(
            ReadLarkBaseSkill.extract_text([{"text": "https://youtu.be/test"}]),
            "https://youtu.be/test",
        )
        attachments = ReadLarkBaseSkill.extract_attachments(
            [{"file_token": "file-token", "name": "record.mp4"}]
        )
        self.assertEqual(attachments[0]["file_token"], "file-token")


class UpdateSkillTests(unittest.TestCase):
    def test_updates_only_comment_and_status(self):
        session = Mock()
        session.put.return_value = FakeResponse({"code": 0, "data": {}})
        auth = Mock()
        auth.get_headers.return_value = {"Authorization": "Bearer token"}
        skill = UpdateLarkBaseSkill(
            config=make_config(),
            auth=auth,
            session=session,
        )

        skill.update_record(
            record_id="rec1",
            comment="Ổn",
            status="Đã kiểm tra",
        )

        payload = session.put.call_args.kwargs["json"]
        self.assertEqual(
            payload,
            {"fields": {"Nhận xét": "Ổn", "Trạng thái": "Đã kiểm tra"}},
        )

    def test_exposes_lark_error_details(self):
        session = Mock()
        response = FakeResponse(
            {
                "code": 99991672,
                "msg": "Access denied. Scope base:record:update is required.",
            }
        )
        response.ok = False
        response.status_code = 403
        session.put.return_value = response
        skill = UpdateLarkBaseSkill(
            config=make_config(),
            auth=Mock(get_headers=Mock(return_value={})),
            session=session,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "base:record:update",
        ):
            skill.update_record(
                record_id="rec1",
                comment="Ổn",
                status="Đã kiểm tra",
            )


class AgentTests(unittest.TestCase):
    def test_live_run_updates_all_returned_records(self):
        read_skill = Mock()
        read_skill.fetch_records.return_value = [
            {
                "record_id": "rec1",
                "fields": {
                    "Group ID": "G1",
                    "Record": "https://youtu.be/one",
                    "Trạng thái": "",
                },
            },
            {
                "record_id": "rec2",
                "fields": {
                    "Group ID": "G2",
                    "Record": "https://youtu.be/two",
                    "Trạng thái": "Lỗi kiểm tra",
                },
            },
        ]
        read_skill.extract_text.side_effect = ReadLarkBaseSkill.extract_text
        read_skill.extract_attachments.side_effect = (
            ReadLarkBaseSkill.extract_attachments
        )
        update_skill = Mock()
        comment_writer = Mock()
        comment_writer.write_comment.return_value = "Nhận xét do AI tạo."
        roster_skill = Mock()
        roster_skill.expected_speakers.return_value = 5
        download_skill = Mock()
        download_skill.download.return_value = Path("audio.wav")
        speaker_skill = Mock()
        speaker_skill.detect_speakers.return_value = 5
        transcribe_skill = Mock()
        transcribe_skill.transcribe.return_value = "Nội dung thảo luận."
        topic_judge_skill = Mock()
        topic_judge_skill.judge.return_value = {"matches_topic": True}
        logger = Mock()

        agent = Agent(
            logger=logger,
            config=make_config(),
            auth=Mock(),
            read_skill=read_skill,
            update_skill=update_skill,
            comment_writer=comment_writer,
            roster_skill=roster_skill,
            download_audio_skill=download_skill,
            speaker_detect_skill=speaker_skill,
            transcribe_skill=transcribe_skill,
            topic_judge_skill=topic_judge_skill,
        )
        agent.run(
            topic="Session 28",
            expected_speakers=5,
            limit=2,
            dry_run=False,
        )

        self.assertEqual(update_skill.update_record.call_count, 2)
        update_skill.update_record.assert_any_call(
            record_id="rec1",
            comment="Nhận xét do AI tạo.",
            status=CHECKED_STATUS,
            dry_run=False,
        )
        update_skill.update_record.assert_any_call(
            record_id="rec2",
            comment="Nhận xét do AI tạo.",
            status=CHECKED_STATUS,
            dry_run=False,
        )

    def test_ai_error_is_written_back_as_short_lark_error(self):
        read_skill = Mock()
        read_skill.fetch_records.return_value = [
            {
                "record_id": "rec1",
                "fields": {
                    "Group ID": "G1",
                    "Record": "https://youtu.be/one",
                    "Trạng thái": "",
                },
            }
        ]
        read_skill.extract_text.side_effect = ReadLarkBaseSkill.extract_text
        read_skill.extract_attachments.side_effect = (
            ReadLarkBaseSkill.extract_attachments
        )
        comment_writer = Mock()
        comment_writer.write_comment.side_effect = RuntimeError(
            "Gemini API đã chạm giới hạn free tier; vui lòng thử lại sau."
        )
        roster_skill = Mock()
        roster_skill.expected_speakers.return_value = 5
        download_skill = Mock()
        download_skill.download.return_value = Path("audio.wav")
        speaker_skill = Mock()
        speaker_skill.detect_speakers.return_value = 5
        transcribe_skill = Mock()
        transcribe_skill.transcribe.return_value = "Nội dung thảo luận."
        topic_judge_skill = Mock()
        topic_judge_skill.judge.return_value = {"matches_topic": True}
        update_skill = Mock()
        agent = Agent(
            logger=Mock(),
            config=make_config(),
            auth=Mock(),
            read_skill=read_skill,
            update_skill=update_skill,
            comment_writer=comment_writer,
            roster_skill=roster_skill,
            download_audio_skill=download_skill,
            speaker_detect_skill=speaker_skill,
            transcribe_skill=transcribe_skill,
            topic_judge_skill=topic_judge_skill,
        )

        agent.run(
            topic="Session 28",
            expected_speakers=5,
            limit=1,
            dry_run=False,
            speaker_check=True,
        )

        update_skill.update_record.assert_called_once_with(
            record_id="rec1",
            comment=(
                "Không thể kiểm tra record: Gemini API đã chạm "
                "giới hạn free tier; vui lòng thử lại sau."
            ),
            status=ERROR_STATUS,
            dry_run=False,
        )

    def test_non_youtube_record_is_not_sent_to_ai(self):
        read_skill = Mock()
        read_skill.fetch_records.return_value = [
            {
                "record_id": "rec-drive",
                "fields": {
                    "Group ID": "G2",
                    "Record": "https://drive.google.com/file/d/test/view",
                    "Trạng thái": "",
                },
            }
        ]
        read_skill.extract_text.side_effect = ReadLarkBaseSkill.extract_text
        read_skill.extract_attachments.side_effect = (
            ReadLarkBaseSkill.extract_attachments
        )
        comment_writer = Mock()
        update_skill = Mock()
        agent = Agent(
            logger=Mock(),
            config=make_config(),
            auth=Mock(),
            read_skill=read_skill,
            update_skill=update_skill,
            comment_writer=comment_writer,
        )

        agent.run(
            topic="Session 28",
            expected_speakers=5,
            limit=1,
            dry_run=False,
            speaker_check=True,
        )

        comment_writer.write_comment.assert_not_called()
        update_skill.update_record.assert_called_once_with(
            record_id="rec-drive",
            comment=NOT_YOUTUBE_COMMENT,
            status=CHECKED_STATUS,
            dry_run=False,
        )

    def test_youtube_link_without_scheme_is_recognized(self):
        self.assertTrue(
            Agent._is_youtube_link(
                "youtube.com/watch?si=test&v=6CT3F5lgEfU"
            )
        )
        self.assertTrue(Agent._is_youtube_link("youtu.be/6CT3F5lgEfU"))
        self.assertFalse(Agent._is_youtube_link("example.com/video"))

    def test_insufficient_speakers_gets_participation_comment(self):
        read_skill = Mock()
        read_skill.fetch_records.return_value = [
            {
                "record_id": "rec-group",
                "fields": {
                    "Group ID": "HN-KS25-CNTT4-G3",
                    "Record": "youtube.com/watch?v=test",
                    "Trạng thái": "",
                },
            }
        ]
        read_skill.extract_text.side_effect = ReadLarkBaseSkill.extract_text
        read_skill.extract_attachments.side_effect = (
            ReadLarkBaseSkill.extract_attachments
        )
        roster_skill = Mock()
        roster_skill.expected_speakers.return_value = 7
        download_skill = Mock()
        download_skill.download.return_value = Path("audio.wav")
        speaker_skill = Mock()
        speaker_skill.detect_speakers.return_value = 4
        transcribe_skill = Mock()
        transcribe_skill.transcribe.return_value = "Nội dung thảo luận."
        topic_judge_skill = Mock()
        topic_judge_skill.judge.return_value = {"matches_topic": True}
        comment_writer = Mock()
        update_skill = Mock()
        agent = Agent(
            logger=Mock(),
            config=make_config(),
            auth=Mock(),
            read_skill=read_skill,
            update_skill=update_skill,
            comment_writer=comment_writer,
            roster_skill=roster_skill,
            download_audio_skill=download_skill,
            speaker_detect_skill=speaker_skill,
            transcribe_skill=transcribe_skill,
            topic_judge_skill=topic_judge_skill,
        )

        agent.run(
            topic="Session 28",
            expected_speakers=0,
            limit=1,
            dry_run=False,
            speaker_check=True,
        )

        comment_writer.write_comment.assert_not_called()
        update_skill.update_record.assert_called_once_with(
            record_id="rec-group",
            comment=INCOMPLETE_PARTICIPATION_COMMENT,
            status=CHECKED_STATUS,
            dry_run=False,
        )

    def test_missing_roster_does_not_use_cli_expected_speakers(self):
        read_skill = Mock()
        read_skill.fetch_records.return_value = [
            {
                "record_id": "rec-no-roster",
                "fields": {
                    "Group ID": "HN-K25-CNTT3-G3",
                    "Record": "youtube.com/watch?v=test",
                    "Trạng thái": "",
                },
            }
        ]
        read_skill.extract_text.side_effect = ReadLarkBaseSkill.extract_text
        read_skill.extract_attachments.side_effect = (
            ReadLarkBaseSkill.extract_attachments
        )
        roster_skill = Mock()
        roster_skill.expected_speakers.return_value = None
        download_skill = Mock()
        speaker_skill = Mock()
        update_skill = Mock()
        agent = Agent(
            logger=Mock(),
            config=make_config(),
            auth=Mock(),
            read_skill=read_skill,
            update_skill=update_skill,
            roster_skill=roster_skill,
            download_audio_skill=download_skill,
            speaker_detect_skill=speaker_skill,
        )

        agent.run(
            topic="Session 28",
            expected_speakers=5,
            limit=1,
            dry_run=False,
            speaker_check=True,
        )

        download_skill.download.assert_not_called()
        speaker_skill.detect_speakers.assert_not_called()
        update_skill.update_record.assert_called_once_with(
            record_id="rec-no-roster",
            comment=MISSING_ROSTER_COMMENT,
            status=ERROR_STATUS,
            dry_run=False,
        )

    def test_only_no_is_a_missing_record_marker(self):
        self.assertFalse(Agent._is_missing_record(""))
        self.assertTrue(Agent._is_missing_record(" NO "))
        self.assertFalse(Agent._is_missing_record("example.com/video"))
        self.assertEqual(
            NO_RECORD_COMMENT,
            "Không có link record để kiểm tra.",
        )

    def test_unavailable_youtube_error_is_short(self):
        self.assertEqual(
            Agent._short_error(
                RuntimeError(
                    "Không tải được audio YouTube: "
                    "ERROR: This video is not available"
                )
            ),
            "Không thể truy cập video YouTube để kiểm tra.",
        )

    def test_blank_record_is_skipped_without_update(self):
        read_skill = Mock()
        read_skill.fetch_records.return_value = [
            {
                "record_id": "rec-empty",
                "fields": {
                    "Group ID": "G3",
                    "Record": "",
                    "Trạng thái": "",
                },
            }
        ]
        read_skill.extract_text.side_effect = ReadLarkBaseSkill.extract_text
        read_skill.extract_attachments.side_effect = (
            ReadLarkBaseSkill.extract_attachments
        )
        comment_writer = Mock()
        update_skill = Mock()
        agent = Agent(
            logger=Mock(),
            config=make_config(),
            auth=Mock(),
            read_skill=read_skill,
            update_skill=update_skill,
            comment_writer=comment_writer,
        )

        agent.run(
            topic="Session 28",
            expected_speakers=5,
            limit=1,
            dry_run=False,
        )

        comment_writer.write_comment.assert_not_called()
        update_skill.update_record.assert_not_called()


if __name__ == "__main__":
    unittest.main()
