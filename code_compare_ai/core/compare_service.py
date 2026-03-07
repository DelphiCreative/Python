from core.models import CompareRequest, ProviderConfig
from providers.factory import get_provider


class CompareService:
    def compare(self, request: CompareRequest, provider_config: ProviderConfig) -> str:
        provider = get_provider(provider_config)
        prompt = request.prompt_text
        return provider.generate_text(prompt)
