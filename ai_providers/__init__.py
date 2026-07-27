"""AI provider selection and public provider types."""

from ai_settings import PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_OPENAI_COMPATIBLE
from .base import AiProvider, ProviderError, ProviderTestResult
from .gemini_provider import GeminiProvider
from .openai_compatible_provider import OpenAICompatibleProvider
from .openai_provider import OpenAIProvider


def create_provider(settings):
    providers = {
        PROVIDER_OPENAI: OpenAIProvider,
        PROVIDER_GEMINI: GeminiProvider,
        PROVIDER_OPENAI_COMPATIBLE: OpenAICompatibleProvider,
    }
    provider = settings.get("provider")
    if provider not in providers:
        raise ProviderError("AI provider is disabled or unsupported", status="disabled")
    return providers[provider](settings)


__all__ = ["AiProvider", "ProviderError", "ProviderTestResult", "create_provider"]
