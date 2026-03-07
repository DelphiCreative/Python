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
