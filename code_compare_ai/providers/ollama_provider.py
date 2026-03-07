import requests

from providers.base import BaseProvider


class OllamaProvider(BaseProvider):
    def generate_text(self, prompt: str) -> str:
        base_url = self.config.base_url.rstrip("/")
        if not base_url:
            raise ValueError("Ollama Base URL is required.")

        url = base_url + "/api/generate"
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "stream": False,
        }

        response = requests.post(
            url,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()

        data = response.json()
        return data.get("response", "").strip()
