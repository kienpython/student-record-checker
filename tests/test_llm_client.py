from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.llm_client import LLMClient


class LLMClientTests(unittest.TestCase):
    def test_generates_text_with_gemini_generate_content_api(self):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(
            text="Nhận xét từ Gemini."
        )
        config = SimpleNamespace(
            GEMINI_API_KEY="test-key",
            GEMINI_MODEL="gemini-2.5-flash-lite",
            GEMINI_FALLBACK_MODEL="gemini-2.5-flash",
            GEMINI_MAX_RETRIES=3,
        )
        llm = LLMClient(config=config, client=client)

        result = llm.generate(
            instructions="Viết ngắn gọn.",
            input_text='{"group_id": "G1"}',
        )

        self.assertEqual(result, "Nhận xét từ Gemini.")
        call = client.models.generate_content.call_args.kwargs
        self.assertEqual(call["model"], "gemini-2.5-flash-lite")
        self.assertIn("Viết ngắn gọn.", call["contents"])
        self.assertIn('"group_id": "G1"', call["contents"])

    def test_requires_api_key(self):
        config = SimpleNamespace(
            GEMINI_API_KEY="",
            GEMINI_MODEL="gemini-2.5-flash-lite",
            GEMINI_FALLBACK_MODEL="gemini-2.5-flash",
            GEMINI_MAX_RETRIES=3,
        )
        with self.assertRaisesRegex(ValueError, "GEMINI_API_KEY"):
            LLMClient(config=config, client=Mock())

    @patch("src.llm_client.time.sleep")
    def test_retries_then_uses_fallback_model(self, sleep):
        client = Mock()
        client.models.generate_content.side_effect = [
            RuntimeError("503 UNAVAILABLE high demand"),
            RuntimeError("503 UNAVAILABLE high demand"),
            SimpleNamespace(text="Fallback thành công."),
        ]
        config = SimpleNamespace(
            GEMINI_API_KEY="test-key",
            GEMINI_MODEL="gemini-2.5-flash-lite",
            GEMINI_FALLBACK_MODEL="gemini-2.5-flash",
            GEMINI_MAX_RETRIES=2,
        )
        llm = LLMClient(config=config, client=client)

        result = llm.generate(instructions="Nhận xét.", input_text="G1")

        self.assertEqual(result, "Fallback thành công.")
        calls = client.models.generate_content.call_args_list
        self.assertEqual(calls[0].kwargs["model"], "gemini-2.5-flash-lite")
        self.assertEqual(calls[1].kwargs["model"], "gemini-2.5-flash-lite")
        self.assertEqual(calls[2].kwargs["model"], "gemini-2.5-flash")
        sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
