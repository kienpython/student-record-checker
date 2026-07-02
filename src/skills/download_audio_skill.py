"""Skill for downloading and caching audio-only media."""

import logging
from pathlib import Path
import re


class DownloadAudioSkill:
    YOUTUBE_PATTERN = re.compile(
        r"^(?:https?://)?(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/",
        re.IGNORECASE,
    )

    def __init__(self, *, config, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self.cache_dir = Path(config.CACHE_AUDIOS)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def is_youtube(self, url: str) -> bool:
        return bool(self.YOUTUBE_PATTERN.match(url.strip()))

    def download(self, url: str, record_id: str) -> Path:
        if not self.is_youtube(url):
            raise ValueError("Record không phải link YouTube.")
        return self._download_youtube(url, record_id)

    def _download_youtube(self, url: str, record_id: str) -> Path:
        record_dir = self.cache_dir / record_id
        record_dir.mkdir(parents=True, exist_ok=True)

        cached = self._find_cached_audio(record_dir)
        if cached:
            self.logger.info("Audio cache hit: %s", cached)
            return cached

        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu yt-dlp. Hãy chạy: pip install -r requirements.txt"
            ) from exc

        normalized_url = url.strip()
        if not normalized_url.lower().startswith(("http://", "https://")):
            normalized_url = f"https://{normalized_url}"

        output_template = str(record_dir / "audio.%(ext)s")
        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "js_runtimes": {
                "node": {"path": None},
            },
            "remote_components": {
                "ejs:github",
            },
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }
            ],
        }
        self.logger.info("Đang tải audio YouTube cho record %s...", record_id)
        try:
            with YoutubeDL(options) as downloader:
                downloader.extract_info(normalized_url, download=True)
        except Exception as exc:
            raise RuntimeError(f"Không tải được audio YouTube: {exc}") from exc

        cached = self._find_cached_audio(record_dir)
        if not cached:
            raise RuntimeError("yt-dlp chạy xong nhưng không tìm thấy file audio.")
        self.logger.info("Đã lưu audio: %s", cached)
        return cached

    @staticmethod
    def _find_cached_audio(record_dir: Path) -> Path | None:
        supported = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".opus"}
        for path in sorted(record_dir.iterdir()) if record_dir.exists() else []:
            if path.is_file() and path.suffix.lower() in supported and path.stat().st_size:
                return path
        return None
