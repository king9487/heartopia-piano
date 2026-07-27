"""OpenAI Responses API compatible endpoint."""
from .openai_provider import OpenAIProvider

class OpenAICompatibleProvider(OpenAIProvider):
    provider_name = "openai_compatible"
    def list_models(self):
        return []
    @property
    def endpoint(self):
        base = self.settings["base_url"].rstrip("/")
        return base if base.endswith("/responses") else base + ("/responses" if base.endswith("/v1") else "/v1/responses")
