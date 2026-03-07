from dataclasses import dataclass


@dataclass
class CompareRequest:
    file_a_name: str
    file_b_name: str
    code_a: str
    code_b: str
    prompt_text: str
    response_language: str
    provider_name: str
    model_name: str


@dataclass
class ProviderConfig:
    provider_name: str
    model_name: str
    api_key: str = ""
    base_url: str = ""
    timeout_seconds: int = 120
