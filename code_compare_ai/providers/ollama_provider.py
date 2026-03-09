import requests
from requests import exceptions as req_exc

from providers.base import BaseProvider


class OllamaProvider(BaseProvider):
    def _truncate_prompt(self, prompt: str) -> str:
        max_chars = getattr(self.config, "max_prompt_chars", 0) or 0
        if max_chars and len(prompt) > max_chars:
            suffix = "\n\n[Prompt truncated for local Ollama execution due to context limit.]"
            safe_limit = max(0, max_chars - len(suffix))
            return prompt[:safe_limit] + suffix
        return prompt

    def generate_text(self, prompt: str) -> str:
        base_url = self.config.base_url.rstrip("/")
        if not base_url:
            raise ValueError("Ollama Base URL is required.")

        url = base_url + "/api/generate"
        payload = {
            "model": self.config.model_name,
            "prompt": self._truncate_prompt(prompt),
            "stream": False,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
        except req_exc.ReadTimeout as exc:
            raise RuntimeError(
                "Ollama response timed out. Try a smaller file, Diff Review mode, "
                "or increase OLLAMA_TIMEOUT_SECONDS / reduce OLLAMA_MAX_PROMPT_CHARS."
            ) from exc
        except req_exc.ConnectionError as exc:
            raise RuntimeError(
                "Could not connect to Ollama. Check if Ollama is running and the Base URL is correct."
            ) from exc
        except req_exc.HTTPError as exc:
            details = ""
            try:
                details = exc.response.text.strip()
            except Exception:
                details = ""
            raise RuntimeError(
                "Ollama returned an HTTP error: {0}".format(details or str(exc))
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError("Unexpected Ollama request error: {0}".format(exc)) from exc

        data = response.json()
        return data.get("response", "").strip()
