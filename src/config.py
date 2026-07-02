"""Application configuration loaded from the project .env file."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Config:
    LARK_APP_ID: str = os.getenv("LARK_APP_ID", "")
    LARK_APP_SECRET: str = os.getenv("LARK_APP_SECRET", "")
    LARK_APP_TOKEN: str = os.getenv("LARK_APP_TOKEN", "")
    LARK_TABLE_ID: str = os.getenv("LARK_TABLE_ID", "")
    LARK_VIEW_ID: str = os.getenv("LARK_VIEW_ID", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash-lite",
    )
    GEMINI_FALLBACK_MODEL: str = os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-2.5-flash",
    )
    GEMINI_MAX_RETRIES: int = int(os.getenv("GEMINI_MAX_RETRIES", "3"))
    PYANNOTE_TOKEN: str = os.getenv("PYANNOTE_TOKEN", "")
    PYANNOTE_MODEL: str = os.getenv(
        "PYANNOTE_MODEL",
        "pyannote/speaker-diarization-community-1",
    )

    LARK_API_BASE: str = "https://open.larksuite.com/open-apis"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    CACHE_DIR: Path = BASE_DIR / "cache"
    CACHE_AUDIOS: Path = CACHE_DIR / "audios"
    CACHE_TRANSCRIPTS: Path = CACHE_DIR / "transcripts"
    CACHE_FILES: Path = CACHE_DIR / "files"
    LOG_DIR: Path = BASE_DIR / "logs"
    CLASS_DIR: Path = BASE_DIR / "class"
    COMMENT_EXAMPLES_FILE: Path = BASE_DIR / "data" / "comment_examples.txt"
    TOPIC_RULES_FILE: Path = BASE_DIR / "data" / "topic_rules.txt"
    ALLOWED_TOPICS_FILE: Path = BASE_DIR / "data" / "allowed_topics.txt"
    YOUTUBE_CONTENT_FILE: Path = BASE_DIR / "data" / "youtube_content.txt"
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "tiny")
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    TRANSCRIPT_MAX_CHARS: int = int(os.getenv("TRANSCRIPT_MAX_CHARS", "12000"))
    TRANSCRIBE_SAMPLE_SECONDS: int = int(os.getenv("TRANSCRIBE_SAMPLE_SECONDS", "120"))
    ENABLE_WHISPER_FALLBACK: bool = (
        os.getenv("ENABLE_WHISPER_FALLBACK", "false").lower()
        in {"1", "true", "yes", "y"}
    )

    def ensure_dirs(self) -> None:
        for directory in (
            self.CACHE_AUDIOS,
            self.CACHE_TRANSCRIPTS,
            self.CACHE_FILES,
            self.LOG_DIR,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def validate_lark(self) -> list[str]:
        required = {
            "LARK_APP_ID": self.LARK_APP_ID,
            "LARK_APP_SECRET": self.LARK_APP_SECRET,
            "LARK_APP_TOKEN": self.LARK_APP_TOKEN,
            "LARK_TABLE_ID": self.LARK_TABLE_ID,
        }
        return [name for name, value in required.items() if not value]


config = Config()
