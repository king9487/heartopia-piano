import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import ai_settings


class AiSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.settings_path = Path(self.temp_dir.name) / "config" / "ai_settings.json"
        self.previous = os.environ.get("YOUTUBE_TO_MIDI_AI_SETTINGS")
        os.environ["YOUTUBE_TO_MIDI_AI_SETTINGS"] = str(self.settings_path)

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("YOUTUBE_TO_MIDI_AI_SETTINGS", None)
        else:
            os.environ["YOUTUBE_TO_MIDI_AI_SETTINGS"] = self.previous
        self.temp_dir.cleanup()

    def configured(self, provider="openai"):
        value = json.loads(json.dumps(ai_settings.DEFAULT_AI_SETTINGS))
        value["provider"] = provider
        value["api_keys"][provider] = "secret-value"
        value["models"][provider] = "test-model"
        return value

    def test_missing_and_malformed_settings_return_defaults(self):
        self.assertEqual(ai_settings.load_ai_settings(), ai_settings.DEFAULT_AI_SETTINGS)
        self.settings_path.parent.mkdir(parents=True)
        self.settings_path.write_text("{bad", encoding="utf-8")
        self.assertEqual(ai_settings.load_ai_settings(), ai_settings.DEFAULT_AI_SETTINGS)

    def test_save_load_and_provider_selection(self):
        settings = self.configured("gemini")
        settings["timeout_seconds"] = "30"
        saved = ai_settings.save_ai_settings(settings)
        self.assertEqual(saved["timeout_seconds"], 30)
        active = ai_settings.get_active_provider_settings()
        self.assertEqual((active["provider"], active["api_key"], active["model"]), ("gemini", "secret-value", "test-model"))

    def test_clear_provider_key_preserves_other_providers(self):
        settings = self.configured("gemini")
        settings["api_keys"]["openai"] = "openai-secret"
        ai_settings.save_ai_settings(settings)
        cleared = ai_settings.clear_provider_key("gemini")
        self.assertEqual(cleared["api_keys"]["gemini"], "")
        self.assertEqual(cleared["api_keys"]["openai"], "openai-secret")

    def test_disabled_and_missing_keys(self):
        ready, errors = ai_settings.validate_ai_settings()
        self.assertFalse(ready)
        self.assertEqual(errors, [])
        for provider in ("openai", "gemini"):
            settings = self.configured(provider)
            settings["api_keys"][provider] = ""
            ready, errors = ai_settings.validate_ai_settings(settings)
            self.assertFalse(ready)
            self.assertIn("AI API key is not configured.", errors)

    def test_compatible_endpoint_requires_base_url(self):
        ready, errors = ai_settings.validate_ai_settings(self.configured("openai_compatible"))
        self.assertFalse(ready)
        self.assertIn("Base URL is required for OpenAI-compatible providers.", errors)

    def test_redaction_removes_key_and_authorization_value(self):
        message = ai_settings.redact_secret("secret-value Authorization: Bearer abc", "secret-value")
        self.assertNotIn("secret-value", message)
        self.assertNotIn("Bearer abc", message)

    def test_example_has_no_keys(self):
        example = json.loads(Path("config/ai_settings.example.json").read_text(encoding="utf-8"))
        self.assertTrue(all(not key for key in example["api_keys"].values()))


if __name__ == "__main__":
    unittest.main()
