"""Google Gemini generateContent provider."""
import json
import logging
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote
from ai_settings import redact_secret
from .base import AiProvider, ProviderError, ProviderTestResult

LOGGER = logging.getLogger(__name__)
GEMINI_RESPONSE_LOG = Path("logs") / "last_gemini_response.txt"
GEMINI_PARSED_LOG = Path("logs") / "last_gemini_response.json"
CHECKED_NOTE_PATHS = ("notes", "result.notes", "data.notes", "optimized_notes")
REQUIRED_NOTE_FIELDS = ("start_ms", "duration_ms", "note", "velocity")
GEMINI_OUTPUT_INSTRUCTIONS = """
Return exactly one JSON object.
Do not use Markdown.
Do not include explanatory text outside JSON.
The root object must contain a field named "notes".
"notes" must be a JSON array.
"notes" must contain the complete optimized note collection.
The root object must also contain "removed_notes" as a JSON array.
For every input note intentionally deleted, copy that exact original note into "removed_notes".
Do not put modified or invented notes in "removed_notes".
If no notes are deleted, return an empty "removed_notes" array.
Do not return a single note as the root object.
Do not return only changed notes.
Do not omit unchanged notes.
Even when no changes are required, return all original notes in "notes".
Do not rename "notes" to "optimized_notes", "result", or another field.
""".strip()
GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["notes", "removed_notes", "explanation"],
    "additionalProperties": False,
    "propertyOrdering": ["notes", "removed_notes", "explanation"],
    "properties": {
        "notes": {
            "type": "array",
            "description": "The complete optimized note collection, including unchanged notes.",
            "items": {
                "type": "object",
                "required": list(REQUIRED_NOTE_FIELDS),
                "additionalProperties": False,
                "properties": {
                    "start_ms": {"type": "integer", "minimum": 0},
                    "duration_ms": {"type": "integer", "minimum": 1},
                    "note": {"type": "integer", "minimum": 0, "maximum": 127},
                    "velocity": {"type": "integer", "minimum": 1, "maximum": 127},
                },
            },
        },
        "removed_notes": {
            "type": "array",
            "description": "Exact copies of input notes intentionally deleted from the optimized collection.",
            "items": {
                "type": "object",
                "required": list(REQUIRED_NOTE_FIELDS),
                "additionalProperties": False,
                "properties": {
                    "start_ms": {"type": "integer", "minimum": 0},
                    "duration_ms": {"type": "integer", "minimum": 1},
                    "note": {"type": "integer", "minimum": 0, "maximum": 127},
                    "velocity": {"type": "integer", "minimum": 1, "maximum": 127},
                },
            },
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


def _save_schema_diagnostics(
    raw, parsed, api_key, model, schema_error, input_note_count, output_note_count
):
    safe_raw = redact_secret(raw, api_key)
    safe_json = redact_secret(
        json.dumps(parsed, ensure_ascii=False, indent=2), api_key
    )
    GEMINI_RESPONSE_LOG.parent.mkdir(parents=True, exist_ok=True)
    GEMINI_RESPONSE_LOG.write_text(safe_raw + "\n", encoding="utf-8")
    GEMINI_PARSED_LOG.parent.mkdir(parents=True, exist_ok=True)
    GEMINI_PARSED_LOG.write_text(safe_json + "\n", encoding="utf-8")
    top_keys = ", ".join(parsed.keys()) if isinstance(parsed, dict) else "<non-object root>"
    checked = "\n".join(f"- {path}" for path in CHECKED_NOTE_PATHS)
    details = (
        f"Provider: gemini\nModel: {model}\n"
        f"Input note count: {input_note_count}\n"
        f"Output note count: {output_note_count if output_note_count is not None else 'unknown'}\n"
        f"Top-level keys: {top_keys or '<none>'}\n"
        f"Checked paths:\n{checked}\n"
        f"Schema validation error: {schema_error}\n\n"
        f"Raw response preview:\n{safe_raw[:500]}"
    )
    LOGGER.error("Gemini schema validation failed: %s; parsed response: %s", schema_error, safe_json)
    return details


def _note_identity(note_item):
    return tuple(int(note_item[field]) for field in REQUIRED_NOTE_FIELDS)


def _normalize_gemini_payload(parsed, input_notes):
    input_note_count = len(input_notes)
    if not isinstance(parsed, dict):
        raise ValueError("The JSON root is not an object.")
    if all(field in parsed for field in REQUIRED_NOTE_FIELDS):
        raise ValueError(
            "Gemini returned one note instead of the required notes array."
        )
    if "explanation" not in parsed or not isinstance(parsed.get("explanation"), str):
        raise ValueError('The root object must contain a string field named "explanation".')
    candidates = (
        ("notes", parsed.get("notes"), parsed),
        ("result.notes", parsed.get("result", {}).get("notes") if isinstance(parsed.get("result"), dict) else None, parsed.get("result")),
        ("data.notes", parsed.get("data", {}).get("notes") if isinstance(parsed.get("data"), dict) else None, parsed.get("data")),
        ("optimized_notes", parsed.get("optimized_notes"), parsed),
    )
    selected_path = None
    notes = None
    container = parsed
    for path, value, owner in candidates:
        if value is not None:
            selected_path, notes, container = path, value, owner
            break
    if selected_path is None:
        raise KeyError("No notes field was found.")
    if not isinstance(notes, list):
        raise TypeError(f"{selected_path} must be a JSON array, not {type(notes).__name__}.")
    for index, note_item in enumerate(notes):
        if not isinstance(note_item, dict):
            raise TypeError(f"{selected_path}[{index}] must be an object.")
        missing = [field for field in REQUIRED_NOTE_FIELDS if field not in note_item]
        if missing:
            raise ValueError(f"{selected_path}[{index}] is missing required fields: {', '.join(missing)}.")
        try:
            start_ms = int(note_item["start_ms"])
            duration_ms = int(note_item["duration_ms"])
            midi_note = int(note_item["note"])
            velocity = int(note_item["velocity"])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{selected_path}[{index}] contains non-numeric note fields."
            ) from exc
        if start_ms < 0 or duration_ms <= 0 or not 0 <= midi_note <= 127 or not 1 <= velocity <= 127:
            raise ValueError(
                f"{selected_path}[{index}] contains invalid MIDI note values."
            )
    removed_notes = parsed.get("removed_notes")
    if removed_notes is None:
        removed_notes = []
    if not isinstance(removed_notes, list):
        raise TypeError("removed_notes must be a JSON array.")
    input_identities = Counter(_note_identity(note) for note in input_notes)
    removed_identities = Counter()
    for index, removed_note in enumerate(removed_notes):
        if not isinstance(removed_note, dict):
            raise TypeError(f"removed_notes[{index}] must be an object.")
        missing = [field for field in REQUIRED_NOTE_FIELDS if field not in removed_note]
        if missing:
            raise ValueError(
                f"removed_notes[{index}] is missing required fields: {', '.join(missing)}."
            )
        try:
            identity = _note_identity(removed_note)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"removed_notes[{index}] contains non-numeric fields.") from exc
        removed_identities[identity] += 1
        if removed_identities[identity] > input_identities[identity]:
            raise ValueError(
                f"removed_notes[{index}] does not match an available input note."
            )
    if input_note_count and len(notes) * 2 < input_note_count:
        expected_removed = input_note_count - len(notes)
        if len(removed_notes) != expected_removed:
            raise ValueError(
                f"AI returned only {len(notes)} of {input_note_count} notes and supplied "
                f"{len(removed_notes)} verified deletions; {expected_removed} are required. "
                "The result was rejected to prevent data loss."
            )
    explanation = parsed.get("explanation", "")
    if not explanation and isinstance(container, dict):
        explanation = container.get("explanation", "")
    return notes, str(explanation or "")

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
        text = prompt if test else prompt + "\n\n" + GEMINI_OUTPUT_INSTRUCTIONS + f"\n\nInput note count: {len(payload)}" + "\n\nNotes JSON:\n" + json.dumps(payload, separators=(",", ":"))
        serialized_payload = json.dumps(payload, separators=(",", ":"))
        # A complete optimizer result is roughly the size of its input JSON.
        # 4096 tokens truncated dense MIDI chunks, so scale the budget with the
        # payload while keeping a bounded ceiling supported by current models.
        output_token_budget = 1024 if test else max(
            16384, min(65536, len(serialized_payload) // 2 + 4096)
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
        body = {"contents": [{"role": "user", "parts": [{"text": text}]}], "generationConfig": generation_config}
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
                    'Return exactly {"notes":[],"removed_notes":[],"explanation":"connection test"}.',
                    [], True,
                ))
            )
            _normalize_gemini_payload(parsed, [])
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
                "Gemini response was truncated before the complete notes array was returned.",
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
            notes, explanation = _normalize_gemini_payload(parsed, payload)
        except (KeyError, TypeError, ValueError) as exc:
            output_count = None
            if isinstance(parsed, dict):
                for candidate in (
                    parsed.get("notes"), parsed.get("optimized_notes"),
                    parsed.get("result", {}).get("notes") if isinstance(parsed.get("result"), dict) else None,
                    parsed.get("data", {}).get("notes") if isinstance(parsed.get("data"), dict) else None,
                ):
                    if isinstance(candidate, list):
                        output_count = len(candidate)
                        break
            try:
                details = _save_schema_diagnostics(
                    raw, parsed, self.settings.get("api_key", ""),
                    self.settings.get("model", ""), exc, len(payload), output_count
                )
            except OSError as save_error:
                details = (
                    f"Provider: gemini\nModel: {self.settings.get('model', '')}\n"
                    f"Input note count: {len(payload)}\nOutput note count: {output_count if output_count is not None else 'unknown'}\n"
                    f"Schema validation error: {exc}\nCould not save diagnostics: {save_error}\n\n"
                    f"Raw response preview:\n{redact_secret(raw, self.settings.get('api_key', ''))[:500]}"
                )
            error_message = str(exc)
            if not (
                error_message.startswith("Gemini returned one note")
                or error_message.startswith("AI returned only")
            ):
                error_message = "Gemini returned valid JSON, but no MIDI notes were found."
            raise ProviderError(
                error_message,
                "invalid_response",
                details=details,
            ) from exc
        usage = response.get("usageMetadata", {})
        return self._normalized(notes, explanation, {"input_tokens": usage.get("promptTokenCount"), "output_tokens": usage.get("candidatesTokenCount")})
