import unittest

from ai_models import model_values_for_provider, selected_model_for_provider


class AiModelSelectorTests(unittest.TestCase):
    def test_switching_openai_to_gemini_refreshes_values(self):
        openai_values = model_values_for_provider("openai")
        gemini_values = model_values_for_provider("gemini")
        self.assertIn("gpt-4.1-mini", openai_values)
        self.assertNotIn("gpt-4.1-mini", gemini_values)
        self.assertEqual(gemini_values[0], "gemini-3-flash-preview")

    def test_switching_gemini_to_openai_refreshes_values(self):
        self.assertNotIn("gemini-2.5-pro", model_values_for_provider("openai"))
        self.assertEqual(model_values_for_provider("openai")[0], "gpt-4.1-mini")

    def test_saved_models_remain_provider_specific(self):
        models = {"openai": "gpt-custom", "gemini": "gemini-custom"}
        self.assertEqual(selected_model_for_provider("openai", models), "gpt-custom")
        self.assertEqual(selected_model_for_provider("gemini", models), "gemini-custom")
        self.assertEqual(models["openai"], "gpt-custom")

    def test_missing_model_uses_provider_default(self):
        self.assertEqual(selected_model_for_provider("gemini", {}), "gemini-3-flash-preview")
        self.assertEqual(selected_model_for_provider("openai_compatible", {}), "")


if __name__ == "__main__":
    unittest.main()
