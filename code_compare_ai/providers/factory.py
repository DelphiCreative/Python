from core.models import ProviderConfig
from providers.gemini_provider import GeminiProvider
from providers.ollama_provider import OllamaProvider
from providers.openai_provider import OpenAIProvider


def get_provider(config: ProviderConfig):
    name = config.provider_name.strip().lower()

    if name == "gemini":
        return GeminiProvider(config)

    if name == "openai":
        return OpenAIProvider(config)

    if name == "ollama":
        return OllamaProvider(config)

    raise ValueError("Unsupported provider: {0}".format(config.provider_name))
