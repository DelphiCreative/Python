import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = APP_DIR / "prompts"
CUSTOM_PROMPTS_DIR = APP_DIR / "custom_prompts"
DATA_DIR = APP_DIR / "data"
HISTORY_DB_PATH = DATA_DIR / "history.db"

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").strip().lower()
DEFAULT_PROMPT_FILE = os.getenv("DEFAULT_PROMPT_FILE", "compare_prompt.md")
DEFAULT_RESPONSE_LANGUAGE = os.getenv("DEFAULT_RESPONSE_LANGUAGE", "Portuguese (Brazil)")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120"))
MAX_FILE_SIZE_KB = int(os.getenv("MAX_FILE_SIZE_KB", "300"))
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "20"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")

CUSTOM_PROMPTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
