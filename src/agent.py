"""Agent orchestrating the Lark Base record checking workflow."""

import logging
import re
from datetime import datetime
from typing import Any

from .config import config as default_config
from .lark_auth import LarkAuth
from .llm_client import LLMClient
from .memory import Memory
from .skills.comment_writer_skill import CommentWriterSkill
from .skills.download_audio_skill import DownloadAudioSkill
from .skills.group_roster_skill import GroupRosterSkill
from .skills.read_lark_base_skill import ReadLarkBaseSkill
from .skills.speaker_detect_skill import SpeakerDetectSkill
from .skills.topic_judge_skill import TopicJudgeSkill
from .skills.transcribe_skill import TranscribeSkill
from .skills.update_lark_base_skill import UpdateLarkBaseSkill


CHECKED_STATUS = "Đã kiểm tra"
ERROR_STATUS = "Lỗi kiểm tra"
NO_RECORD_COMMENT = "Không có link record để kiểm tra."
NOT_YOUTUBE_COMMENT = "Không phải link YouTube để kiểm tra."
MISSING_ROSTER_COMMENT = "Không tìm thấy sĩ số của nhóm để kiểm tra."
INCOMPLETE_PARTICIPATION_COMMENT = (
    "Nhóm cần đảm bảo toàn bộ thành viên cùng tham gia hoạt động nhóm nhé."
)
YOUTUBE_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/",
    re.IGNORECASE,
)


class Agent:
    def __init__(
        self,
        *,
        logger: logging.Logger,
        config: Any = default_config,
        auth: LarkAuth | None = None,
        read_skill: ReadLarkBaseSkill | None = None,
        update_skill: UpdateLarkBaseSkill | None = None,
        comment_writer: CommentWriterSkill | None = None,
        roster_skill: GroupRosterSkill | None = None,
        download_audio_skill: DownloadAudioSkill | None = None,
        speaker_detect_skill: SpeakerDetectSkill | None = None,
        transcribe_skill: TranscribeSkill | None = None,
        topic_judge_skill: TopicJudgeSkill | None = None,
        memory: Memory | None = None,
    ) -> None:
        self.logger = logger
        self.config = config
        self.memory = memory or Memory()
        self.auth = auth or LarkAuth(
            config.LARK_APP_ID,
            config.LARK_APP_SECRET,
            logger=logger,
        )
        self.read_skill = read_skill or ReadLarkBaseSkill(
            config=config,
            auth=self.auth,
            logger=logger,
        )
        self.update_skill = update_skill or UpdateLarkBaseSkill(
            config=config,
            auth=self.auth,
            logger=logger,
        )
        self.comment_writer = comment_writer
        self.roster_skill = roster_skill
        self.download_audio_skill = download_audio_skill
        self.speaker_detect_skill = speaker_detect_skill
        self.transcribe_skill = transcribe_skill
        self.topic_judge_skill = topic_judge_skill

    def _get_llm_client(self) -> LLMClient:
        return LLMClient(config=self.config, logger=self.logger)

    def _get_comment_writer(self) -> CommentWriterSkill:
        if self.comment_writer is None:
            self.comment_writer = CommentWriterSkill(
                llm_client=self._get_llm_client(),
                logger=self.logger,
            )
        return self.comment_writer

    def _get_roster_skill(self) -> GroupRosterSkill:
        if self.roster_skill is None:
            self.roster_skill = GroupRosterSkill(
                config=self.config,
                logger=self.logger,
            )
        return self.roster_skill

    def _get_download_audio_skill(self) -> DownloadAudioSkill:
        if self.download_audio_skill is None:
            self.download_audio_skill = DownloadAudioSkill(
                config=self.config,
                logger=self.logger,
            )
        return self.download_audio_skill

    def _get_speaker_detect_skill(self) -> SpeakerDetectSkill:
        if self.speaker_detect_skill is None:
            self.speaker_detect_skill = SpeakerDetectSkill(
                config=self.config,
                logger=self.logger,
            )
        return self.speaker_detect_skill

    def _get_transcribe_skill(self) -> TranscribeSkill:
        if self.transcribe_skill is None:
            self.transcribe_skill = TranscribeSkill(
                config=self.config,
                logger=self.logger,
            )
        return self.transcribe_skill

    def _get_topic_judge_skill(self) -> TopicJudgeSkill:
        if self.topic_judge_skill is None:
            self.topic_judge_skill = TopicJudgeSkill(
                llm_client=self._get_llm_client(),
                config=self.config,
                logger=self.logger,
            )
        return self.topic_judge_skill

    def run(
        self,
        *,
        topic: str,
        expected_speakers: int,
        limit: int = 10,
        dry_run: bool = False,
        speaker_check: bool = False,
    ) -> None:
        """Process every pending record returned within the requested limit."""
        self.logger.info(
            "MVP bắt đầu | topic=%r | expected_speakers=%d | limit=%d | "
            "dry_run=%s | speaker_check=%s",
            topic,
            expected_speakers,
            limit,
            dry_run,
            speaker_check,
        )
        self._reset_youtube_content_file(
            topic=topic,
            limit=limit,
            dry_run=dry_run,
            speaker_check=speaker_check,
        )
        records = self.read_skill.fetch_records(limit=limit)
        if not records:
            self.logger.info("Không có record nào cần xử lý.")
            return

        for index, record in enumerate(records, start=1):
            record_id = str(record.get("record_id") or "")
            fields = record.get("fields") or {}
            group_id = self.read_skill.extract_text(fields.get("Group ID"))
            record_value = fields.get("Record")
            record_text = self.read_skill.extract_text(record_value)
            if not record_text and self.read_skill.extract_attachments(record_value):
                record_text = "[Lark attachment]"
            status = self.read_skill.extract_text(fields.get("Trạng thái"))
            report_summary = self.read_skill.extract_text(
                fields.get("Tóm tắt báo cáo")
            )

            self.logger.info(
                "[%d] Group ID=%r | Record=%r | Trạng thái=%r | record_id=%s",
                index,
                group_id,
                record_text,
                status,
                record_id,
            )

            if not record_id or self.memory.contains(record_id):
                self.logger.warning("Bỏ qua record thiếu/trùng record_id: %r", record_id)
                continue

            if self._is_blank_record(record_text):
                self.logger.info(
                    "Bỏ qua record %s vì field Record đang trống.",
                    record_id,
                )
                self.memory.remember(record_id, action="skipped-empty-record")
                continue

            try:
                comment, result_status = self._process_record(
                    record_id=record_id,
                    group_id=group_id,
                    record_text=record_text,
                    report_summary=report_summary,
                    topic=topic,
                    speaker_check=speaker_check,
                )
                self.update_skill.update_record(
                    record_id=record_id,
                    comment=comment,
                    status=result_status,
                    dry_run=dry_run,
                )
                self.memory.remember(
                    record_id,
                    action="dry-run" if dry_run else "updated",
                    comment=comment,
                )
            except Exception as exc:
                error_comment = self._short_error(exc)
                self.logger.error(
                    "Xử lý record %s thất bại: %s",
                    record_id,
                    error_comment,
                )
                try:
                    self.update_skill.update_record(
                        record_id=record_id,
                        comment=error_comment,
                        status=ERROR_STATUS,
                        dry_run=dry_run,
                    )
                    self.memory.remember(
                        record_id,
                        action="dry-run-error" if dry_run else "error-updated",
                        error=error_comment,
                    )
                except Exception as update_exc:
                    self.memory.remember(
                        record_id,
                        action="update-error",
                        error=str(update_exc),
                    )
                    self.logger.error(
                        "Không thể ghi lỗi vào Lark record %s: %s",
                        record_id,
                        self._short_error(update_exc),
                    )

        self.logger.info("MVP hoàn tất; đã ghi nhớ %d record.", self.memory.count())

    def _process_record(
        self,
        *,
        record_id: str,
        group_id: str,
        record_text: str,
        report_summary: str,
        topic: str,
        speaker_check: bool,
    ) -> tuple[str, str]:
        if self._is_missing_record(record_text):
            self.logger.info("Record %s không có link; bỏ qua Gemini.", record_id)
            return NO_RECORD_COMMENT, CHECKED_STATUS

        if not self._is_youtube_link(record_text):
            self.logger.info(
                "Record %s không phải link YouTube; bỏ qua Gemini.",
                record_id,
            )
            return NOT_YOUTUBE_COMMENT, CHECKED_STATUS

        roster_count: int | None = None
        if speaker_check:
            roster_count = self._get_roster_skill().expected_speakers(group_id)
            if roster_count is None:
                return MISSING_ROSTER_COMMENT, ERROR_STATUS

        transcribe_skill = self._get_transcribe_skill()
        transcript = transcribe_skill.transcribe_youtube(record_text, record_id)
        audio_path = None
        if transcript is None or speaker_check:
            audio_path = self._get_download_audio_skill().download(record_text, record_id)
        if transcript is None:
            if not getattr(self.config, "ENABLE_WHISPER_FALLBACK", False):
                raise RuntimeError(
                    "Không lấy được caption YouTube để tạo transcript. "
                    "Nếu muốn dùng Whisper local, bật ENABLE_WHISPER_FALLBACK=true."
                )
            transcript = transcribe_skill.transcribe(audio_path, record_id)
        self._append_youtube_content(
            record_id=record_id,
            group_id=group_id,
            url=record_text,
            transcript=transcript,
        )
        topic_judgment = self._get_topic_judge_skill().judge(transcript, topic)
        analysis: dict[str, Any] = {
            "đề_bài": topic,
            "đánh_giá_nội_dung": topic_judgment,
            "tóm_tắt_báo_cáo": report_summary or "Không có thông tin.",
        }

        if speaker_check:
            detected_speakers = self._get_speaker_detect_skill().detect_speakers(
                audio_path,
                record_id,
            )
            analysis.update(
                {
                    "số_thành_viên": roster_count,
                    "số_giọng_nói_phát_hiện": detected_speakers,
                    "đủ_thành_viên_tham_gia": detected_speakers >= roster_count,
                }
            )
            if detected_speakers < roster_count:
                return INCOMPLETE_PARTICIPATION_COMMENT, CHECKED_STATUS

        return self._get_comment_writer().write_comment(analysis), CHECKED_STATUS

    @staticmethod
    def _short_error(exc: Exception, limit: int = 300) -> str:
        message = " ".join(str(exc).split()).strip()
        if not message:
            message = exc.__class__.__name__
        if "video is not available" in message.lower():
            return "Không thể truy cập video YouTube để kiểm tra."
        return f"Không thể kiểm tra record: {message}"[:limit]

    def _reset_youtube_content_file(
        self,
        *,
        topic: str,
        limit: int,
        dry_run: bool,
        speaker_check: bool,
    ) -> None:
        path = getattr(self.config, "YOUTUBE_CONTENT_FILE", None)
        if not path:
            return

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "YouTube content used by Student Record Checker\n"
                f"Run time: {datetime.now().isoformat(timespec='seconds')}\n"
                f"Topic: {topic}\n"
                f"Limit: {limit}\n"
                f"Dry run: {dry_run}\n"
                f"Speaker check: {speaker_check}\n",
                encoding="utf-8",
            )
        except Exception as exc:
            self.logger.warning("Không thể reset file youtube_content.txt: %s", exc)

    def _append_youtube_content(
        self,
        *,
        record_id: str,
        group_id: str,
        url: str,
        transcript: str,
    ) -> None:
        path = getattr(self.config, "YOUTUBE_CONTENT_FILE", None)
        if not path:
            return

        try:
            with path.open("a", encoding="utf-8") as file:
                file.write(
                    "\n\n"
                    + "=" * 80
                    + "\n"
                    f"record_id: {record_id}\n"
                    f"group_id: {group_id}\n"
                    f"url: {url}\n"
                    f"transcript_chars: {len(transcript)}\n"
                    + "-" * 80
                    + "\n"
                    + transcript.strip()
                    + "\n"
                )
            self.logger.info("Đã ghi YouTube transcript vào %s.", path)
        except Exception as exc:
            self.logger.warning("Không thể ghi file youtube_content.txt: %s", exc)

    @staticmethod
    def _is_youtube_link(value: str) -> bool:
        return bool(YOUTUBE_PATTERN.match(value.strip()))

    @staticmethod
    def _is_missing_record(value: str) -> bool:
        return value.strip().lower() == "no"

    @staticmethod
    def _is_blank_record(value: str) -> bool:
        return not value.strip()
