import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock
from urllib import error

from ai_providers import create_provider
from ai_providers.base import ProviderError
from ai_providers.gemini_provider import _parse_gemini_json


def settings(provider):
    return {"provider": provider, "api_key": "test-secret", "model": "test-model", "base_url": "http://local.test/v1", "timeout_seconds": 1, "max_retries": 0}

class FakeResponse:
    def __init__(self, value): self.value = value
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return json.dumps(self.value).encode()

class AiProviderTests(unittest.TestCase):
    def test_gemini_json_recovery_handles_fences_and_extra_text(self):
        self.assertEqual(_parse_gemini_json('```json\n{"notes": []}\n```'), {"notes": []})
        self.assertEqual(
            _parse_gemini_json('Here is the result: {"notes": []} trailing text'),
            {"notes": []},
        )

    def test_gemini_json_recovery_does_not_extract_note_from_truncated_root(self):
        truncated = '{"notes":[{"start_ms":1,"duration_ms":2,"note":60,"velocity":90},{"start_ms":3'
        with self.assertRaises(json.JSONDecodeError):
            _parse_gemini_json(truncated)

    def test_provider_selection(self):
        self.assertEqual(create_provider(settings("openai")).provider_name, "openai")
        self.assertEqual(create_provider(settings("gemini")).provider_name, "gemini")
        self.assertEqual(create_provider(settings("openai_compatible")).provider_name, "openai_compatible")

    def test_openai_normalized_output(self):
        response = {"output_text": '{"notes":[],"explanation":"ok"}', "usage": {"input_tokens": 2, "output_tokens": 3}}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            result = create_provider(settings("openai")).optimize_midi("prompt", [])
        self.assertEqual(result, {"notes": [], "explanation": "ok", "provider": "openai", "model": "test-model", "usage": {"input_tokens": 2, "output_tokens": 3}})

    def test_gemini_normalized_output(self):
        response = {"candidates": [{"content": {"parts": [{"text": '{"notes":[],"explanation":"empty input"}'}]}}], "usageMetadata": {"promptTokenCount": 1}}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            result = create_provider(settings("gemini")).optimize_midi("prompt", [])
        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(result["notes"], [])

    def test_gemini_request_never_uses_openai_model(self):
        configured = settings("gemini")
        configured["model"] = "gemini-3-flash-preview"
        response = {"candidates": [{"content": {"parts": [{"text": '{"notes":[],"explanation":"empty input"}'}]}}]}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)) as urlopen:
            create_provider(configured).optimize_midi("prompt", [])
        request_url = urlopen.call_args.args[0].full_url
        request_body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertIn("gemini-3-flash-preview", request_url)
        self.assertNotIn("gpt-", request_url)
        self.assertEqual(
            request_body["generationConfig"]["responseJsonSchema"]["required"],
            ["notes", "removed_notes", "explanation"],
        )
        self.assertNotIn("responseSchema", request_body["generationConfig"])
        self.assertEqual(
            request_body["generationConfig"]["responseJsonSchema"]["type"],
            "object",
        )
        self.assertEqual(
            request_body["generationConfig"]["responseJsonSchema"]["properties"]["notes"]["type"],
            "array",
        )
        prompt_text = request_body["contents"][0]["parts"][0]["text"]
        self.assertIn('The root object must contain a field named "notes".', prompt_text)
        self.assertGreaterEqual(request_body["generationConfig"]["maxOutputTokens"], 16384)
        self.assertEqual(
            request_body["generationConfig"]["thinkingConfig"],
            {"thinkingLevel": "low"},
        )

    def test_gemini_reports_output_token_truncation(self):
        response = {
            "candidates": [{
                "finishReason": "MAX_TOKENS",
                "content": {"parts": [{"text": '{"notes":[{"start_ms":1'}]},
            }]
        }
        with TemporaryDirectory() as temp_dir, mock.patch(
            "ai_providers.gemini_provider.GEMINI_RESPONSE_LOG", Path(temp_dir) / "last.txt"
        ), mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            with self.assertRaises(ProviderError) as raised:
                create_provider(settings("gemini")).optimize_midi("prompt", [{}] * 428)
        self.assertIn("truncated", str(raised.exception).lower())

    def test_gemini_25_flash_connection_disables_thinking(self):
        configured = settings("gemini")
        configured["model"] = "gemini-2.5-flash"
        response = {"candidates": [{"content": {"parts": [{"text": '{"notes":[],"removed_notes":[],"explanation":"connection test"}'}]}}]}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)) as urlopen:
            result = create_provider(configured).test_connection()
        request_body = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertTrue(result.success)
        self.assertEqual(request_body["generationConfig"]["maxOutputTokens"], 1024)
        self.assertEqual(
            request_body["generationConfig"]["thinkingConfig"],
            {"thinkingBudget": 0},
        )

    def test_gemini_empty_candidate_reports_finish_reason(self):
        response = {"candidates": [{"finishReason": "MAX_TOKENS"}]}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            result = create_provider(settings("gemini")).test_connection()
        self.assertFalse(result.success)
        self.assertIn("MAX_TOKENS", result.message)

    def test_gemini_normalizes_supported_note_paths(self):
        note = {"start_ms": 0, "duration_ms": 100, "note": 60, "velocity": 90}
        structures = (
            {"notes": [note], "explanation": "root"},
            {"optimized_notes": [note], "explanation": "alias"},
            {"result": {"notes": [note]}, "explanation": "result"},
            {"data": {"notes": [note]}, "explanation": "data"},
        )
        for parsed in structures:
            response = {"candidates": [{"content": {"parts": [{"text": json.dumps(parsed)}]}}]}
            with self.subTest(keys=list(parsed)), mock.patch(
                "ai_providers.base.request.urlopen", return_value=FakeResponse(response)
            ):
                result = create_provider(settings("gemini")).optimize_midi("prompt", [note])
            self.assertEqual(result["notes"], [note])
            self.assertEqual(result["provider"], "gemini")

    def test_gemini_schema_failures_are_distinct_and_diagnostic(self):
        cases = (
            ({"result": {}, "explanation": "missing"}, "No notes field"),
            ({"notes": "not-a-list", "explanation": "bad"}, "must be a JSON array"),
            ({"notes": [{"note": 60}], "explanation": "bad"}, "missing required fields"),
            ({"notes": [{"start_ms": 0, "duration_ms": 0, "note": 60, "velocity": 90}], "explanation": "bad"}, "invalid MIDI note values"),
        )
        with TemporaryDirectory() as temp_dir:
            text_log = Path(temp_dir) / "logs" / "last_gemini_response.txt"
            json_log = Path(temp_dir) / "logs" / "last_gemini_response.json"
            for parsed, expected in cases:
                response = {"candidates": [{"content": {"parts": [{"text": json.dumps(parsed)}]}}]}
                with self.subTest(expected=expected), mock.patch(
                    "ai_providers.gemini_provider.GEMINI_RESPONSE_LOG", text_log
                ), mock.patch(
                    "ai_providers.gemini_provider.GEMINI_PARSED_LOG", json_log
                ), mock.patch(
                    "ai_providers.base.request.urlopen", return_value=FakeResponse(response)
                ):
                    with self.assertRaises(ProviderError) as raised:
                        create_provider(settings("gemini")).optimize_midi("prompt", [])
                self.assertEqual(
                    str(raised.exception),
                    "Gemini returned valid JSON, but no MIDI notes were found.",
                )
                self.assertIn(expected, raised.exception.details)
                self.assertIn("Top-level keys:", raised.exception.details)
                self.assertIn("Checked paths:", raised.exception.details)
                self.assertTrue(text_log.exists())
                self.assertEqual(json.loads(json_log.read_text(encoding="utf-8")), parsed)

    def test_gemini_unchanged_full_note_list(self):
        note = {"start_ms": 0, "duration_ms": 100, "note": 60, "velocity": 90}
        parsed = {"notes": [note, dict(note)], "explanation": "No changes required."}
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps(parsed)}]}}]}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            result = create_provider(settings("gemini")).optimize_midi("prompt", [note, note])
        self.assertEqual(result["notes"], [note, note])

    def test_gemini_rejects_single_note_root(self):
        note = {"start_ms": 9, "duration_ms": 1950, "note": 72, "velocity": 64}
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps(note)}]}}]}
        with TemporaryDirectory() as temp_dir, mock.patch(
            "ai_providers.gemini_provider.GEMINI_RESPONSE_LOG", Path(temp_dir) / "last.txt"
        ), mock.patch(
            "ai_providers.gemini_provider.GEMINI_PARSED_LOG", Path(temp_dir) / "last.json"
        ), mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            with self.assertRaises(ProviderError) as raised:
                create_provider(settings("gemini")).optimize_midi("prompt", [note])
        self.assertEqual(
            str(raised.exception),
            "Gemini returned one note instead of the required notes array.",
        )

    def test_gemini_rejects_unexpectedly_low_note_count(self):
        notes = [
            {"start_ms": i * 100, "duration_ms": 90, "note": 60 + i, "velocity": 90}
            for i in range(4)
        ]
        parsed = {"notes": [notes[0]], "explanation": "Removed most notes."}
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps(parsed)}]}}]}
        with TemporaryDirectory() as temp_dir, mock.patch(
            "ai_providers.gemini_provider.GEMINI_RESPONSE_LOG", Path(temp_dir) / "last.txt"
        ), mock.patch(
            "ai_providers.gemini_provider.GEMINI_PARSED_LOG", Path(temp_dir) / "last.json"
        ), mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            with self.assertRaises(ProviderError) as raised:
                create_provider(settings("gemini")).optimize_midi("prompt", notes)
        self.assertEqual(
            str(raised.exception),
            "AI returned only 1 of 4 notes and supplied 0 verified deletions; 3 are required. The result was rejected to prevent data loss.",
        )
        self.assertIn("Input note count: 4", raised.exception.details)
        self.assertIn("Output note count: 1", raised.exception.details)

    def test_gemini_accepts_low_count_with_verified_deletions(self):
        notes = [
            {"start_ms": i * 100, "duration_ms": 90, "note": 60 + i, "velocity": 90}
            for i in range(4)
        ]
        parsed = {
            "notes": [notes[0]],
            "removed_notes": notes[1:],
            "explanation": "Removed three noisy notes.",
        }
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps(parsed)}]}}]}
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            result = create_provider(settings("gemini")).optimize_midi("prompt", notes)
        self.assertEqual(result["notes"], [notes[0]])

    def test_gemini_rejects_unverified_deletion(self):
        notes = [
            {"start_ms": i * 100, "duration_ms": 90, "note": 60 + i, "velocity": 90}
            for i in range(4)
        ]
        invented = {"start_ms": 999, "duration_ms": 90, "note": 80, "velocity": 90}
        parsed = {
            "notes": [notes[0]],
            "removed_notes": [notes[1], notes[2], invented],
            "explanation": "Removed noise.",
        }
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps(parsed)}]}}]}
        with TemporaryDirectory() as temp_dir, mock.patch(
            "ai_providers.gemini_provider.GEMINI_RESPONSE_LOG", Path(temp_dir) / "last.txt"
        ), mock.patch(
            "ai_providers.gemini_provider.GEMINI_PARSED_LOG", Path(temp_dir) / "last.json"
        ), mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse(response)):
            with self.assertRaises(ProviderError) as raised:
                create_provider(settings("gemini")).optimize_midi("prompt", notes)
        self.assertIn("does not match an available input note", raised.exception.details)

    def test_connection_failure_and_secret_redaction(self):
        with mock.patch("ai_providers.base.request.urlopen", side_effect=OSError("failed test-secret")):
            result = create_provider(settings("openai")).test_connection()
        self.assertFalse(result.success)
        self.assertNotIn("test-secret", result.message)

    def test_quota_and_malformed_response(self):
        quota = error.HTTPError("url", 429, "quota", {}, io.BytesIO())
        with mock.patch("ai_providers.base.request.urlopen", side_effect=quota):
            result = create_provider(settings("gemini")).test_connection()
        self.assertEqual(result.status, "quota_error")
        with mock.patch("ai_providers.base.request.urlopen", return_value=FakeResponse({"output_text": "not-json"})):
            with self.assertRaises(ProviderError):
                create_provider(settings("openai")).optimize_midi("prompt", [])

    def test_invalid_model_has_clear_category(self):
        configured = settings("gemini")
        configured["model"] = "gemini-3.0-flash"
        missing = error.HTTPError("url", 404, "missing", {}, io.BytesIO())
        with mock.patch("ai_providers.base.request.urlopen", side_effect=missing):
            result = create_provider(configured).test_connection()
        self.assertEqual(result.status, "model_not_found")
        self.assertEqual(result.message, "Model not found: gemini-3.0-flash")

    def test_invalid_gemini_json_saves_redacted_diagnostics(self):
        configured = settings("gemini")
        response = {"candidates": [{"content": {"parts": [{"text": "bad JSON test-secret"}]}}]}
        with TemporaryDirectory() as temp_dir:
            diagnostic = Path(temp_dir) / "logs" / "last_gemini_response.txt"
            with mock.patch("ai_providers.gemini_provider.GEMINI_RESPONSE_LOG", diagnostic), mock.patch(
                "ai_providers.base.request.urlopen", return_value=FakeResponse(response)
            ):
                with self.assertRaises(ProviderError) as raised:
                    create_provider(configured).optimize_midi("prompt", [])
            saved = diagnostic.read_text(encoding="utf-8")
        self.assertEqual(raised.exception.status, "invalid_response")
        self.assertIn("Parsing error:", raised.exception.details)
        self.assertIn("line 1", raised.exception.details)
        self.assertIn("Raw response preview:", raised.exception.details)
        self.assertNotIn("test-secret", saved)
        self.assertIn("[REDACTED]", saved)

if __name__ == "__main__":
    unittest.main()
