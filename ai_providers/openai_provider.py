"""OpenAI Responses API provider."""
import json
from .base import AiProvider, ProviderError, ProviderTestResult

class OpenAIProvider(AiProvider):
    provider_name = "openai"
    endpoint = "https://api.openai.com/v1/responses"
    def list_models(self):
        response = self._get_json(
            "https://api.openai.com/v1/models",
            {"Authorization": "Bearer " + self.settings["api_key"]},
        )
        return sorted(item["id"] for item in response.get("data", []) if item.get("id"))
    def _request(self, prompt, payload, test=False):
        content = prompt if test else prompt + "\n\nNotes JSON:\n" + json.dumps(payload, separators=(",", ":"))
        body = {"model": self.settings["model"], "input": [{"role": "user", "content": content}], "max_output_tokens": 16 if test else 4096}
        return self._post_json(self.endpoint, body, {"Authorization": "Bearer " + self.settings["api_key"], "Content-Type": "application/json"})
    @staticmethod
    def _text(response):
        if isinstance(response.get("output_text"), str): return response["output_text"]
        parts = [part.get("text", "") for item in response.get("output", []) for part in item.get("content", []) if part.get("type") in ("output_text", "text")]
        if parts: return "".join(parts)
        choices = response.get("choices", [])
        if choices and isinstance(choices[0].get("message", {}).get("content"), str): return choices[0]["message"]["content"]
        raise ProviderError("Provider returned an invalid response.", "invalid_response")
    def test_connection(self):
        try:
            json.loads(self._text(self._request('Return exactly {"notes":[]}.', [], True)))
            return ProviderTestResult(True, "connected", "Connected")
        except ProviderError as exc: return ProviderTestResult(False, exc.status, str(exc))
        except (ValueError, TypeError): return ProviderTestResult(False, "invalid_response", "Provider returned malformed JSON.")
    def optimize_midi(self, prompt, payload):
        response = self._request(prompt, payload)
        try: parsed = json.loads(self._text(response))
        except (ValueError, TypeError) as exc: raise ProviderError("Provider returned malformed JSON.", "invalid_response") from exc
        notes = parsed.get("notes") if isinstance(parsed, dict) else parsed
        if not isinstance(notes, list): raise ProviderError("Provider response did not contain a notes list.", "invalid_response")
        usage = response.get("usage", {})
        return self._normalized(notes, parsed.get("explanation", "") if isinstance(parsed, dict) else "", {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")})
