"""Gemini client used by the project's AI skills."""

import logging
import time
from typing import Any

from .config import config as default_config


class LLMClient:
    """Small wrapper around the official Google Gen AI SDK."""

    def __init__(
        self,
        *,
        config: Any = default_config,
        logger: logging.Logger | None = None,
        client: Any | None = None,
    ) -> None:
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình trong .env")

        self.model = config.GEMINI_MODEL
        self.fallback_model = getattr(config, "GEMINI_FALLBACK_MODEL", "")
        self.max_retries = max(1, getattr(config, "GEMINI_MAX_RETRIES", 3))
        self.logger = logger or logging.getLogger(__name__)

        if client is not None:
            self.client = client
        else:
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError(
                    "Thiếu thư viện google-genai. "
                    "Hãy chạy: pip install -r requirements.txt"
                ) from exc
            self.client = genai.Client(api_key=config.GEMINI_API_KEY)

    def generate(self, *, instructions: str, input_text: str) -> str:
        """Generate plain text with Gemini."""
        prompt = f"{instructions}\n\nDữ liệu cần nhận xét:\n{input_text}"
        models = [self.model]
        if self.fallback_model and self.fallback_model not in models:
            models.append(self.fallback_model)

        last_error: Exception | None = None
        for model in models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    text = (response.text or "").strip()
                    if not text:
                        raise RuntimeError("Gemini trả về nội dung rỗng.")
                    if model != self.model:
                        self.logger.info(
                            "Gemini fallback thành công với model %s.",
                            model,
                        )
                    return text
                except Exception as exc:
                    last_error = exc
                    message = " ".join(str(exc).split())
                    lowered = message.lower()

                    if "api key" in lowered or "api_key" in lowered or "401" in lowered:
                        raise RuntimeError(
                            "Gemini API key không hợp lệ hoặc chưa được kích hoạt."
                        ) from exc

                    retryable = any(
                        marker in lowered
                        for marker in (
                            "429",
                            "503",
                            "resource_exhausted",
                            "unavailable",
                            "high demand",
                            "temporarily",
                        )
                    )
                    if not retryable:
                        raise RuntimeError(
                            f"Gemini API lỗi: {message[:240]}"
                        ) from exc

                    if attempt < self.max_retries:
                        delay = 2 ** (attempt - 1)
                        self.logger.warning(
                            "Gemini model %s tạm bận; thử lại %d/%d sau %ds.",
                            model,
                            attempt + 1,
                            self.max_retries,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        self.logger.warning(
                            "Gemini model %s vẫn bận sau %d lần; chuyển fallback.",
                            model,
                            self.max_retries,
                        )

        message = " ".join(str(last_error).split()) if last_error else ""
        if "429" in message or "resource_exhausted" in message.lower():
            raise RuntimeError(
                "Gemini API đã chạm giới hạn free tier; vui lòng thử lại sau."
            ) from last_error
        raise RuntimeError(
            "Các model Gemini đang quá tải; vui lòng thử lại sau vài phút."
        ) from last_error
