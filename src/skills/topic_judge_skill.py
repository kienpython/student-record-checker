"""Skill to judge whether a transcript matches the expected topic."""

import json
import logging
from pathlib import Path
from typing import Any

from ..config import config as default_config


class TopicJudgeSkill:
    """Uses an LLM to evaluate transcript content against allowed topics."""

    def __init__(
        self,
        *,
        llm_client: Any | None = None,
        logger: logging.Logger | None = None,
        config: Any = default_config,
        topic_rules_file: Path | None = None,
        allowed_topics_file: Path | None = None,
    ) -> None:
        self.llm = llm_client
        self.logger = logger or logging.getLogger(__name__)
        self.config = config
        self.topic_rules_file = topic_rules_file or config.TOPIC_RULES_FILE
        self.allowed_topics_file = allowed_topics_file or config.ALLOWED_TOPICS_FILE

    def judge(self, transcript: str, topic: str) -> dict[str, Any]:
        """Return a compact structured judgment for comment generation."""
        if self.llm is None:
            raise RuntimeError("TopicJudgeSkill cần llm_client để đánh giá transcript.")

        instructions = (
            "Bạn là trợ giảng đang kiểm tra transcript buổi thảo luận nhóm. "
            "Mục tiêu chính là kiểm tra tương đối xem nội dung có giống một buổi "
            "thảo luận/làm bài tập nhóm thật hay không. Không yêu cầu khớp tuyệt đối "
            "từng keyword với đề hiện tại. Hãy coi là hợp lệ nếu transcript có trao đổi "
            "qua lại về bài tập, code, sửa lỗi, phân tích yêu cầu, chia việc, review bài, "
            "test/unit test, logging, validate dữ liệu hoặc tiến độ làm bài. "
            "Chỉ đánh dấu nộp nhầm/file cũ khi nội dung hoàn toàn không liên quan tới "
            "học tập, bài tập, lập trình hoặc chỉ nói chuyện ngoài lề. "
            "matches_topic có thể false nếu lệch đề chi tiết, nhưng is_group_work_discussion "
            "vẫn phải true nếu đó là một buổi làm bài/thảo luận nhóm thật. "
            "Chỉ trả về JSON hợp lệ, không Markdown, không giải thích ngoài JSON. "
            "Schema JSON: {"
            '"is_group_work_discussion": boolean, '
            '"has_discussion": boolean, '
            '"matches_topic": boolean, '
            '"topic_match_level": "cao"|"tương đối"|"thấp", '
            '"suspected_old_or_wrong_file": boolean, '
            '"has_quiz_mindmap_or_summary": boolean, '
            '"participation_level": "tốt"|"trung bình"|"yếu", '
            '"summary": string, '
            '"suggestion": string'
            "}."
        )
        input_text = json.dumps(
            {
                "topic_hien_tai": topic,
                "tieu_chi": self._read_optional_file(self.topic_rules_file),
                "chu_de_hop_le": self._read_optional_file(self.allowed_topics_file),
                "transcript": transcript[: self.config.TRANSCRIPT_MAX_CHARS],
            },
            ensure_ascii=False,
            indent=2,
        )
        raw = self.llm.generate(instructions=instructions, input_text=input_text)
        cleaned_raw = self._clean_json_text(raw)
        try:
            result = json.loads(cleaned_raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Gemini trả về kết quả đánh giá không phải JSON: {raw[:200]}"
            ) from exc

        return {
            "is_group_work_discussion": bool(result.get("is_group_work_discussion")),
            "has_discussion": bool(result.get("has_discussion")),
            "matches_topic": bool(result.get("matches_topic")),
            "topic_match_level": str(result.get("topic_match_level") or "tương đối"),
            "suspected_old_or_wrong_file": bool(
                result.get("suspected_old_or_wrong_file")
            ),
            "has_quiz_mindmap_or_summary": bool(
                result.get("has_quiz_mindmap_or_summary")
            ),
            "participation_level": str(result.get("participation_level") or "trung bình"),
            "summary": str(result.get("summary") or ""),
            "suggestion": str(result.get("suggestion") or ""),
        }

    def _read_optional_file(self, path: Path) -> str:
        if not path.exists():
            self.logger.warning("Không tìm thấy file tiêu chí/chủ đề: %s", path)
            return ""
        return path.read_text(encoding="utf-8").strip()

    @staticmethod
    def _clean_json_text(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
            cleaned = cleaned.removesuffix("```").strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return cleaned[start : end + 1]
        return cleaned
