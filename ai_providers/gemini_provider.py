"""Google Gemini generateContent provider."""
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote
from ai_settings import redact_secret
from .base import (
    AiProvider, ProviderError, ProviderTestResult, normalize_removal_result,
)

LOGGER = logging.getLogger(__name__)
GEMINI_RESPONSE_LOG = Path("logs") / "last_gemini_response.txt"
GEMINI_PARSED_LOG = Path("logs") / "last_gemini_response.json"
GEMINI_REQUEST_LOG = Path("logs") / "last_gemini_request.json"
GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["removed_ids"],
    "additionalProperties": False,
    "propertyOrdering": ["removed_ids", "explanation"],
    "properties": {
        "removed_ids": {
            "type": "array",
            "description": "Temporary input note IDs selected for removal.",
            "items": {"type": "integer", "minimum": 0},
        },
        "explanation": {
            "type": "string",
            "description": "A concise explanation of the optimization.",
        },
    },
}


def _strip_markdown_fences(raw):
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    return fenced.group(1).strip() if fenced else text.replace("```json", "").replace("```", "").strip()


def _parse_gemini_json(raw):
    """Parse direct/fenced JSON or one root value surrounded by prose.

    Never scan past a broken root into nested objects: a truncated
    {"notes": [...]} response may contain complete note objects, but those are
    not valid optimizer results by themselves.
    """
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as initial_error:
        decoder = json.JSONDecoder()
        object_index = cleaned.find("{")
        array_index = cleaned.find("[")
        indexes = [index for index in (object_index, array_index) if index >= 0]
        if indexes:
            root_index = min(indexes)
            try:
                value, _end = decoder.raw_decode(cleaned[root_index:])
                return value
            except json.JSONDecodeError:
                pass
        raise initial_error


def _save_invalid_response(raw, api_key, parse_error):
    safe_raw = redact_secret(raw, api_key)
    safe_error = redact_secret(parse_error, api_key)
    GEMINI_RESPONSE_LOG.parent.mkdir(parents=True, exist_ok=True)
    GEMINI_RESPONSE_LOG.write_text(
        f"JSON parsing error: {safe_error}\n\nRaw Gemini response:\n{safe_raw}\n",
        encoding="utf-8",
    )
    LOGGER.error("Gemini JSON parsing failed: %s; raw response: %s", safe_error, safe_raw)
    location = ""
    if isinstance(parse_error, json.JSONDecodeError):
        location = f" (line {parse_error.lineno}, column {parse_error.colno})"
    details = (
        f"Parsing error: {safe_error}{location}\n"
        f"Saved to: {GEMINI_RESPONSE_LOG}\n\n"
        f"Raw response preview:\n{safe_raw[:500]}"
    )
    return details


def _save_schema_diagnostics(raw, parsed, api_key, model, schema_error, input_note_count):
    safe_raw = redact_secret(raw, api_key)
    safe_json = redact_secret(
        json.dumps(parsed, ensure_ascii=False, indent=2), api_key
    )
    GEMINI_RESPONSE_LOG.parent.mkdir(parents=True, exist_ok=True)
    GEMINI_RESPONSE_LOG.write_text(safe_raw + "\n", encoding="utf-8")
    GEMINI_PARSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    GEMINI_PARSED_LOG.write_text(safe_json + "\n", encoding="utf-8")
    top_keys = ", ".join(parsed.keys()) if isinstance(parsed, dict) else "<non-object root>"
    details = (
        f"Provider: gemini\nModel: {model}\n"
        f"Input note count: {input_note_count}\n"
        f"Top-level keys: {top_keys or '<none>'}\n"
        f"Schema validation error: {schema_error}\n\n"
        f"Raw response preview:\n{safe_raw[:500]}"
    )
    LOGGER.error("Gemini schema validation failed: %s; parsed response: %s", schema_error, safe_json)
    return details


class GeminiProvider(AiProvider):
    provider_name = "gemini"
    def list_models(self):
        key = quote(self.settings["api_key"], safe="")
        response = self._get_json(
            "https://generativelanguage.googleapis.com/v1beta/models?key=" + key
        )
        models = []
        for item in response.get("models", []):
            if "generateContent" not in item.get("supportedGenerationMethods", []):
                continue
            name = str(item.get("name", ""))
            if name.startswith("models/"):
                name = name[7:]
            if name:
                models.append(name)
        return sorted(set(models))
    def _request(self, prompt, payload, test=False):
        model = quote(self.settings["model"], safe="")
        key = quote(self.settings["api_key"], safe="")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        text = (
            prompt
            if test
            else prompt
            + f"\n\nInput note count: {len(payload)}"
            + "\n\nNotes JSON:\n"
            + json.dumps(payload, separators=(",", ":"))
        )
        serialized_payload = json.dumps(payload, separators=(",", ":"))
        output_token_budget = 1024 if test else max(
            1024, min(8192, len(serialized_payload) // 8 + 512)
        )
        generation_config = {
            "responseMimeType": "application/json",
            "maxOutputTokens": output_token_budget,
        }
        # The project calls generateContent via REST rather than a Gemini SDK.
        generation_config["responseJsonSchema"] = GEMINI_RESPONSE_SCHEMA
        model_name = self.settings["model"].lower()
        if model_name.startswith("gemini-3"):
            generation_config["thinkingConfig"] = {"thinkingLevel": "low"}
        elif model_name.startswith("gemini-2.5-flash"):
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}
        body = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": generation_config,
        }
        if not test:
            GEMINI_REQUEST_LOG.parent.mkdir(parents=True, exist_ok=True)
            GEMINI_REQUEST_LOG.write_text(
                json.dumps(
                    {
                        "model": self.settings["model"],
                        "input_note_count": len(payload),
                        "lightweight_ai_notes": payload,
                        "prompt": prompt,
                        "generation_config": generation_config,
                        "request_body": body,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return self._post_json(url, body, {"Content-Type": "application/json"})
    def _text(self, response):
        try:
            text = "".join(part.get("text", "") for part in response["candidates"][0]["content"]["parts"])
            if text:
                return text
        except (KeyError, IndexError, TypeError):
            pass
        candidates = response.get("candidates") or []
        finish_reason = candidates[0].get("finishReason", "unknown") if candidates else "no candidates"
        block_reason = (response.get("promptFeedback") or {}).get("blockReason", "")
        safe_envelope = redact_secret(
            json.dumps(response, ensure_ascii=False, indent=2),
            self.settings.get("api_key", ""),
        )
        details = (
            f"Provider: gemini\nModel: {self.settings.get('model', '')}\n"
            f"Finish reason: {finish_reason}\n"
            f"Prompt block reason: {block_reason or 'none'}\n\n"
            f"API response preview:\n{safe_envelope[:500]}"
        )
        raise ProviderError(
            f"Gemini returned no text (finish reason: {finish_reason}).",
            "invalid_response",
            details=details,
        )
    def test_connection(self):
        try:
            parsed = _parse_gemini_json(
                self._text(self._request(
                    'Return exactly {"removed_ids":[],"explanation":"connection test"}.',
                    [], True,
                ))
            )
            normalize_removal_result(parsed, [])
            return ProviderTestResult(True, "connected", "Connected")
        except ProviderError as exc:
            return ProviderTestResult(False, exc.status, str(exc))
        except (ValueError, TypeError) as exc:
            return ProviderTestResult(False, "invalid_response", f"Gemini returned invalid JSON: {exc}")
    def optimize_midi(self, prompt, payload):
        response = self._request(prompt, payload)
        raw = self._text(response)
        finish_reason = str(
            (response.get("candidates") or [{}])[0].get("finishReason", "")
        ).upper()
        if finish_reason in {"MAX_TOKENS", "MAX_OUTPUT_TOKENS"}:
            error = ValueError(
                "Gemini truncated the optimizer response at the output token limit."
            )
            try:
                details = _save_invalid_response(
                    raw, self.settings.get("api_key", ""), error
                )
            except OSError as save_error:
                details = f"Truncation error: {error}\nCould not save diagnostics: {save_error}"
            raise ProviderError(
                "Gemini response was truncated before removed_ids were returned.",
                "invalid_response",
                details=details,
            )
        try:
            parsed = _parse_gemini_json(raw)
        except (ValueError, TypeError) as exc:
            try:
                details = _save_invalid_response(raw, self.settings.get("api_key", ""), exc)
            except OSError as save_error:
                details = f"Parsing error: {exc}\nCould not save diagnostic file: {save_error}\n\nRaw response preview:\n{redact_secret(raw, self.settings.get('api_key', ''))[:500]}"
            raise ProviderError(
                "Gemini returned invalid JSON.", "invalid_response", details=details
            ) from exc
        try:
            removed_ids, explanation = normalize_removal_result(
                parsed, (note.get("id") for note in payload)
            )
        except (TypeError, ValueError) as exc:
            try:
                details = _save_schema_diagnostics(
                    raw, parsed, self.settings.get("api_key", ""),
                    self.settings.get("model", ""), exc, len(payload)
                )
            except OSError as save_error:
                details = (
                    f"Provider: gemini\nModel: {self.settings.get('model', '')}\n"
                    f"Input note count: {len(payload)}\n"
                    f"Schema validation error: {exc}\nCould not save diagnostics: {save_error}\n\n"
                    f"Raw response preview:\n{redact_secret(raw, self.settings.get('api_key', ''))[:500]}"
                )
            raise ProviderError(
                str(exc),
                "invalid_response",
                details=details,
            ) from exc
        usage = response.get("usageMetadata", {})
        return self._normalized_removals(removed_ids, explanation, {"input_tokens": usage.get("promptTokenCount"), "output_tokens": usage.get("candidatesTokenCount")})
