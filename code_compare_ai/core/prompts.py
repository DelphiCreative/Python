from pathlib import Path
from typing import List

from config import CUSTOM_PROMPTS_DIR, DEFAULT_PROMPT_FILE, PROMPTS_DIR


def list_prompt_files() -> List[str]:
    prompt_names = []

    if PROMPTS_DIR.exists():
        prompt_names.extend(sorted([p.name for p in PROMPTS_DIR.glob("*.md")]))

    if CUSTOM_PROMPTS_DIR.exists():
        prompt_names.extend(sorted([p.name for p in CUSTOM_PROMPTS_DIR.glob("*.md")]))

    # preserve order while removing duplicates
    seen = set()
    unique_names = []
    for name in prompt_names:
        if name not in seen:
            seen.add(name)
            unique_names.append(name)

    return unique_names


def resolve_prompt_path(prompt_name: str) -> Path:
    custom_path = CUSTOM_PROMPTS_DIR / prompt_name
    if custom_path.exists():
        return custom_path

    default_path = PROMPTS_DIR / prompt_name
    if default_path.exists():
        return default_path

    raise FileNotFoundError("Prompt file not found: {0}".format(prompt_name))


def load_prompt_template(prompt_name: str = DEFAULT_PROMPT_FILE) -> str:
    path = resolve_prompt_path(prompt_name)
    return path.read_text(encoding="utf-8")


def save_custom_prompt(prompt_name: str, content: str) -> Path:
    safe_name = prompt_name.strip()
    if not safe_name:
        raise ValueError("Prompt name cannot be empty.")

    if not safe_name.lower().endswith(".md"):
        safe_name += ".md"

    path = CUSTOM_PROMPTS_DIR / safe_name
    path.write_text(content, encoding="utf-8")
    return path


def build_compare_prompt(
    template: str,
    file_a_name: str,
    file_b_name: str,
    code_a: str,
    code_b: str,
    response_language: str,
) -> str:
    return (
        template
        .replace("{{response_language}}", response_language)
        .replace("{{file_a_name}}", file_a_name)
        .replace("{{file_b_name}}", file_b_name)
        .replace("{{code_a}}", code_a)
        .replace("{{code_b}}", code_b)
    )
