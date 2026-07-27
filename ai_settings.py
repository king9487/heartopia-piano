"""Local, secret-bearing AI provider settings.

The example configuration may live in bundled resources, but the runtime file
is always resolved to a writable location.
"""

import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path


PROVIDER_DISABLED = "disabled"
PROVIDER_OPENAI = "openai"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"
VALID_AI_PROVIDERS = {
    PROVIDER_DISABLED, PROVIDER_OPENAI, PROVIDER_GEMINI,
    PROVIDER_OPENAI_COMPATIBLE,
}

DEFAULT_AI_SETTINGS = {
    "provider": PROVIDER_DISABLED,
    "api_keys": {name: "" for name in (
        PROVIDER_OPENAI, PROVIDER_GEMINI, PROVIDER_OPENAI_COMPATIBLE
    )},
    "models": {name: "" for name in (
        PROVIDER_OPENAI, PROVIDER_GEMINI, PROVIDER_OPENAI_COMPATIBLE
    )},
    "openai_compatible_base_url": "",
    "timeout_seconds": 60,
    "max_retries": 2,
}


def _project_root():
    return Path(__file__).resolve().parent


def _is_writable_directory(path):
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ai_settings_write_test"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def get_ai_settings_path():
    override = os.environ.get("YOUTUBE_TO_MIDI_AI_SETTINGS")
    if override:
        return Path(override)
    if not getattr(sys, "frozen", False):
        return _project_root() / "config" / "ai_settings.json"
    executable_config = Path(sys.executable).resolve().parent / "config"
    if _is_writable_directory(executable_config):
        return executable_config / "ai_settings.json"
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    return Path(base or (Path.home() / ".config")) / "youtube_to_midi" / "ai_settings.json"


def _coerce_int(value, default, minimum=0):
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _provider_name(value):
    value = str(value or "").strip().lower().replace("-", "_")
    return value if value in VALID_AI_PROVIDERS else PROVIDER_DISABLED


def _normalize_settings(settings):
    source = settings if isinstance(settings, dict) else {}
    result = deepcopy(DEFAULT_AI_SETTINGS)
    result["provider"] = _provider_name(source.get("provider"))
    for group in ("api_keys", "models"):
        values = source.get(group, {})
        if isinstance(values, dict):
            for provider in result[group]:
                result[group][provider] = str(values.get(provider, "") or "").strip()

    # Read the previous single-provider schema so existing users do not lose settings.
    active = result["provider"]
    if active != PROVIDER_DISABLED:
        if "api_key" in source and not result["api_keys"][active]:
            result["api_keys"][active] = str(source.get("api_key") or "").strip()
        if "model" in source and not result["models"][active]:
            result["models"][active] = str(source.get("model") or "").strip()
    result["openai_compatible_base_url"] = str(
        source.get("openai_compatible_base_url", source.get("base_url", "")) or ""
    ).strip()
    result["timeout_seconds"] = _coerce_int(
        source.get("timeout_seconds"), 60, minimum=1
    )
    result["max_retries"] = _coerce_int(source.get("max_retries"), 2)
    return result


def load_ai_settings():
    path = get_ai_settings_path()
    if not path.exists():
        return deepcopy(DEFAULT_AI_SETTINGS)
    try:
        return _normalize_settings(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return deepcopy(DEFAULT_AI_SETTINGS)


def save_ai_settings(settings):
    normalized = _normalize_settings(settings)
    path = get_ai_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def get_active_provider_settings(settings=None):
    settings = _normalize_settings(load_ai_settings() if settings is None else settings)
    provider = settings["provider"]
    return {
        "provider": provider,
        "api_key": settings["api_keys"].get(provider, ""),
        "model": settings["models"].get(provider, ""),
        "base_url": settings["openai_compatible_base_url"] if provider == PROVIDER_OPENAI_COMPATIBLE else "",
        "timeout_seconds": settings["timeout_seconds"],
        "max_retries": settings["max_retries"],
    }


def clear_provider_key(provider):
    settings = load_ai_settings()
    provider = _provider_name(provider)
    if provider in settings["api_keys"]:
        settings["api_keys"][provider] = ""
    return save_ai_settings(settings)


def redact_secret(value, secrets=None):
    text = str(value)
    if secrets is None:
        secrets = load_ai_settings().get("api_keys", {}).values()
    elif isinstance(secrets, str):
        secrets = (secrets,)
    for secret in sorted((str(s) for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+", r"\1[REDACTED]", text)
    return text


def validate_ai_settings(settings=None):
    active = get_active_provider_settings(settings)
    if active["provider"] == PROVIDER_DISABLED:
        return False, []
    errors = []
    if not active["api_key"]:
        errors.append("AI API key is not configured.")
    if not active["model"]:
        errors.append("AI model is not configured.")
    if active["provider"] == PROVIDER_OPENAI_COMPATIBLE and not active["base_url"]:
        errors.append("Base URL is required for OpenAI-compatible providers.")
    return not errors, errors


# Compatibility aliases for callers from the previous settings implementation.
clear_ai_api_key = lambda: clear_provider_key(load_ai_settings()["provider"])
redact_api_key = redact_secret
