"""Provider-neutral contracts and safe network error handling."""
import json
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib import error, request

from ai_settings import redact_secret

@dataclass(frozen=True)
class ProviderTestResult:
    success: bool
    status: str
    message: str

class ProviderError(RuntimeError):
    def __init__(self, message, status="request_failed", details=""):
        super().__init__(message)
        self.status = status
        self.details = details


def normalize_removal_result(parsed, valid_ids):
    """Validate the common ID-only KEEP/REMOVE provider response."""
    if not isinstance(parsed, dict):
        raise ValueError("The JSON root must be an object.")
    if "notes" in parsed or "removed_notes" in parsed:
        raise ValueError(
            "The obsolete note-object response shape is not accepted; "
            "return removed_ids only."
        )
    removed_ids = parsed.get("removed_ids")
    if not isinstance(removed_ids, list):
        raise ValueError('The root object must contain a "removed_ids" array.')
    explanation = parsed.get("explanation", "")
    if not isinstance(explanation, str):
        raise ValueError("explanation must be a string when provided.")
    valid_ids = set(valid_ids)
    normalized = []
    seen = set()
    for index, note_id in enumerate(removed_ids):
        if isinstance(note_id, bool) or not isinstance(note_id, int):
            raise ValueError(f"removed_ids[{index}] must be an integer.")
        if note_id not in valid_ids:
            raise ValueError(f"removed_ids[{index}] is not present in the input.")
        if note_id not in seen:
            seen.add(note_id)
            normalized.append(note_id)
    return normalized, explanation

class AiProvider(ABC):
    provider_name = ""
    def __init__(self, settings): self.settings = dict(settings)
    @abstractmethod
    def test_connection(self): raise NotImplementedError
    @abstractmethod
    def optimize_midi(self, prompt, payload): raise NotImplementedError
    def list_models(self):
        return []

    def _post_json(self, url, body, headers):
        req = request.Request(url, json.dumps(body).encode(), headers=headers, method="POST")
        retries = max(0, int(self.settings.get("max_retries", 0)))
        for attempt in range(retries + 1):
            try:
                with request.urlopen(req, timeout=max(1, int(self.settings.get("timeout_seconds", 60)))) as response:
                    return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                status = "invalid_key" if exc.code in (401, 403) else "model_not_found" if exc.code == 404 else "quota_error" if exc.code == 429 else "request_failed"
                if status != "request_failed" or attempt == retries:
                    messages = {
                        "invalid_key": "Authentication failed",
                        "model_not_found": f"Model not found: {self.settings.get('model', '')}",
                        "quota_error": "Quota exceeded",
                    }
                    raise ProviderError(messages.get(status, f"Provider request failed (HTTP {exc.code})."), status) from None
            except (TimeoutError, socket.timeout):
                if attempt == retries: raise ProviderError("Network timeout", "timeout") from None
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                if attempt == retries:
                    raise ProviderError("AI request failed: " + redact_secret(exc, self.settings.get("api_key", ""))) from None
            time.sleep(min(2 ** attempt, 4))

    def _get_json(self, url, headers=None):
        req = request.Request(url, headers=headers or {}, method="GET")
        try:
            with request.urlopen(req, timeout=max(1, int(self.settings.get("timeout_seconds", 60)))) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            status = "invalid_key" if exc.code in (401, 403) else "quota_error" if exc.code == 429 else "request_failed"
            message = "Authentication failed" if status == "invalid_key" else "Quota exceeded" if status == "quota_error" else f"Model retrieval failed (HTTP {exc.code})"
            raise ProviderError(message, status) from None
        except (TimeoutError, socket.timeout):
            raise ProviderError("Network timeout", "timeout") from None
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise ProviderError("Model retrieval failed: " + redact_secret(exc, self.settings.get("api_key", ""))) from None

    def _normalized(self, notes, explanation="", usage=None):
        usage = usage or {}
        return {"notes": notes, "explanation": explanation or "", "provider": self.provider_name,
                "model": self.settings.get("model", ""), "usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")}}
    def _normalized_removals(self, removed_ids, explanation="", usage=None):
        usage = usage or {}
        return {
            "removed_ids": list(removed_ids),
            "explanation": explanation or "",
            "provider": self.provider_name,
            "model": self.settings.get("model", ""),
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            },
        }
