from abc import ABC, abstractmethod

from core.models import ProviderConfig


class BaseProvider(ABC):
    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    def generate_text(self, prompt: str) -> str:
        raise NotImplementedError
