from pathlib import Path
from typing import List

from config import CUSTOM_PROMPTS_DIR, DEFAULT_PROMPT_FILE, PROMPTS_DIR
from utils import detect_language_from_extension


JSON_SCHEMA_INSTRUCTION = """
Return ONLY valid JSON.
Do not wrap the JSON in markdown.
Do not add explanations before or after the JSON.
Use exactly this structure:
{
  "summary": "short technical summary",
  "score": 0,
  "issues": [
    {
      "severity": "low | medium | high | critical",
      "category": "bug | performance | security | code_smell | maintainability | logic | style | refactoring | other",
      "title": "short issue title",
      "description": "clear explanation",
      "file": "file name if applicable",
      "line": 0
    }
  ],
  "suggestions": [
    {
      "title": "short suggestion title",
      "description": "clear suggestion"
    }
  ],
  "changes_detected": ["change 1", "change 2"]
}
If a list is empty, return an empty array.
All values must be in {{response_language}}.
""".strip()

FILE_COMPARE_INSTRUCTION = """
Review mode: file_compare.
Compare the two full files as complete versions of the same source.
Explain the most important functional and technical differences.
Do not pretend there is a diff block available.
""".strip()

MULTI_FILE_INSTRUCTION = """
Review mode: multi_file_review.
This file pair is part of a larger multi-file review.
Focus on the important technical changes for this specific file pair.
Keep the analysis concise and practical because many files may be reviewed in the same batch.
Prioritize bugs, regressions and maintainability issues introduced by the changed lines.
If there are no meaningful code changes, say so clearly.
""".strip()

DIFF_REVIEW_INSTRUCTION = """
Review mode: diff_review.
Focus primarily on the diff block and the modified areas.
Use the full file contents only as supporting context.
Prioritize issues introduced by the changed lines.
If the diff is empty, explain that no meaningful code change was detected.
""".strip()

GIT_REVIEW_INSTRUCTION = """
Review mode: git_review.
This review comes from a local Git repository.
Focus on changes between the HEAD version and the current working tree file.
Prioritize regressions, logic problems, maintainability issues and risks introduced by the uncommitted changes.
If the file is new, evaluate the current implementation quality and call out important risks.
""".strip()

LANGUAGE_TEMPLATE_MAP = {
    "pascal": "delphi_compare_prompt.md",
    "delphi": "delphi_compare_prompt.md",
    "csharp": "csharp_compare_prompt.md",
    "python": "python_compare_prompt.md",
    "sql": "sql_compare_prompt.md",
    "javascript": "javascript_compare_prompt.md",
    "typescript": "javascript_compare_prompt.md",
}


def list_prompt_files() -> List[str]:
    prompt_names = []
    if PROMPTS_DIR.exists():
        prompt_names.extend(sorted([p.name for p in PROMPTS_DIR.glob("*.md")]))
    if CUSTOM_PROMPTS_DIR.exists():
        prompt_names.extend(sorted([p.name for p in CUSTOM_PROMPTS_DIR.glob("*.md")]))

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


def get_effective_prompt_name(selected_prompt_file: str, file_name: str) -> str:
    if selected_prompt_file != DEFAULT_PROMPT_FILE:
        return selected_prompt_file
    language = detect_language_from_extension(file_name)
    return LANGUAGE_TEMPLATE_MAP.get(language, DEFAULT_PROMPT_FILE)


def get_effective_prompt_template(selected_prompt_file: str, file_name: str) -> str:
    return load_prompt_template(get_effective_prompt_name(selected_prompt_file, file_name))


def _replace_common_placeholders(template: str, file_a_name: str, file_b_name: str, code_a: str, code_b: str, response_language: str) -> str:
    return (
        template
        .replace("{{response_language}}", response_language)
        .replace("{{file_a_name}}", file_a_name)
        .replace("{{file_b_name}}", file_b_name)
        .replace("{{code_a}}", code_a)
        .replace("{{code_b}}", code_b)
    )


def build_compare_prompt(template: str, file_a_name: str, file_b_name: str, code_a: str, code_b: str, response_language: str) -> str:
    base_prompt = _replace_common_placeholders(template, file_a_name, file_b_name, code_a, code_b, response_language)
    schema_instruction = JSON_SCHEMA_INSTRUCTION.replace("{{response_language}}", response_language)
    return base_prompt.strip() + "\n\n" + FILE_COMPARE_INSTRUCTION + "\n\n" + schema_instruction


def build_diff_review_prompt(template: str, file_a_name: str, file_b_name: str, code_a: str, code_b: str, diff_text: str, response_language: str) -> str:
    base_prompt = _replace_common_placeholders(template, file_a_name, file_b_name, code_a, code_b, response_language)
    diff_text = diff_text.strip() or "No diff content available."
    schema_instruction = JSON_SCHEMA_INSTRUCTION.replace("{{response_language}}", response_language)
    diff_block = "Unified diff:\n```diff\n{0}\n```".format(diff_text)
    return base_prompt.strip() + "\n\n" + DIFF_REVIEW_INSTRUCTION + "\n\n" + diff_block + "\n\n" + schema_instruction


def build_multi_file_prompt(template: str, file_a_name: str, file_b_name: str, code_a: str, code_b: str, diff_text: str, response_language: str) -> str:
    base_prompt = _replace_common_placeholders(template, file_a_name, file_b_name, code_a, code_b, response_language)
    diff_text = diff_text.strip() or "No diff content available."
    schema_instruction = JSON_SCHEMA_INSTRUCTION.replace("{{response_language}}", response_language)
    diff_block = "Unified diff:\n```diff\n{0}\n```".format(diff_text)
    return base_prompt.strip() + "\n\n" + MULTI_FILE_INSTRUCTION + "\n\n" + diff_block + "\n\n" + schema_instruction


def build_git_review_prompt(template: str, file_a_name: str, file_b_name: str, code_a: str, code_b: str, diff_text: str, response_language: str, repo_path: str) -> str:
    base_prompt = _replace_common_placeholders(template, file_a_name, file_b_name, code_a, code_b, response_language)
    diff_text = diff_text.strip() or "No diff content available."
    schema_instruction = JSON_SCHEMA_INSTRUCTION.replace("{{response_language}}", response_language)
    repo_block = "Repository path: {0}".format(repo_path)
    diff_block = "Unified diff:\n```diff\n{0}\n```".format(diff_text)
    return base_prompt.strip() + "\n\n" + GIT_REVIEW_INSTRUCTION + "\n\n" + repo_block + "\n\n" + diff_block + "\n\n" + schema_instruction