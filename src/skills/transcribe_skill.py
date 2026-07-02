"""Skill to transcribe audio/video files using faster-whisper.

Saves transcripts to cache/transcripts/{record_id}.txt.
"""

import logging
from pathlib import Path
import re
from typing import Optional
import wave


class TranscribeSkill:
    """Transcribes audio/video files to text using faster-whisper."""

    def __init__(self, *, config, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.cache_dir: Path = Path(self.config.CACHE_TRANSCRIPTS)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def transcribe(self, audio_path: Path, record_id: str) -> Optional[str]:
        """Transcribe an audio/video file and return the full transcript.

        Args:
            audio_path: Path to the audio/video file.
            record_id: Used for cache filename.

        Returns:
            Transcript text, or None on failure.
        """
        # Check cache first
        cache_file = self.cache_dir / f"{record_id}.txt"
        if cache_file.exists() and cache_file.stat().st_size > 0:
            self.logger.info(f"Transcript cache hit: {cache_file}")
            return cache_file.read_text(encoding="utf-8")

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu thư viện faster-whisper. Hãy chạy: pip install -r requirements.txt"
            ) from exc

        model_name = getattr(self.config, "WHISPER_MODEL", "base")
        compute_type = getattr(self.config, "WHISPER_COMPUTE_TYPE", "int8")
        transcribe_path = self._sample_wav_if_needed(audio_path, record_id)
        self.logger.info(
            "Đang transcribe %s bằng faster-whisper model=%s.",
            transcribe_path,
            model_name,
        )

        model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
        segments, _info = model.transcribe(
            str(transcribe_path),
            language="vi",
            vad_filter=True,
        )
        transcript = "\n".join(segment.text.strip() for segment in segments if segment.text.strip())
        if not transcript:
            raise RuntimeError("Không nhận được nội dung transcript từ audio.")

        self._save_cache(record_id, transcript)
        return transcript

    def _save_cache(self, record_id: str, transcript: str) -> Path:
        """Save transcript to cache."""
        cache_file = self.cache_dir / f"{record_id}.txt"
        cache_file.write_text(transcript, encoding="utf-8")
        self.logger.debug(f"Transcript cached: {cache_file}")
        return cache_file

    def transcribe_youtube(self, url: str, record_id: str) -> Optional[str]:
        """Try to extract YouTube subtitles/auto-captions before using Whisper."""
        cache_file = self.cache_dir / f"{record_id}.txt"
        source_file = self.cache_dir / f"{record_id}.source.txt"
        source_matches = (
            source_file.exists()
            and source_file.read_text(encoding="utf-8").strip() == url.strip()
        )
        if cache_file.exists() and cache_file.stat().st_size > 0 and source_matches:
            self.logger.info("Transcript cache hit: %s", cache_file)
            return cache_file.read_text(encoding="utf-8")
        if cache_file.exists() and not source_matches:
            self.logger.info(
                "Transcript cache source changed for %s; refreshing transcript.",
                record_id,
            )

        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            self.logger.warning("Thiếu yt-dlp nên không lấy được caption: %s", exc)
            return None

        for old_caption in self.cache_dir.glob(f"{record_id}*.vtt"):
            old_caption.unlink(missing_ok=True)

        output_template = str(self.cache_dir / f"{record_id}.%(ext)s")
        options = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "vtt",
            "subtitleslangs": ["vi.*", "en.*"],
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 30,
            "retries": 2,
            "js_runtimes": {"node": {"path": None}},
            "remote_components": {"ejs:github"},
        }
        caption_error: Exception | None = None
        try:
            self.logger.info("Đang thử lấy YouTube caption cho record %s.", record_id)
            with YoutubeDL(options) as ydl:
                ydl.download([url])
        except Exception as exc:
            caption_error = exc

        captions = sorted(
            self.cache_dir.glob(f"{record_id}*.vtt"),
            key=lambda path: path.stat().st_size,
            reverse=True,
        )
        for caption_file in captions:
            transcript = self._vtt_to_text(caption_file)
            if transcript:
                self._save_cache(record_id, transcript)
                source_file.write_text(url.strip(), encoding="utf-8")
                self.logger.info("Đã lấy transcript từ caption: %s", caption_file)
                return transcript

        if caption_error:
            self.logger.info(
                "Không lấy được YouTube caption, sẽ fallback Whisper: %s",
                caption_error,
            )
        self.logger.info("YouTube không có caption usable cho record %s.", record_id)
        return None

    def _vtt_to_text(self, caption_file: Path) -> str:
        seen: set[str] = set()
        lines: list[str] = []
        for raw_line in caption_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if (
                line == "WEBVTT"
                or line.startswith(("Kind:", "Language:", "NOTE"))
                or "-->" in line
                or line.isdigit()
            ):
                continue

            line = re.sub(r"<[^>]+>", "", line)
            line = re.sub(r"\s+", " ", line).strip()
            if not line or line in seen:
                continue

            seen.add(line)
            lines.append(line)

        return " ".join(lines).strip()

    def _sample_wav_if_needed(self, audio_path: Path, record_id: str) -> Path:
        """Create a short WAV sample for faster demo transcription."""
        max_seconds = int(getattr(self.config, "TRANSCRIBE_SAMPLE_SECONDS", 0) or 0)
        if max_seconds <= 0 or audio_path.suffix.lower() != ".wav":
            return audio_path

        sample_dir = self.cache_dir / "samples"
        sample_dir.mkdir(parents=True, exist_ok=True)
        sample_file = sample_dir / f"{record_id}.{max_seconds}s.wav"
        if sample_file.exists() and sample_file.stat().st_size > 0:
            self.logger.info("Transcript audio sample cache hit: %s", sample_file)
            return sample_file

        try:
            with wave.open(str(audio_path), "rb") as source:
                frame_rate = source.getframerate()
                total_frames = source.getnframes()
                sample_frames = min(total_frames, frame_rate * max_seconds)
                params = source.getparams()
                data = source.readframes(sample_frames)

            with wave.open(str(sample_file), "wb") as target:
                target.setparams(params)
                target.writeframes(data)

            self.logger.info(
                "Đã tạo audio sample %ss để transcribe nhanh: %s",
                max_seconds,
                sample_file,
            )
            return sample_file
        except Exception as exc:
            self.logger.warning(
                "Không tạo được audio sample, sẽ transcribe file gốc: %s",
                exc,
            )
            return audio_path
