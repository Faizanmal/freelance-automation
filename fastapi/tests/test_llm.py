import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.application.services.llm import (
    FALLBACK_ORDER,
    _resolve_model,
    _retry_after_seconds,
    any_llm_configured,
    configured_providers,
)


class LLMConfigTests(unittest.TestCase):
    def test_fallback_order(self) -> None:
        self.assertEqual(
            FALLBACK_ORDER, ("groq", "nvidia", "gemini", "openai", "anthropic")
        )

    def test_retired_models_remap(self) -> None:
        self.assertEqual(_resolve_model("llama-3.3-70b-versatile"), "openai/gpt-oss-20b")
        self.assertEqual(
            _resolve_model("meta/llama-3.1-70b-instruct"),
            "nvidia/nemotron-3.5-lightning-30b-a3b",
        )
        self.assertEqual(_resolve_model("gemini-2.0-flash"), "gemini-2.5-flash-lite")
        self.assertEqual(_resolve_model("openai/gpt-oss-20b"), "openai/gpt-oss-20b")

    def test_retry_after_parses_groq_message(self) -> None:
        msg = (
            "429 for openai/gpt-oss-20b: Rate limit reached ... "
            "Please try again in 1.77s. Ne"
        )
        self.assertAlmostEqual(_retry_after_seconds(Exception(msg)), 1.77, places=2)
        self.assertAlmostEqual(
            _retry_after_seconds(Exception("try again in 105ms")), 0.25, places=2
        )

    def test_configured_providers_respect_keys(self) -> None:
        settings = SimpleNamespace(
            groq_api_key="g",
            groq_model="llama",
            nvidia_api_key=None,
            nvidia_model="n",
            gemini_api_key="ge",
            gemini_model="gemini",
            openai_api_key=None,
            openai_model="gpt",
            anthropic_api_key="a",
            anthropic_model="claude",
        )
        with patch(
            "backend.application.services.llm.get_settings", return_value=settings
        ):
            self.assertTrue(any_llm_configured())
            self.assertEqual(configured_providers(), ["groq", "gemini", "anthropic"])


if __name__ == "__main__":
    unittest.main()
