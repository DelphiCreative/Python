import difflib
from pathlib import Path


TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")


def read_uploaded_file(uploaded_file) -> str:
    raw = uploaded_file.getvalue()

    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError("Could not decode uploaded file: {0}".format(uploaded_file.name))


def detect_language_from_extension(file_name: str) -> str:
    ext = Path(file_name).suffix.lower()

    mapping = {
        ".pas": "pascal",
        ".dpr": "pascal",
        ".cs": "csharp",
        ".py": "python",
        ".sql": "sql",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".json": "json",
        ".xml": "xml",
        ".vb": "vbnet",
        ".bas": "vb",
    }
    return mapping.get(ext, "text")


def generate_unified_diff(file_a_name: str, code_a: str, file_b_name: str, code_b: str, context_lines: int = 3) -> str:
    lines_a = code_a.splitlines()
    lines_b = code_b.splitlines()
    diff_lines = difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile=file_a_name,
        tofile=file_b_name,
        n=context_lines,
        lineterm="",
    )
    return "\n".join(diff_lines)


def count_diff_changes(diff_text: str):
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed
