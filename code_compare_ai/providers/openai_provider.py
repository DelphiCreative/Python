from openai import OpenAI

from providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    def generate_text(self, prompt: str) -> str:
        if not self.config.api_key:
            raise ValueError("OpenAI API key is required.")

        client = OpenAI(api_key=self.config.api_key, timeout=self.config.timeout_seconds)
        response = client.responses.create(
            model=self.config.model_name,
            input=prompt,
        )

        output_text = getattr(response, "output_text", "")
        if output_text:
            return output_text.strip()

        return str(response)
