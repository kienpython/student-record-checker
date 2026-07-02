"""Skill for generating concise Vietnamese teaching-assistant feedback."""

import json
import logging
from pathlib import Path
from typing import Any

from ..config import config as default_config
from ..llm_client import LLMClient


class CommentWriterSkill:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        logger: logging.Logger | None = None,
        examples_file: Path | None = None,
    ) -> None:
        self.llm = llm_client
        self.logger = logger or logging.getLogger(__name__)
        self.examples_file = examples_file or default_config.COMMENT_EXAMPLES_FILE

    def _load_examples(self) -> list[str]:
        """Load editable style examples used as few-shot guidance."""
        if not self.examples_file.exists():
            self.logger.warning(
                "Không tìm thấy file mẫu nhận xét: %s",
                self.examples_file,
            )
            return []

        return [
            line.strip()
            for line in self.examples_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    def write_comment(self, analysis: dict[str, Any]) -> str:
        """Generate a grounded comment without inventing unobserved evidence."""
        examples = self._load_examples()
        example_text = "\n".join(f"- {example}" for example in examples)
        instructions = (
            "Bạn là trợ giảng đang nhận xét hoạt động nhóm sinh viên. "
            "Viết đúng 1-2 câu tiếng Việt, ngắn gọn, tự nhiên và gần gũi. "
            "Không chào hỏi, không gọi tên nhóm, không viết kiểu thông báo hành chính. "
            "Tuyệt đối không nhắc đến hệ thống, AI, transcript, dữ liệu ghi âm, "
            "record, video đang xử lý hoặc việc chưa thể cung cấp nhận xét. "
            "Không dùng Markdown và không giải thích cách bạn tạo nhận xét. "
            "Chỉ nhận xét những gì có căn cứ trong dữ liệu; nếu thông tin còn ít, "
            "hãy viết một lời động viên ngắn, trung tính, không bịa chi tiết. "
            "Nếu đánh_giá_nội_dung.is_group_work_discussion là true, hãy xem như "
            "nhóm có tham gia hoạt động thảo luận/làm bài tập; không nhận xét "
            "kiểu nội dung không đúng chủ đề chỉ vì matches_topic=false. "
            "Trong trường hợp đó, hãy ghi nhận nhóm có thảo luận và chỉ góp ý "
            "nhẹ nếu cần bổ sung quiz, mindmap, tổng kết hoặc kiểm tra kiến thức. "
            "Chỉ nhắc nội dung không phù hợp hoặc nộp nhầm khi "
            "is_group_work_discussion=false hoặc suspected_old_or_wrong_file=true.\n\n"
            "Giọng văn tham khảo lấy từ các nhận xét thật của trợ giảng:\n"
            f"{example_text or '- Nhóm hoạt động tốt, cứ thế phát huy.'}\n\n"
            "Hãy bắt chước độ dài và sắc thái của các mẫu trên, nhưng không sao "
            "chép máy móc."
        )
        input_text = json.dumps(analysis, ensure_ascii=False, indent=2)
        comment = self.llm.generate(
            instructions=instructions,
            input_text=input_text,
        )
        self.logger.info("AI đã tạo nhận xét dài %d ký tự.", len(comment))
        return comment
