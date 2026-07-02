"""CLI entry point.

Supports: ``python src/main.py ...``.
"""

import argparse
from pathlib import Path
import sys


for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import Agent  # noqa: E402
from src.config import config  # noqa: E402
from src.logger import get_logger  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Student Record Checker MVP")
    parser.add_argument("--topic", required=True, help="Đề bài cần kiểm tra")
    parser.add_argument(
        "--expected-speakers",
        type=int,
        default=0,
        help="Số người nói kỳ vọng, chỉ dùng khi bật --speaker-check",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Số record tối đa cần đọc và xử lý",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ đọc/in, không cập nhật Lark Base",
    )
    parser.add_argument(
        "--speaker-check",
        action="store_true",
        help="Bật kiểm tra số giọng nói bằng pyannote.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config.ensure_dirs()
    logger = get_logger(log_dir=config.LOG_DIR, level=config.LOG_LEVEL)

    missing = config.validate_lark()
    if missing:
        logger.error("Thiếu cấu hình trong .env: %s", ", ".join(missing))
        return 2
    if args.limit < 1:
        logger.error("--limit phải lớn hơn hoặc bằng 1.")
        return 2
    if args.expected_speakers < 0:
        logger.error("--expected-speakers không được âm.")
        return 2

    try:
        Agent(logger=logger, config=config).run(
            topic=args.topic,
            expected_speakers=args.expected_speakers,
            limit=args.limit,
            dry_run=args.dry_run,
            speaker_check=args.speaker_check,
        )
    except Exception:
        logger.exception("Chương trình dừng do lỗi khởi tạo/đọc Lark Base.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
