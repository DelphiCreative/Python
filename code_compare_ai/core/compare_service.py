from core.models import CompareRequest, ProviderConfig, StructuredCompareResult
from core.result_parser import parse_structured_result
from providers.factory import get_provider


class CompareService:
    def compare(self, request: CompareRequest, provider_config: ProviderConfig) -> StructuredCompareResult:
        provider = get_provider(provider_config)
        raw_response = provider.generate_text(request.prompt_text)
        return parse_structured_result(raw_response)
