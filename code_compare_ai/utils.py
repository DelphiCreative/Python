import difflib
import re
import subprocess
from pathlib import Path


TEXT_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
TEXT_FILE_EXTENSIONS = {
    ".pas", ".dpr", ".dpk", ".dproj", ".dfm", ".fmx", ".inc",
    ".lpr", ".lpi", ".lfm", ".pp", ".cs", ".py", ".sql", ".js",
    ".ts", ".java", ".json", ".xml", ".vb", ".bas", ".txt", ".md",
    ".yml", ".yaml", ".ini", ".cfg", ".bat", ".ps1", ".sh", ".html",
    ".css", ".jsx", ".tsx", ".mjs", ".cjs",
}


def _normalize_file_name(file_name: str) -> str:
    raw_name = (file_name or "").strip()
    if not raw_name:
        return ""

    cleaned = raw_name.strip("\"'`")
    cleaned = cleaned.replace('\\', '/')
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    cleaned = cleaned.rsplit("/", 1)[-1]
    cleaned = cleaned.strip().strip("\"'`")

    cleaned = re.sub(r'\\(["\\])', r'\1', cleaned)
    cleaned = cleaned.rstrip("\"'`)]}")
    return cleaned.lower()


def read_uploaded_file(uploaded_file) -> str:
    raw = uploaded_file.getvalue()

    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError("Could not decode uploaded file: {0}".format(uploaded_file.name))


def read_text_file(file_path: str) -> str:
    raw = Path(file_path).read_bytes()
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode file: {0}".format(file_path))


def detect_language_from_extension(file_name: str) -> str:
    normalized_name = _normalize_file_name(file_name)
    suffixes = Path(normalized_name).suffixes

    language_by_name = {
        "dockerfile": "docker",
        "makefile": "makefile",
    }
    if normalized_name in language_by_name:
        return language_by_name[normalized_name]

    language_by_suffix = {
        ".pas": "pascal",
        ".dpr": "pascal",
        ".dpk": "pascal",
        ".dproj": "xml",
        ".dfm": "pascal",
        ".fmx": "pascal",
        ".inc": "pascal",
        ".lpr": "pascal",
        ".lpi": "xml",
        ".lfm": "pascal",
        ".pp": "pascal",
        ".cs": "csharp",
        ".py": "python",
        ".sql": "sql",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".json": "json",
        ".xml": "xml",
        ".vb": "vbnet",
        ".bas": "vb",
        ".html": "html",
        ".css": "css",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".md": "markdown",
    }

    if len(suffixes) >= 2:
        combined_suffix = "".join(suffixes[-2:])
        combined_mapping = {
            ".d.ts": "typescript",
            ".spec.ts": "typescript",
            ".test.ts": "typescript",
            ".spec.js": "javascript",
            ".test.js": "javascript",
        }
        if combined_suffix in combined_mapping:
            return combined_mapping[combined_suffix]

    ext = suffixes[-1] if suffixes else ""
    return language_by_suffix.get(ext, "text")


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


def _run_git(repo_path: str, args):
    command = ["git", "-C", repo_path] + list(args)
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


class GitError(RuntimeError):
    pass


def is_git_repo(repo_path: str) -> bool:
    repo_path = (repo_path or "").strip()
    if not repo_path:
        return False
    result = _run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def is_supported_text_file(file_path: str) -> bool:
    normalized_name = _normalize_file_name(file_path)
    suffixes = Path(normalized_name).suffixes
    ext = suffixes[-1] if suffixes else ""
    return ext in TEXT_FILE_EXTENSIONS


def get_git_modified_files(repo_path: str, include_untracked: bool = True):
    if not is_git_repo(repo_path):
        raise GitError("Invalid Git repository path.")

    result = _run_git(repo_path, ["status", "--porcelain"])
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or "Unable to read git status.")

    files = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        status_code = line[:2]
        raw_path = line[3:].strip()
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1].strip()

        if not is_supported_text_file(raw_path):
            continue

        if status_code == "??":
            if include_untracked:
                files.append({"path": raw_path, "status": "untracked"})
            continue

        normalized = status_code.replace(" ", "")
        if "D" in normalized or "U" in normalized:
            continue

        status_label = "modified"
        if "A" in normalized:
            status_label = "added"
        elif "R" in normalized:
            status_label = "renamed"
        elif "M" in normalized:
            status_label = "modified"

        files.append({"path": raw_path, "status": status_label})

    files.sort(key=lambda item: item["path"].lower())
    return files


def get_git_file_pair(repo_path: str, relative_path: str):
    relative_path = relative_path.replace("\\", "/")
    worktree_path = str(Path(repo_path) / Path(relative_path))

    if not Path(worktree_path).exists():
        raise GitError("File not found in working tree: {0}".format(relative_path))

    new_code = read_text_file(worktree_path)

    old_result = _run_git(repo_path, ["show", "HEAD:{0}".format(relative_path)])
    if old_result.returncode == 0:
        old_code = old_result.stdout
        old_label = "HEAD:{0}".format(relative_path)
        status = "modified"
    else:
        old_code = ""
        old_label = "(new file)"
        status = "added"

    return {
        "file_path": relative_path,
        "old_label": old_label,
        "new_label": relative_path,
        "old_code": old_code,
        "new_code": new_code,
        "status": status,
    }
