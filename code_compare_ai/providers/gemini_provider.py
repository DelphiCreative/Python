from google import genai

from providers.base import BaseProvider


class GeminiProvider(BaseProvider):
    def generate_text(self, prompt: str) -> str:
        if not self.config.api_key:
            raise ValueError("Gemini API key is required.")

        client = genai.Client(api_key=self.config.api_key)
        response = client.models.generate_content(
            model=self.config.model_name,
            contents=prompt,
        )

        text = getattr(response, "text", "")
        if text:
            return text.strip()

        return str(response)
