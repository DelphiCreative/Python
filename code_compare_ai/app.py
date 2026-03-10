import json
from datetime import datetime
from html import escape

import streamlit as st

from config import (
    AI_PROVIDER,
    DEFAULT_PROMPT_FILE,
    DEFAULT_RESPONSE_LANGUAGE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GIT_REVIEW_MAX_FILES,
    MAX_MULTI_FILE_PAIRS,
    HISTORY_LIMIT,
    MAX_FILE_SIZE_KB,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    OLLAMA_MAX_PROMPT_CHARS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from core.compare_service import CompareService
from core.models import CompareRequest, ProviderConfig, StructuredCompareResult
from core.prompts import (
    build_compare_prompt,
    build_diff_review_prompt,
    build_git_review_prompt,
    build_multi_file_prompt,
    get_effective_prompt_name,
    get_effective_prompt_template,
    list_prompt_files,
    load_prompt_template,
    save_custom_prompt,
)
from core.storage import init_history_db, list_history_entries, save_history_entry
from providers.factory import get_provider
from utils import (
    GitError,
    count_diff_changes,
    detect_language_from_extension,
    generate_unified_diff,
    get_git_file_pair,
    get_git_modified_files,
    is_git_repo,
    read_uploaded_file,
)

st.set_page_config(page_title="Code Compare AI", page_icon="🧠", layout="wide")

PROVIDER_OPTIONS = ["gemini", "openai", "ollama"]
LANGUAGE_OPTIONS = ["Portuguese (Brazil)", "English"]
REVIEW_MODE_OPTIONS = {
    "file_compare": "File Compare",
    "diff_review": "Diff Review",
    "multi_file_review": "Multi-File Review",
    "git_review": "Git Review",
}
SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#22c55e",
}


def inject_styles():
    st.markdown(
        """
        <style>
        .ccai-card {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 12px 14px;
            background: #ffffff;
            margin-bottom: 10px;
        }
        .ccai-card-label {
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 4px;
        }
        .ccai-card-value {
            font-size: 16px;
            font-weight: 600;
            color: #111827;
            word-break: break-word;
        }
        .ccai-issue {
            border: 1px solid #e5e7eb;
            border-left: 6px solid #d1d5db;
            border-radius: 12px;
            background: #ffffff;
            padding: 14px;
            margin-bottom: 12px;
        }
        .ccai-issue-title {
            font-size: 16px;
            font-weight: 700;
            color: #111827;
            margin-bottom: 6px;
        }
        .ccai-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            margin-right: 6px;
            color: white;
            text-transform: uppercase;
        }
        .ccai-meta {
            font-size: 12px;
            color: #6b7280;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_session():
    init_history_db()
    prompt_files = list_prompt_files()
    default_prompt_name = DEFAULT_PROMPT_FILE if DEFAULT_PROMPT_FILE in prompt_files else (prompt_files[0] if prompt_files else "")

    defaults = {
        "selected_provider": AI_PROVIDER if AI_PROVIDER in PROVIDER_OPTIONS else "gemini",
        "selected_review_mode": "file_compare",
        "response_language": DEFAULT_RESPONSE_LANGUAGE if DEFAULT_RESPONSE_LANGUAGE in LANGUAGE_OPTIONS else "Portuguese (Brazil)",
        "selected_prompt_file": default_prompt_name,
        "prompt_text": load_prompt_template(default_prompt_name) if default_prompt_name else "",
        "provider_api_key": "",
        "ollama_base_url": OLLAMA_BASE_URL,
        "compare_result": None,
        "project_result": None,
        "last_error": "",
        "save_prompt_name": "",
        "gemini_model": GEMINI_MODEL,
        "openai_model": OPENAI_MODEL,
        "ollama_model": OLLAMA_MODEL,
        "ollama_timeout_seconds": OLLAMA_TIMEOUT_SECONDS,
        "ollama_max_prompt_chars": OLLAMA_MAX_PROMPT_CHARS,
        "last_code_a": "",
        "last_code_b": "",
        "last_file_a_name": "",
        "last_file_b_name": "",
        "last_diff_text": "",
        "last_multi_missing_a": [],
        "last_multi_missing_b": [],
        "git_repo_path": "",
        "git_modified_files": [],
        "git_selected_files": [],
        "git_include_untracked": True,
        "git_file_results": [],
        "git_repo_error": "",
        "last_git_repo_path": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session()
inject_styles()


def get_current_model(provider_name):
    if provider_name == "gemini":
        return st.session_state.gemini_model.strip() or GEMINI_MODEL
    if provider_name == "openai":
        return st.session_state.openai_model.strip() or OPENAI_MODEL
    if provider_name == "ollama":
        return st.session_state.ollama_model.strip() or OLLAMA_MODEL
    raise ValueError("Unsupported provider: {0}".format(provider_name))


def get_effective_api_key(provider_name):
    entered = st.session_state.provider_api_key.strip()
    if entered:
        return entered
    if provider_name == "gemini":
        return GEMINI_API_KEY.strip()
    if provider_name == "openai":
        return OPENAI_API_KEY.strip()
    return ""


@st.dialog("Edit prompt", width="large")
def prompt_editor_dialog():
    st.caption("Load, edit and save the prompt used in the comparison.")

    prompt_files = list_prompt_files()
    current_prompt_file = st.session_state.selected_prompt_file
    current_index = prompt_files.index(current_prompt_file) if current_prompt_file in prompt_files else 0

    selected_prompt_file = st.selectbox("Prompt template", prompt_files, index=current_index)
    response_language = st.selectbox(
        "Response language",
        LANGUAGE_OPTIONS,
        index=LANGUAGE_OPTIONS.index(st.session_state.response_language),
    )

    edited_prompt = st.text_area("Prompt content", value=st.session_state.prompt_text, height=260)
    save_name = st.text_input("Save as custom prompt (.md)", value=st.session_state.save_prompt_name, placeholder="my_prompt.md")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Load template", use_container_width=True):
            st.session_state.selected_prompt_file = selected_prompt_file
            st.session_state.prompt_text = load_prompt_template(selected_prompt_file)
            st.session_state.response_language = response_language
            st.rerun()
    with col2:
        if st.button("Apply changes", use_container_width=True):
            st.session_state.prompt_text = edited_prompt
            st.session_state.response_language = response_language
            st.session_state.selected_prompt_file = selected_prompt_file
            st.rerun()
    with col3:
        if st.button("Restore template", use_container_width=True):
            st.session_state.prompt_text = load_prompt_template(selected_prompt_file)
            st.session_state.response_language = response_language
            st.session_state.selected_prompt_file = selected_prompt_file
            st.rerun()
    with col4:
        if st.button("Save custom", use_container_width=True):
            try:
                path = save_custom_prompt(save_name, edited_prompt)
                st.session_state.prompt_text = edited_prompt
                st.session_state.response_language = response_language
                st.session_state.selected_prompt_file = path.name
                st.session_state.save_prompt_name = path.name
                st.success("Prompt saved: {0}".format(path.name))
            except Exception as exc:
                st.error(str(exc))


def render_sidebar():
    st.sidebar.title("Settings")
    st.sidebar.selectbox(
        "Provider",
        PROVIDER_OPTIONS,
        index=PROVIDER_OPTIONS.index(st.session_state.selected_provider),
        key="selected_provider",
    )
    st.sidebar.selectbox(
        "Review mode",
        options=list(REVIEW_MODE_OPTIONS.keys()),
        format_func=lambda value: REVIEW_MODE_OPTIONS[value],
        index=list(REVIEW_MODE_OPTIONS.keys()).index(st.session_state.selected_review_mode),
        key="selected_review_mode",
    )

    provider = st.session_state.selected_provider

    st.sidebar.subheader("Connection")
    if provider == "gemini":
        st.sidebar.text_input("Model", key="gemini_model", help="Example: gemini-1.5-flash")
        st.sidebar.text_input("Gemini API Key", value=st.session_state.provider_api_key, key="provider_api_key", type="password", help="Leave empty to use GEMINI_API_KEY from .env")
    elif provider == "openai":
        st.sidebar.text_input("Model", key="openai_model", help="Example: gpt-4.1-mini")
        st.sidebar.text_input("OpenAI API Key", value=st.session_state.provider_api_key, key="provider_api_key", type="password", help="Leave empty to use OPENAI_API_KEY from .env")
    else:
        st.sidebar.text_input("Model", key="ollama_model", help="Example: qwen2.5-coder:7b")
        st.sidebar.text_input("Ollama Base URL", value=st.session_state.ollama_base_url, key="ollama_base_url", help="Leave as default if Ollama is running locally.")
        st.sidebar.number_input("Ollama timeout (seconds)", min_value=30, max_value=1800, step=30, key="ollama_timeout_seconds", help="Increase this if local model responses are timing out.")
        st.sidebar.number_input("Ollama max prompt chars", min_value=4000, max_value=100000, step=1000, key="ollama_max_prompt_chars", help="Long prompts are truncated for local execution.")
        if st.sidebar.button("Test Ollama connection", use_container_width=True):
            try:
                provider = get_provider(_build_provider_config())
                reply = provider.generate_text("Reply with exactly: OK")
                st.sidebar.success("Ollama OK: {0}".format((reply or "").strip()[:80]))
            except Exception as exc:
                st.sidebar.error("Ollama test failed: {0}".format(exc))

    st.sidebar.divider()
    st.sidebar.subheader("Prompt")
    st.sidebar.caption("Template: `{0}`".format(st.session_state.selected_prompt_file))
    st.sidebar.caption("Response language: `{0}`".format(st.session_state.response_language))
    st.sidebar.divider()
    with st.sidebar.expander("Advanced settings", expanded=False):
        if st.session_state.selected_provider == "ollama":
            st.caption("Ollama timeout: {0}s".format(st.session_state.ollama_timeout_seconds))
            st.caption("Ollama max prompt chars: {0}".format(st.session_state.ollama_max_prompt_chars))
        else:
            st.caption("Timeout: {0}s".format(REQUEST_TIMEOUT_SECONDS))
        st.caption("Max file size: {0} KB".format(MAX_FILE_SIZE_KB))
        st.caption("History limit: {0}".format(HISTORY_LIMIT))
        st.caption("Git max files per review: {0}".format(GIT_REVIEW_MAX_FILES))
        st.caption("Multi-file max pairs: {0}".format(MAX_MULTI_FILE_PAIRS))


def info_card(title, value):
    st.markdown(
        """
        <div class="ccai-card">
            <div class="ccai-card-label">{0}</div>
            <div class="ccai-card-value">{1}</div>
        </div>
        """.format(escape(title), escape(str(value))),
        unsafe_allow_html=True,
    )


def get_auto_prompt_label(file_name: str) -> str:
    return get_effective_prompt_name(st.session_state.selected_prompt_file, file_name)


def get_score_band(score: float) -> str:
    if score >= 9:
        return "Excellent"
    if score >= 7:
        return "Good"
    if score >= 5:
        return "Attention"
    return "Critical"


def get_score_progress(score: float) -> float:
    try:
        return max(0.0, min(float(score) / 10.0, 1.0))
    except Exception:
        return 0.0


def render_score_panel(score: float, issues_count: int, high_count: int, suggestions_count: int, label: str = "Code Quality Score"):
    st.markdown("### {0}".format(label))
    col1, col2 = st.columns([2, 3])
    with col1:
        st.metric("Score", "{0:.1f}/10".format(float(score)))
        st.caption("Band: {0}".format(get_score_band(float(score))))
    with col2:
        st.progress(get_score_progress(score))
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Issues", int(issues_count))
        with k2:
            st.metric("High/Critical", int(high_count))
        with k3:
            st.metric("Suggestions", int(suggestions_count))


def render_header():
    st.title("Code Compare AI")
    st.caption("AI-powered code review with file compare, diff review, multi-file review, Git review, language-aware prompts, and improved Ollama stability.")

    action_col1, action_col2, _ = st.columns([1, 1, 4])
    with action_col1:
        if st.button("Edit prompt", use_container_width=True):
            prompt_editor_dialog()
    with action_col2:
        if st.button("Clear result", use_container_width=True):
            st.session_state.compare_result = None
            st.session_state.project_result = None
            st.session_state.last_error = ""
            st.session_state.last_code_a = ""
            st.session_state.last_code_b = ""
            st.session_state.last_file_a_name = ""
            st.session_state.last_file_b_name = ""
            st.session_state.last_diff_text = ""
            st.session_state.git_file_results = []
            st.session_state.last_git_repo_path = ""
            st.rerun()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        info_card("Provider", "🤖 {0}".format(st.session_state.selected_provider))
    with col2:
        info_card("Model", "🧠 {0}".format(get_current_model(st.session_state.selected_provider)))
    with col3:
        info_card("Mode", "🔀 {0}".format(REVIEW_MODE_OPTIONS[st.session_state.selected_review_mode]))
    with col4:
        info_card("Prompt", "📄 {0}".format(st.session_state.selected_prompt_file))
    with col5:
        info_card("Language", "🌐 {0}".format(st.session_state.response_language))

    st.caption("When the default prompt is selected, the app automatically switches to a language-specific template based on file extension.")


def render_single_upload_area():
    col1, col2 = st.columns(2)
    with col1:
        file_a = st.file_uploader("File A", type=None, key="file_a", help="Upload the original or reference file.")
    with col2:
        file_b = st.file_uploader("File B", type=None, key="file_b", help="Upload the changed or candidate file.")
    return file_a, file_b


def render_multi_upload_area():
    col1, col2 = st.columns(2)
    with col1:
        files_a = st.file_uploader(
            "Files A",
            type=None,
            key="files_a_multi",
            help="Upload the original/reference set of files.",
            accept_multiple_files=True,
        )
    with col2:
        files_b = st.file_uploader(
            "Files B",
            type=None,
            key="files_b_multi",
            help="Upload the changed/candidate set of files.",
            accept_multiple_files=True,
        )
    return files_a or [], files_b or []


def validate_file_size(uploaded_file):
    max_size_bytes = MAX_FILE_SIZE_KB * 1024
    if uploaded_file.size > max_size_bytes:
        raise ValueError("File '{0}' exceeds the limit of {1} KB.".format(uploaded_file.name, MAX_FILE_SIZE_KB))


def _build_provider_config():
    provider_name = st.session_state.selected_provider
    timeout_seconds = REQUEST_TIMEOUT_SECONDS
    max_prompt_chars = 0
    if provider_name == "ollama":
        timeout_seconds = int(st.session_state.ollama_timeout_seconds)
        max_prompt_chars = int(st.session_state.ollama_max_prompt_chars)
    return ProviderConfig(
        provider_name=provider_name,
        model_name=get_current_model(provider_name),
        api_key=get_effective_api_key(provider_name),
        base_url=st.session_state.ollama_base_url.strip(),
        timeout_seconds=timeout_seconds,
        max_prompt_chars=max_prompt_chars,
    )


def compare_files(file_a, file_b):
    validate_file_size(file_a)
    validate_file_size(file_b)

    code_a = read_uploaded_file(file_a)
    code_b = read_uploaded_file(file_b)
    review_mode = st.session_state.selected_review_mode
    diff_text = generate_unified_diff(file_a.name, code_a, file_b.name, code_b)

    effective_template = get_effective_prompt_template(st.session_state.selected_prompt_file, file_b.name)

    if review_mode == "diff_review":
        prompt_text = build_diff_review_prompt(
            template=effective_template,
            file_a_name=file_a.name,
            file_b_name=file_b.name,
            code_a=code_a,
            code_b=code_b,
            diff_text=diff_text,
            response_language=st.session_state.response_language,
        )
    else:
        prompt_text = build_compare_prompt(
            template=effective_template,
            file_a_name=file_a.name,
            file_b_name=file_b.name,
            code_a=code_a,
            code_b=code_b,
            response_language=st.session_state.response_language,
        )

    provider_name = st.session_state.selected_provider
    model_name = get_current_model(provider_name)

    request = CompareRequest(
        file_a_name=file_a.name,
        file_b_name=file_b.name,
        code_a=code_a,
        code_b=code_b,
        prompt_text=prompt_text,
        response_language=st.session_state.response_language,
        provider_name=provider_name,
        model_name=model_name,
        review_mode=review_mode,
        diff_text=diff_text,
    )

    service = CompareService()
    result = service.compare(request, _build_provider_config())
    return result, code_a, code_b, diff_text, model_name




def _build_name_map(uploaded_files):
    mapping = {}
    duplicates = []
    for file in uploaded_files:
        if file.name in mapping:
            duplicates.append(file.name)
        else:
            mapping[file.name] = file
    if duplicates:
        raise ValueError(
            "Duplicate file names are not supported in multi-file mode: {0}".format(", ".join(sorted(set(duplicates))))
        )
    return mapping


def compare_multiple_files(files_a, files_b):
    map_a = _build_name_map(files_a)
    map_b = _build_name_map(files_b)

    names_a = set(map_a.keys())
    names_b = set(map_b.keys())
    common = sorted(names_a & names_b)
    only_a = sorted(names_a - names_b)
    only_b = sorted(names_b - names_a)

    if not common:
        raise ValueError("No matching file names were found between Files A and Files B.")
    if len(common) > MAX_MULTI_FILE_PAIRS:
        raise ValueError("Matched file pairs exceed the configured limit of {0}.".format(MAX_MULTI_FILE_PAIRS))

    st.session_state.last_multi_missing_a = only_a
    st.session_state.last_multi_missing_b = only_b

    service = CompareService()
    provider_config = _build_provider_config()

    file_results = []
    aggregated_issues = []
    aggregated_suggestions = []
    aggregated_changes = []
    parsing_notes = []

    for name in common:
        file_a = map_a[name]
        file_b = map_b[name]
        validate_file_size(file_a)
        validate_file_size(file_b)

        code_a = read_uploaded_file(file_a)
        code_b = read_uploaded_file(file_b)
        diff_text = generate_unified_diff(file_a.name, code_a, file_b.name, code_b)
        effective_template = get_effective_prompt_template(st.session_state.selected_prompt_file, file_b.name)
        prompt_text = build_multi_file_prompt(
            template=effective_template,
            file_a_name=file_a.name,
            file_b_name=file_b.name,
            code_a=code_a,
            code_b=code_b,
            diff_text=diff_text,
            response_language=st.session_state.response_language,
        )
        request = CompareRequest(
            file_a_name=file_a.name,
            file_b_name=file_b.name,
            code_a=code_a,
            code_b=code_b,
            prompt_text=prompt_text,
            response_language=st.session_state.response_language,
            provider_name=provider_config.provider_name,
            model_name=provider_config.model_name,
            review_mode="multi_file_review",
            diff_text=diff_text,
        )
        result = service.compare(request, provider_config)

        issue_dicts = []
        for issue in result.issues:
            item = issue.to_dict()
            if not item.get("file"):
                item["file"] = name
            issue_dicts.append(item)
            aggregated_issues.append(item)

        suggestion_dicts = []
        for suggestion in result.suggestions:
            item = suggestion.to_dict()
            suggestion_dicts.append(item)
            aggregated_suggestions.append({"file": name, **item})

        changes = list(result.changes_detected)
        aggregated_changes.extend(["{0}: {1}".format(name, change) for change in changes])
        parsing_notes.extend(result.parsing_notes)

        added, removed = count_diff_changes(diff_text)
        file_results.append(
            {
                "file_name": name,
                "language": detect_language_from_extension(name),
                "score": result.score,
                "summary": result.summary,
                "issues_count": len(result.issues),
                "high_count": len([issue for issue in result.issues if issue.severity in {"high", "critical"}]),
                "suggestions_count": len(result.suggestions),
                "diff_added": added,
                "diff_removed": removed,
                "diff_text": diff_text,
                "old_code": code_a,
                "new_code": code_b,
                "result": result.to_dict(),
            }
        )

    project_score = round(sum(item["score"] for item in file_results) / len(file_results), 2) if file_results else 0.0
    summary = "Reviewed {0} matched file pair(s). Average score: {1:.2f}/10.".format(len(file_results), project_score)

    return {
        "summary": summary,
        "project_score": project_score,
        "files_reviewed": len(file_results),
        "issues": aggregated_issues,
        "suggestions": aggregated_suggestions,
        "changes_detected": aggregated_changes,
        "file_results": file_results,
        "missing_in_b": only_a,
        "missing_in_a": only_b,
        "parsing_notes": parsing_notes,
    }, provider_config.model_name

def refresh_git_files(repo_path):
    repo_path = (repo_path or "").strip()
    if not repo_path:
        st.session_state.git_modified_files = []
        st.session_state.git_repo_error = ""
        return
    try:
        files = get_git_modified_files(repo_path, include_untracked=st.session_state.git_include_untracked)
        st.session_state.git_modified_files = files
        st.session_state.git_repo_error = ""
        valid_paths = [item["path"] for item in files]
        st.session_state.git_selected_files = [path for path in st.session_state.git_selected_files if path in valid_paths]
    except GitError as exc:
        st.session_state.git_modified_files = []
        st.session_state.git_repo_error = str(exc)


def render_git_area():
    st.markdown("### Local Git repository")
    st.text_input(
        "Repository path",
        key="git_repo_path",
        placeholder=r"C:\projects\my-repo or /home/user/my-repo",
        help="Path to a local Git repository available on this machine.",
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        st.checkbox("Include untracked files", key="git_include_untracked")
    with col2:
        if st.button("Load modified files", use_container_width=True):
            refresh_git_files(st.session_state.git_repo_path)

    repo_path = st.session_state.git_repo_path.strip()
    if repo_path and not st.session_state.git_modified_files and not st.session_state.git_repo_error and is_git_repo(repo_path):
        refresh_git_files(repo_path)

    if st.session_state.git_repo_error:
        st.error(st.session_state.git_repo_error)
        return []

    if repo_path and not is_git_repo(repo_path):
        st.warning("Enter a valid local Git repository path.")
        return []

    files = st.session_state.git_modified_files
    if repo_path and is_git_repo(repo_path) and not files:
        st.info("No modified supported text files found in this repository.")
        return []

    options = [item["path"] for item in files]
    status_lookup = dict((item["path"], item["status"]) for item in files)

    selected = st.multiselect(
        "Modified files",
        options=options,
        default=st.session_state.git_selected_files,
        format_func=lambda path: "{0} ({1})".format(path, status_lookup.get(path, "modified")),
        key="git_selected_files",
        help="Select one or more modified files to review.",
    )

    if len(selected) > GIT_REVIEW_MAX_FILES:
        st.warning("Select up to {0} files per Git review.".format(GIT_REVIEW_MAX_FILES))
    elif selected:
        st.caption("Selected: {0} file(s)".format(len(selected)))

    return selected


def compare_git_files(repo_path, selected_paths):
    if len(selected_paths) > GIT_REVIEW_MAX_FILES:
        raise ValueError("Select up to {0} files per Git review.".format(GIT_REVIEW_MAX_FILES))

    service = CompareService()
    provider_config = _build_provider_config()
    file_results = []
    all_issues = []
    all_suggestions = []
    all_changes = []
    score_total = 0.0
    parsing_notes = []

    for relative_path in selected_paths:
        pair = get_git_file_pair(repo_path, relative_path)
        diff_text = generate_unified_diff(pair["old_label"], pair["old_code"], pair["new_label"], pair["new_code"])
        prompt_text = build_git_review_prompt(
            template=st.session_state.prompt_text,
            file_a_name=pair["old_label"],
            file_b_name=pair["new_label"],
            code_a=pair["old_code"],
            code_b=pair["new_code"],
            diff_text=diff_text,
            response_language=st.session_state.response_language,
            repo_path=repo_path,
        )
        request = CompareRequest(
            file_a_name=pair["old_label"],
            file_b_name=pair["new_label"],
            code_a=pair["old_code"],
            code_b=pair["new_code"],
            prompt_text=prompt_text,
            response_language=st.session_state.response_language,
            provider_name=provider_config.provider_name,
            model_name=provider_config.model_name,
            review_mode="git_review",
            diff_text=diff_text,
        )
        result = service.compare(request, provider_config)
        for issue in result.issues:
            if not issue.file:
                issue.file = relative_path
        score_total += result.score
        all_issues.extend(result.issues)
        all_suggestions.extend(result.suggestions)
        all_changes.extend(result.changes_detected)
        parsing_notes.extend(result.parsing_notes)
        file_results.append(
            {
                "file_path": relative_path,
                "status": pair["status"],
                "diff_text": diff_text,
                "old_file_name": pair["old_label"],
                "new_file_name": pair["new_label"],
                "old_code": pair["old_code"],
                "new_code": pair["new_code"],
                "result": result.to_dict(),
            }
        )

    files_reviewed = len(file_results)
    project_score = score_total / files_reviewed if files_reviewed else 0.0
    summary = "Git review analyzed {0} file(s) from repository: {1}".format(files_reviewed, repo_path)
    aggregate_result = StructuredCompareResult(
        summary=summary,
        score=project_score,
        issues=all_issues,
        suggestions=all_suggestions,
        changes_detected=all_changes,
        raw_response="",
        parsing_notes=parsing_notes,
    )
    return aggregate_result, file_results, provider_config.model_name


def add_history_entry(file_a_name, file_b_name, provider_name, model_name, result, extra_payload=None):
    if hasattr(result, "to_dict"):
        score_value = result.score
        result_payload = result.to_dict()
    else:
        score_value = float(result.get("project_score", result.get("score", 0)) or 0)
        result_payload = result

    entry = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_a_name": file_a_name,
        "file_b_name": file_b_name,
        "provider_name": provider_name,
        "model_name": model_name,
        "review_mode": st.session_state.selected_review_mode,
        "score": score_value,
        "result": result_payload,
    }
    if extra_payload:
        entry.update(extra_payload)
    save_history_entry(entry)


def render_previews():
    if st.session_state.selected_review_mode in {"git_review", "multi_file_review"}:
        return
    if not st.session_state.last_code_a or not st.session_state.last_code_b:
        return
    with st.expander("Preview files", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**File A: {0}**".format(st.session_state.last_file_a_name))
            st.code(st.session_state.last_code_a, language=detect_language_from_extension(st.session_state.last_file_a_name))
        with col2:
            st.markdown("**File B: {0}**".format(st.session_state.last_file_b_name))
            st.code(st.session_state.last_code_b, language=detect_language_from_extension(st.session_state.last_file_b_name))

    if st.session_state.last_diff_text:
        with st.expander("Unified diff", expanded=(st.session_state.selected_review_mode == "diff_review")):
            added, removed = count_diff_changes(st.session_state.last_diff_text)
            st.caption("Added lines: {0} · Removed lines: {1}".format(added, removed))
            st.code(st.session_state.last_diff_text, language="diff")



def render_result_summary(result):
    st.subheader("Overview")
    high_count = len([item for item in result.issues if item.severity in {"high", "critical"}])
    render_score_panel(result.score, len(result.issues), high_count, len(result.suggestions))

    meta1, meta2, meta3 = st.columns(3)
    with meta1:
        st.info("Detected file A language: **{0}**".format(detect_language_from_extension(st.session_state.last_file_a_name or "")))
    with meta2:
        st.info("Detected file B language: **{0}**".format(detect_language_from_extension(st.session_state.last_file_b_name or "")))
    with meta3:
        auto_prompt = get_effective_prompt_name(st.session_state.selected_prompt_file, st.session_state.last_file_b_name or st.session_state.last_file_a_name or "")
        st.info("Effective prompt: **{0}**".format(auto_prompt))

    st.markdown("### Summary")
    st.write(result.summary)

    if result.parsing_notes:
        with st.expander("Parsing notes", expanded=False):
            for note in result.parsing_notes:
                st.warning(note)


def render_changes_tab(result):
    if not result.changes_detected:
        st.info("No structured list of changes was returned.")
        return
    for item in result.changes_detected:
        st.markdown("- {0}".format(item))



def render_issues_tab(result, key_prefix="issues_tab"):
    if not result.issues:
        st.success("No structured issues were found.")
        return

    severity_filter = st.multiselect(
        "Filter by severity",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
        key="{0}_severity".format(key_prefix),
    )
    category_options = sorted({issue.category for issue in result.issues})
    category_filter = st.multiselect(
        "Filter by category",
        options=category_options,
        default=category_options,
        key="{0}_category".format(key_prefix),
    )

    filtered = [
        issue for issue in result.issues
        if issue.severity in severity_filter and issue.category in category_filter
    ]

    if not filtered:
        st.info("No issues match the selected filters.")
        return

    for issue in filtered:
        color = SEVERITY_COLORS.get(issue.severity, "#9ca3af")
        meta = []
        if issue.file:
            meta.append(issue.file)
        if issue.line is not None:
            meta.append("line {0}".format(issue.line))
        st.markdown(
            """
            <div class="ccai-issue" style="border-left-color:{0};">
                <div>
                    <span class="ccai-badge" style="background:{0};">{1}</span>
                    <span class="ccai-badge" style="background:#6b7280;">{2}</span>
                </div>
                <div class="ccai-issue-title">{3}</div>
                <div>{4}</div>
                <div class="ccai-meta">{5}</div>
            </div>
            """.format(
                color,
                escape(issue.severity),
                escape(issue.category),
                escape(issue.title),
                escape(issue.description),
                escape(" · ".join(meta)) if meta else "No file/line context provided.",
            ),
            unsafe_allow_html=True,
        )


def render_suggestions_tab(result):
    if not result.suggestions:
        st.info("No suggestions were returned.")
        return
    for item in result.suggestions:
        with st.container(border=True):
            st.markdown("**{0}**".format(item.title))
            st.write(item.description)


def render_raw_tab(result):
    payload = result.to_dict()
    if st.session_state.selected_review_mode == "git_review" and st.session_state.git_file_results:
        payload = {
            "aggregate_result": payload,
            "git_repo_path": st.session_state.last_git_repo_path,
            "file_results": st.session_state.git_file_results,
        }
    st.download_button(
        label="Download JSON",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name="code_review_result.json",
        mime="application/json",
        use_container_width=True,
    )
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


def render_git_files_tab():
    file_results = st.session_state.git_file_results
    if not file_results:
        st.info("No Git file results available.")
        return

    labels = ["{0} · {1} · score {2:.1f} · {3}".format(item["file_path"], detect_language_from_extension(item["file_path"]), float(item["result"].get("score", 0)), item.get("status", "modified")) for item in file_results]
    selected_label = st.selectbox("Reviewed files", labels)
    selected_index = labels.index(selected_label)
    item = file_results[selected_index]
    result_dict = item["result"]

    st.markdown("### {0}".format(item["file_path"]))
    st.caption("Status: {0}".format(item.get("status", "modified")))
    st.write(result_dict.get("summary", "No summary."))

    with st.expander("Unified diff", expanded=True):
        added, removed = count_diff_changes(item.get("diff_text", ""))
        st.caption("Added lines: {0} · Removed lines: {1}".format(added, removed))
        st.code(item.get("diff_text", ""), language="diff")

    with st.expander("Preview files", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**{0}**".format(item.get("old_file_name", "File A")))
            st.code(item.get("old_code", ""), language=detect_language_from_extension(item.get("file_path", "")))
        with col2:
            st.markdown("**{0}**".format(item.get("new_file_name", "File B")))
            st.code(item.get("new_code", ""), language=detect_language_from_extension(item.get("file_path", "")))

    file_result = StructuredCompareResult(
        summary=result_dict.get("summary", ""),
        score=float(result_dict.get("score", 0)),
        issues=[],
        suggestions=[],
        changes_detected=result_dict.get("changes_detected", []),
        raw_response=result_dict.get("raw_response", ""),
        parsing_notes=result_dict.get("parsing_notes", []),
    )

    from core.result_parser import _build_issue, _build_suggestion  # local reuse

    for raw_issue in result_dict.get("issues", []):
        if isinstance(raw_issue, dict):
            file_result.issues.append(_build_issue(raw_issue))
    for raw_suggestion in result_dict.get("suggestions", []):
        if isinstance(raw_suggestion, dict):
            file_result.suggestions.append(_build_suggestion(raw_suggestion))

    sub1, sub2, sub3 = st.tabs(["Issues", "Suggestions", "Raw JSON"])
    with sub1:
        render_issues_tab(file_result, key_prefix="file_issues_tab")
    with sub2:
        render_suggestions_tab(file_result)
    with sub3:
        st.code(json.dumps(result_dict, ensure_ascii=False, indent=2), language="json")





def render_project_summary(project_result):
    st.subheader("Project Overview")
    issues = project_result.get("issues", [])
    high_count = len([item for item in issues if item.get("severity") in {"high", "critical"}])
    render_score_panel(
        float(project_result.get("project_score", 0) or 0),
        len(issues),
        high_count,
        len(project_result.get("suggestions", [])),
        label="Project Quality Score",
    )

    st.markdown("### Summary")
    st.write(project_result.get("summary", "No summary available."))

    parsing_notes = project_result.get("parsing_notes", [])
    if parsing_notes:
        with st.expander("Parsing notes", expanded=False):
            for note in parsing_notes:
                st.warning(note)

    missing_a = project_result.get("missing_in_a", [])
    missing_b = project_result.get("missing_in_b", [])
    if missing_a or missing_b:
        with st.expander("Unmatched files", expanded=False):
            if missing_b:
                st.write("Present only in Files A:")
                for item in missing_b:
                    st.markdown("- {0}".format(item))
            if missing_a:
                st.write("Present only in Files B:")
                for item in missing_a:
                    st.markdown("- {0}".format(item))


def render_issues_from_list(issue_items, key_prefix="issues"):
    if not issue_items:
        st.success("No structured issues were found.")
        return

    severity_filter = st.multiselect(
        "Filter by severity",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
        key="{0}_severity".format(key_prefix),
    )
    category_options = sorted({str(issue.get("category")) for issue in issue_items if str(issue.get("category"))})
    category_filter = st.multiselect(
        "Filter by category",
        options=category_options,
        default=category_options,
        key="{0}_category".format(key_prefix),
    )

    filtered = [
        issue for issue in issue_items
        if issue.get("severity") in severity_filter and issue.get("category") in category_filter
    ]

    if not filtered:
        st.info("No issues match the selected filters.")
        return

    for issue in filtered:
        color = SEVERITY_COLORS.get(issue.get("severity"), "#9ca3af")
        meta = []
        if issue.get("file"):
            meta.append(issue.get("file"))
        if issue.get("line") not in (None, ""):
            meta.append("line {0}".format(issue.get("line")))
        st.markdown(
            """
            <div class="ccai-issue" style="border-left-color:{0};">
                <div>
                    <span class="ccai-badge" style="background:{0};">{1}</span>
                    <span class="ccai-badge" style="background:#6b7280;">{2}</span>
                </div>
                <div class="ccai-issue-title">{3}</div>
                <div>{4}</div>
                <div class="ccai-meta">{5}</div>
            </div>
            """.format(
                color,
                escape(str(issue.get("severity"))),
                escape(str(issue.get("category"))),
                escape(str(issue.get("title"))),
                escape(str(issue.get("description"))),
                escape(" · ".join(meta)) if meta else "No file/line context provided.",
            ),
            unsafe_allow_html=True,
        )


def render_project_changes_tab(project_result):
    changes = project_result.get("changes_detected", [])
    if not changes:
        st.info("No structured list of changes was returned.")
        return
    for item in changes:
        st.markdown("- {0}".format(item))


def render_project_issues_tab(project_result):
    render_issues_from_list(project_result.get("issues", []), key_prefix="project_issues")


def render_project_suggestions_tab(project_result):
    suggestions = project_result.get("suggestions", [])
    if not suggestions:
        st.info("No suggestions were returned.")
        return
    for item in suggestions:
        with st.container(border=True):
            title = item.get("title", "Untitled suggestion")
            file_name = item.get("file")
            if file_name:
                st.markdown("**{0}** · `{1}`".format(title, file_name))
            else:
                st.markdown("**{0}**".format(title))
            st.write(item.get("description", "No description provided."))


def render_project_raw_tab(project_result):
    st.download_button(
        label="Download JSON",
        data=json.dumps(project_result, ensure_ascii=False, indent=2),
        file_name="project_code_review_result.json",
        mime="application/json",
        use_container_width=True,
    )
    st.code(json.dumps(project_result, ensure_ascii=False, indent=2), language="json")


def render_project_files_tab(project_result):
    file_results = project_result.get("file_results", [])
    if not file_results:
        st.info("No file results available.")
        return

    for index, item in enumerate(file_results):
        title = "{0} · score {1:.2f} · issues {2}".format(
            item.get("file_name", ""),
            float(item.get("score", 0) or 0),
            int(item.get("issues_count", 0)),
        )
        with st.expander(title, expanded=(index == 0)):
            meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
            with meta_col1:
                st.metric("Score", "{0:.2f}/10".format(float(item.get("score", 0) or 0)))
            with meta_col2:
                st.metric("Issues", int(item.get("issues_count", 0) or 0))
            with meta_col3:
                st.metric("High/Critical", int(item.get("high_count", 0) or 0))
            with meta_col4:
                st.metric("Suggestions", int(item.get("suggestions_count", 0) or 0))

            st.caption(
                "Language: {0} · Added lines: {1} · Removed lines: {2}".format(
                    item.get("language", "text"),
                    int(item.get("diff_added", 0) or 0),
                    int(item.get("diff_removed", 0) or 0),
                )
            )
            st.write(item.get("summary", "No summary available."))

            subtab1, subtab2, subtab3 = st.tabs(["Diff", "Code", "Raw"])
            with subtab1:
                st.code(item.get("diff_text", ""), language="diff")
            with subtab2:
                code_col1, code_col2 = st.columns(2)
                with code_col1:
                    st.markdown("**Old / A**")
                    st.code(item.get("old_code", ""), language=item.get("language", "text"))
                with code_col2:
                    st.markdown("**New / B**")
                    st.code(item.get("new_code", ""), language=item.get("language", "text"))
            with subtab3:
                st.code(json.dumps(item.get("result", {}), ensure_ascii=False, indent=2), language="json")

def render_history_tab():
    st.subheader("History")
    items = list_history_entries(HISTORY_LIMIT)
    if not items:
        st.info("No comparisons saved yet.")
        return

    for index, item in enumerate(items):
        result = item.get("result", {})
        extra = ""
        if item.get("review_mode") == "git_review":
            extra = " · files {0}".format(len(item.get("file_results", [])))
        elif item.get("review_mode") == "multi_file_review":
            extra = " · files {0}".format(int(item.get("result", {}).get("files_reviewed", 0) or 0))
        title = "{0} · {1} · {2} → {3} · {4}/{5} · score {6:.1f}{7}".format(
            item.get("created_at", ""),
            item.get("review_mode", "file_compare"),
            item.get("file_a_name", ""),
            item.get("file_b_name", ""),
            item.get("provider_name", ""),
            item.get("model_name", ""),
            float(item.get("score", 0) or 0),
            extra,
        )
        with st.expander(title, expanded=(index == 0)):
            st.write(result.get("summary", "No summary."))
            st.caption(
                "Issues: {0} · Suggestions: {1}".format(
                    len(result.get("issues", [])),
                    len(result.get("suggestions", [])),
                )
            )
            if item.get("review_mode") == "git_review":
                st.caption("Repository: {0}".format(item.get("git_repo_path", "")))
            elif item.get("review_mode") == "multi_file_review":
                st.caption("Files reviewed: {0}".format(int(item.get("result", {}).get("files_reviewed", 0) or 0)))
            st.code(json.dumps(item, ensure_ascii=False, indent=2), language="json")


def main():
    render_sidebar()
    render_header()

    compare_tab, history_tab = st.tabs(["Compare", "History"])

    with compare_tab:
        mode = st.session_state.selected_review_mode
        if mode == "diff_review":
            st.info("Diff Review focuses the AI analysis on the changed lines while still using the full files as context.")
        elif mode == "multi_file_review":
            st.info("Manual Multi-File Review compares multiple matched file names without ZIP uploads.")
        elif mode == "git_review":
            st.info("Git Review analyzes modified files from a local repository using HEAD versus current working tree content.")

        if mode == "multi_file_review":
            files_a, files_b = render_multi_upload_area()

            if files_a or files_b:
                names_a = {f.name for f in files_a}
                names_b = {f.name for f in files_b}
                matched = sorted(names_a & names_b)
                only_a = sorted(names_a - names_b)
                only_b = sorted(names_b - names_a)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Files A", len(files_a))
                with col2:
                    st.metric("Files B", len(files_b))
                with col3:
                    st.metric("Matched pairs", len(matched))

                with st.expander("Pairing preview", expanded=False):
                    if matched:
                        st.write("Matched by file name:")
                        for item in matched:
                            st.markdown("- {0}".format(item))
                    if only_a:
                        st.write("Only in Files A:")
                        for item in only_a:
                            st.markdown("- {0}".format(item))
                    if only_b:
                        st.write("Only in Files B:")
                        for item in only_b:
                            st.markdown("- {0}".format(item))

            col1, col2 = st.columns([1, 4])
            with col1:
                compare_clicked = st.button("Compare project", type="primary", use_container_width=True)
            with col2:
                if not files_a or not files_b:
                    st.info("Upload files on both sides to start the multi-file review.")

            if compare_clicked:
                if not files_a or not files_b:
                    st.warning("Please upload both file sets before comparing.")
                else:
                    with st.spinner("Reviewing matched file pairs..."):
                        try:
                            project_result, model_name = compare_multiple_files(files_a, files_b)
                            st.session_state.project_result = project_result
                            st.session_state.compare_result = None
                            st.session_state.last_error = ""
                            st.session_state.last_code_a = ""
                            st.session_state.last_code_b = ""
                            st.session_state.last_file_a_name = ""
                            st.session_state.last_file_b_name = ""
                            st.session_state.last_diff_text = ""
                            st.session_state.git_file_results = []
                            st.session_state.last_git_repo_path = ""
                            add_history_entry(
                                file_a_name="{0} files".format(len(files_a)),
                                file_b_name="{0} files".format(len(files_b)),
                                provider_name=st.session_state.selected_provider,
                                model_name=model_name,
                                result=project_result,
                            )
                        except Exception as exc:
                            st.session_state.project_result = None
                            st.session_state.compare_result = None
                            st.session_state.last_error = "Unexpected error: {0}".format(exc)

            if st.session_state.last_error:
                st.error(st.session_state.last_error)

            project_result = st.session_state.project_result
            if project_result:
                render_project_summary(project_result)
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["Files", "Changes", "Issues", "Suggestions", "Raw JSON"])
                with tab1:
                    render_project_files_tab(project_result)
                with tab2:
                    render_project_changes_tab(project_result)
                with tab3:
                    render_project_issues_tab(project_result)
                with tab4:
                    render_project_suggestions_tab(project_result)
                with tab5:
                    render_project_raw_tab(project_result)

        elif mode == "git_review":
            selected_files = render_git_area()
            col1, col2 = st.columns([1, 4])
            with col1:
                compare_clicked = st.button("Review selected files", type="primary", use_container_width=True)
            with col2:
                if not selected_files:
                    st.info("Load a repository and select one or more modified files.")

            if compare_clicked:
                repo_path = st.session_state.git_repo_path.strip()
                if not repo_path or not is_git_repo(repo_path):
                    st.warning("Please enter a valid local Git repository path.")
                elif not selected_files:
                    st.warning("Select one or more modified files before reviewing.")
                else:
                    with st.spinner("Reviewing Git changes..."):
                        try:
                            result, file_results, model_name = compare_git_files(repo_path, selected_files)
                            st.session_state.compare_result = result
                            st.session_state.project_result = None
                            st.session_state.last_error = ""
                            st.session_state.last_code_a = ""
                            st.session_state.last_code_b = ""
                            st.session_state.last_file_a_name = ""
                            st.session_state.last_file_b_name = ""
                            st.session_state.last_diff_text = ""
                            st.session_state.git_file_results = file_results
                            st.session_state.last_git_repo_path = repo_path
                            add_history_entry(
                                file_a_name=repo_path,
                                file_b_name="{0} file(s)".format(len(selected_files)),
                                provider_name=st.session_state.selected_provider,
                                model_name=model_name,
                                result=result,
                                extra_payload={
                                    "git_repo_path": repo_path,
                                    "git_files": list(selected_files),
                                    "file_results": file_results,
                                },
                            )
                        except Exception as exc:
                            st.session_state.compare_result = None
                            st.session_state.project_result = None
                            st.session_state.last_error = "Unexpected error: {0}".format(exc)
        else:
            file_a, file_b = render_single_upload_area()
            col1, col2 = st.columns([1, 4])
            with col1:
                compare_clicked = st.button("Compare", type="primary", use_container_width=True)
            with col2:
                if not file_a or not file_b:
                    st.info("Upload 2 files to start the comparison.")

            if compare_clicked:
                if not file_a or not file_b:
                    st.warning("Please upload both files before comparing.")
                else:
                    with st.spinner("Comparing files..."):
                        try:
                            result, code_a, code_b, diff_text, model_name = compare_files(file_a, file_b)
                            st.session_state.compare_result = result
                            st.session_state.project_result = None
                            st.session_state.last_error = ""
                            st.session_state.last_code_a = code_a
                            st.session_state.last_code_b = code_b
                            st.session_state.last_file_a_name = file_a.name
                            st.session_state.last_file_b_name = file_b.name
                            st.session_state.last_diff_text = diff_text
                            st.session_state.git_file_results = []
                            st.session_state.last_git_repo_path = ""
                            add_history_entry(file_a.name, file_b.name, st.session_state.selected_provider, model_name, result)
                        except Exception as exc:
                            st.session_state.compare_result = None
                            st.session_state.project_result = None
                            st.session_state.last_error = "Unexpected error: {0}".format(exc)

        if st.session_state.last_error:
            st.error(st.session_state.last_error)

        render_previews()

        result = st.session_state.compare_result
        if result:
            render_result_summary(result)
            if mode == "git_review":
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["Files", "Changes", "Issues", "Suggestions", "Raw JSON"])
                with tab1:
                    render_git_files_tab()
                with tab2:
                    render_changes_tab(result)
                with tab3:
                    render_issues_tab(result, key_prefix="main_issues_tab")
                with tab4:
                    render_suggestions_tab(result)
                with tab5:
                    render_raw_tab(result)
            else:
                tab1, tab2, tab3, tab4 = st.tabs(["Changes", "Issues", "Suggestions", "Raw JSON"])
                with tab1:
                    render_changes_tab(result)
                with tab2:
                    render_issues_tab(result, key_prefix="main_issues_tab")
                with tab3:
                    render_suggestions_tab(result)
                with tab4:
                    render_raw_tab(result)

    with history_tab:
        render_history_tab()


if __name__ == "__main__":
    main()
