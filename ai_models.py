"""Built-in provider model choices and provider-switch selection helpers."""

PROVIDER_MODELS = {
    "openai": ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
    "gemini": [
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
    ],
    "openai_compatible": [],
}

DEFAULT_PROVIDER_MODELS = {
    provider: models[0] if models else ""
    for provider, models in PROVIDER_MODELS.items()
}


def model_values_for_provider(provider, discovered=None):
    """Return stable, de-duplicated choices with discovered models first."""
    values = list(discovered or []) + list(PROVIDER_MODELS.get(provider, []))
    return tuple(dict.fromkeys(value for value in values if value))


def selected_model_for_provider(provider, saved_models):
    """Use only this provider's saved model, otherwise its recommended default."""
    saved = str((saved_models or {}).get(provider, "") or "").strip()
    return saved or DEFAULT_PROVIDER_MODELS.get(provider, "")
