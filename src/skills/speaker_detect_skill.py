"""Skill for counting distinct speakers with local pyannote.audio."""

import json
import logging
import os
from pathlib import Path
from typing import Any
import warnings


class SpeakerDetectSkill:
    def __init__(
        self,
        *,
        config,
        logger: logging.Logger | None = None,
        pipeline: Any | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.token = config.PYANNOTE_TOKEN or ""
        self.model = config.PYANNOTE_MODEL
        self.cache_dir = Path(config.CACHE_AUDIOS) / "speaker_counts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault(
            "MPLCONFIGDIR",
            str(Path(config.CACHE_DIR) / "matplotlib"),
        )
        self._pipeline = pipeline

    @property
    def is_available(self) -> bool:
        return bool(self.token)

    def detect_speakers(self, audio_path: Path, record_id: str) -> int:
        if not self.is_available:
            raise RuntimeError("Chưa bật speaker detection.")

        cache_file = self.cache_dir / f"{record_id}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("audio_size") == audio_path.stat().st_size:
                count = int(data["speaker_count"])
                self.logger.info("Speaker cache hit: %d giọng nói.", count)
                return count

        pipeline = self._get_pipeline()
        self.logger.info("Đang đếm giọng nói trong %s...", audio_path.name)
        try:
            audio_input = self._load_wav(audio_path)
            output = pipeline(audio_input)
            speakers = self._extract_speakers(output)
        except Exception as exc:
            raise RuntimeError(f"Không đếm được giọng nói: {exc}") from exc

        count = len(speakers)
        if count < 1:
            raise RuntimeError("Không phát hiện được giọng nói nào trong audio.")

        cache_file.write_text(
            json.dumps(
                {
                    "audio_size": audio_path.stat().st_size,
                    "speaker_count": count,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.logger.info("Phát hiện %d giọng nói.", count)
        return count

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*torchcodec is not installed correctly.*",
                )
                from pyannote.audio import Pipeline
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu pyannote.audio. Hãy chạy: pip install -r requirements.txt"
            ) from exc

        self.logger.info("Đang tải pyannote model %s...", self.model)
        try:
            self._pipeline = Pipeline.from_pretrained(
                self.model,
                token=self.token,
            )
        except Exception as exc:
            message = str(exc).lower()
            if "gated" in message or "403" in message or "restricted" in message:
                raise RuntimeError(
                    "Tài khoản Hugging Face chưa được cấp quyền model pyannote. "
                    f"Hãy chấp nhận điều kiện tại https://huggingface.co/{self.model}"
                ) from exc
            raise RuntimeError(f"Không tải được model pyannote: {exc}") from exc
        if torch.cuda.is_available():
            self._pipeline.to(torch.device("cuda"))
            self.logger.info("Speaker detection đang dùng GPU CUDA.")
        else:
            self.logger.info("Speaker detection đang dùng CPU.")
        return self._pipeline

    @staticmethod
    def _load_wav(audio_path: Path) -> dict[str, Any]:
        """Load WAV in memory to avoid TorchCodec/FFmpeg DLL issues on Windows."""
        if audio_path.suffix.lower() != ".wav":
            raise RuntimeError(
                "Speaker detection cần file WAV; hãy xóa cache audio cũ để tải lại."
            )
        try:
            import numpy as np
            import torch
            from scipy.io import wavfile
        except ImportError as exc:
            raise RuntimeError("Thiếu scipy/numpy/torch để đọc WAV.") from exc

        sample_rate, samples = wavfile.read(audio_path)
        if samples.ndim == 1:
            samples = samples[:, None]

        if np.issubdtype(samples.dtype, np.integer):
            max_value = max(
                abs(np.iinfo(samples.dtype).min),
                np.iinfo(samples.dtype).max,
            )
            samples = samples.astype(np.float32) / float(max_value)
        else:
            samples = samples.astype(np.float32)

        waveform = torch.from_numpy(samples.T.copy())
        return {
            "waveform": waveform,
            "sample_rate": int(sample_rate),
        }

    @staticmethod
    def _extract_speakers(output: Any) -> set[str]:
        diarization = getattr(output, "speaker_diarization", output)
        if hasattr(diarization, "labels"):
            return {str(label) for label in diarization.labels()}

        speakers: set[str] = set()
        if hasattr(diarization, "itertracks"):
            for _, _, speaker in diarization.itertracks(yield_label=True):
                speakers.add(str(speaker))
            return speakers

        for item in diarization:
            if isinstance(item, tuple) and len(item) >= 2:
                speakers.add(str(item[-1]))
        return speakers
