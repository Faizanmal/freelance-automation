import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.llm import FALLBACK_ORDER, any_llm_configured, configured_providers


class LLMConfigTests(unittest.TestCase):
    def test_fallback_order(self) -> None:
        self.assertEqual(FALLBACK_ORDER, ("groq", "nvidia", "gemini", "openai", "anthropic"))

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
        with patch("app.services.llm.get_settings", return_value=settings):
            self.assertTrue(any_llm_configured())
            self.assertEqual(configured_providers(), ["groq", "gemini", "anthropic"])


if __name__ == "__main__":
    unittest.main()
