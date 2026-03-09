
import json
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

from config import (
    AI_PROVIDER,
    DEFAULT_PROMPT_FILE,
    DEFAULT_RESPONSE_LANGUAGE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    HISTORY_LIMIT,
    MAX_FILE_SIZE_KB,
    MAX_MULTI_FILE_PAIRS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from core.compare_service import CompareService
from core.models import CompareRequest, ProviderConfig, StructuredCompareResult, Issue, Suggestion
from core.prompts import (
    build_compare_prompt,
    build_diff_review_prompt,
    build_multi_file_prompt,
    list_prompt_files,
    load_prompt_template,
    save_custom_prompt,
)
from core.storage import init_history_db, list_history_entries, save_history_entry
from utils import count_diff_changes, detect_language_from_extension, generate_unified_diff, read_uploaded_file

st.set_page_config(page_title="Code Compare AI", page_icon="🧠", layout="wide")

PROVIDER_OPTIONS = ["gemini", "openai", "ollama"]
LANGUAGE_OPTIONS = ["Portuguese (Brazil)", "English"]
REVIEW_MODE_OPTIONS = {
    "file_compare": "File Compare",
    "diff_review": "Diff Review",
    "multi_file_review": "Multi-File Review",
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
        "last_code_a": "",
        "last_code_b": "",
        "last_file_a_name": "",
        "last_file_b_name": "",
        "last_diff_text": "",
        "last_multi_missing_a": [],
        "last_multi_missing_b": [],
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session()
inject_styles()


def get_current_model(provider_name: str) -> str:
    if provider_name == "gemini":
        return st.session_state.gemini_model.strip() or GEMINI_MODEL
    if provider_name == "openai":
        return st.session_state.openai_model.strip() or OPENAI_MODEL
    if provider_name == "ollama":
        return st.session_state.ollama_model.strip() or OLLAMA_MODEL
    raise ValueError("Unsupported provider: {0}".format(provider_name))


def get_effective_api_key(provider_name: str) -> str:
    entered = st.session_state.provider_api_key.strip()
    if entered:
        return entered
    if provider_name == "gemini":
        return GEMINI_API_KEY.strip()
    if provider_name == "openai":
        return OPENAI_API_KEY.strip()
    return ""


def get_effective_prompt_template(file_name: str) -> str:
    selected_prompt = st.session_state.selected_prompt_file
    suffix = Path(file_name).suffix.lower()
    if selected_prompt == DEFAULT_PROMPT_FILE and suffix in {".pas", ".dpr"}:
        prompt_files = list_prompt_files()
        if "delphi_compare_prompt.md" in prompt_files:
            return load_prompt_template("delphi_compare_prompt.md")
    return st.session_state.prompt_text


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

    st.sidebar.divider()
    st.sidebar.subheader("Prompt")
    st.sidebar.caption("Template: `{0}`".format(st.session_state.selected_prompt_file))
    st.sidebar.caption("Response language: `{0}`".format(st.session_state.response_language))
    st.sidebar.divider()
    with st.sidebar.expander("Advanced settings", expanded=False):
        st.caption("Timeout: {0}s".format(REQUEST_TIMEOUT_SECONDS))
        st.caption("Max file size: {0} KB".format(MAX_FILE_SIZE_KB))
        st.caption("History limit: {0}".format(HISTORY_LIMIT))
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


def render_header():
    st.title("Code Compare AI v8")
    st.caption("Now with manual Multi-File Review based on v7, without ZIP uploads.")

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
            st.session_state.last_multi_missing_a = []
            st.session_state.last_multi_missing_b = []
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
            key="files_a",
            accept_multiple_files=True,
            help="Upload the original/reference set of files. Pairing is done by file name.",
        )
    with col2:
        files_b = st.file_uploader(
            "Files B",
            type=None,
            key="files_b",
            accept_multiple_files=True,
            help="Upload the changed/candidate set of files. Pairing is done by file name.",
        )
    return files_a or [], files_b or []


def validate_file_size(uploaded_file):
    max_size_bytes = MAX_FILE_SIZE_KB * 1024
    if uploaded_file.size > max_size_bytes:
        raise ValueError("File '{0}' exceeds the limit of {1} KB.".format(uploaded_file.name, MAX_FILE_SIZE_KB))


def create_provider_config():
    provider_name = st.session_state.selected_provider
    return ProviderConfig(
        provider_name=provider_name,
        model_name=get_current_model(provider_name),
        api_key=get_effective_api_key(provider_name),
        base_url=st.session_state.ollama_base_url.strip(),
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
    )


def create_request(file_a_name: str, file_b_name: str, code_a: str, code_b: str, review_mode: str) -> CompareRequest:
    diff_text = generate_unified_diff(file_a_name, code_a, file_b_name, code_b)
    template = get_effective_prompt_template(file_b_name or file_a_name)

    if review_mode == "diff_review":
        prompt_text = build_diff_review_prompt(
            template=template,
            file_a_name=file_a_name,
            file_b_name=file_b_name,
            code_a=code_a,
            code_b=code_b,
            diff_text=diff_text,
            response_language=st.session_state.response_language,
        )
    elif review_mode == "multi_file_review":
        prompt_text = build_multi_file_prompt(
            template=template,
            file_a_name=file_a_name,
            file_b_name=file_b_name,
            code_a=code_a,
            code_b=code_b,
            diff_text=diff_text,
            response_language=st.session_state.response_language,
        )
    else:
        prompt_text = build_compare_prompt(
            template=template,
            file_a_name=file_a_name,
            file_b_name=file_b_name,
            code_a=code_a,
            code_b=code_b,
            response_language=st.session_state.response_language,
        )

    provider_name = st.session_state.selected_provider
    model_name = get_current_model(provider_name)

    return CompareRequest(
        file_a_name=file_a_name,
        file_b_name=file_b_name,
        code_a=code_a,
        code_b=code_b,
        prompt_text=prompt_text,
        response_language=st.session_state.response_language,
        provider_name=provider_name,
        model_name=model_name,
        review_mode=review_mode,
        diff_text=diff_text,
    )


def compare_files(file_a, file_b):
    validate_file_size(file_a)
    validate_file_size(file_b)

    code_a = read_uploaded_file(file_a)
    code_b = read_uploaded_file(file_b)
    review_mode = st.session_state.selected_review_mode
    request = create_request(file_a.name, file_b.name, code_a, code_b, review_mode)

    service = CompareService()
    result = service.compare(request, create_provider_config())
    return result, code_a, code_b, request.diff_text, get_current_model(st.session_state.selected_provider)


def _build_name_map(uploaded_files):
    mapping = {}
    duplicates = []
    for file in uploaded_files:
        if file.name in mapping:
            duplicates.append(file.name)
        else:
            mapping[file.name] = file
    if duplicates:
        raise ValueError("Duplicate file names are not supported in multi-file mode: {0}".format(", ".join(sorted(set(duplicates)))))
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
    provider_config = create_provider_config()

    file_results = []
    aggregated_issues = []
    aggregated_suggestions = []
    aggregated_changes = []

    for name in common:
        file_a = map_a[name]
        file_b = map_b[name]
        validate_file_size(file_a)
        validate_file_size(file_b)

        code_a = read_uploaded_file(file_a)
        code_b = read_uploaded_file(file_b)
        request = create_request(file_a.name, file_b.name, code_a, code_b, "multi_file_review")
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

        file_results.append(
            {
                "file_name": name,
                "language": detect_language_from_extension(name),
                "score": result.score,
                "summary": result.summary,
                "issues_count": len(result.issues),
                "high_count": len([issue for issue in result.issues if issue.severity in {"high", "critical"}]),
                "suggestions_count": len(result.suggestions),
                "diff_added": count_diff_changes(request.diff_text)[0],
                "diff_removed": count_diff_changes(request.diff_text)[1],
                "result": result.to_dict(),
            }
        )

    project_score = round(sum(item["score"] for item in file_results) / len(file_results), 2) if file_results else 0.0
    summary = "Reviewed {0} matched file pairs. Average score: {1:.2f}/10.".format(len(file_results), project_score)

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
    }, get_current_model(st.session_state.selected_provider)


def add_history_entry(file_a_name, file_b_name, provider_name, model_name, result_payload, review_mode, score):
    entry = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_a_name": file_a_name,
        "file_b_name": file_b_name,
        "provider_name": provider_name,
        "model_name": model_name,
        "review_mode": review_mode,
        "score": score,
        "result": result_payload,
    }
    save_history_entry(entry)


def render_previews():
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


def render_result_summary(result: StructuredCompareResult):
    st.subheader("Overview")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Score", "{0:.1f}/10".format(result.score))
    with col2:
        st.metric("Issues", len(result.issues))
    with col3:
        high_count = len([item for item in result.issues if item.severity in {"high", "critical"}])
        st.metric("High/Critical", high_count)
    with col4:
        st.metric("Suggestions", len(result.suggestions))

    st.markdown("### Summary")
    st.write(result.summary)

    if result.parsing_notes:
        with st.expander("Parsing notes", expanded=False):
            for note in result.parsing_notes:
                st.warning(note)


def render_project_summary(project_result):
    st.subheader("Project Overview")
    col1, col2, col3, col4 = st.columns(4)
    issues = project_result.get("issues", [])
    suggestions = project_result.get("suggestions", [])
    high_count = len([item for item in issues if item.get("severity") in {"high", "critical"}])
    with col1:
        st.metric("Project score", "{0:.2f}/10".format(float(project_result.get("project_score", 0))))
    with col2:
        st.metric("Files reviewed", int(project_result.get("files_reviewed", 0)))
    with col3:
        st.metric("Issues", len(issues))
    with col4:
        st.metric("High/Critical", high_count)

    st.markdown("### Summary")
    st.write(project_result.get("summary", "No summary available."))

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


def render_changes_tab(result: StructuredCompareResult):
    if not result.changes_detected:
        st.info("No structured list of changes was returned.")
        return
    for item in result.changes_detected:
        st.markdown("- {0}".format(item))


def render_project_changes_tab(project_result):
    changes = project_result.get("changes_detected", [])
    if not changes:
        st.info("No structured list of changes was returned.")
        return
    for item in changes:
        st.markdown("- {0}".format(item))


def render_issues_from_list(issue_items):
    if not issue_items:
        st.success("No structured issues were found.")
        return

    severity_filter = st.multiselect(
        "Filter by severity",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
        key="severity_filter_{0}".format(len(issue_items)),
    )
    category_options = sorted({str(issue.get("category")) for issue in issue_items if str(issue.get("category"))})
    category_filter = st.multiselect(
        "Filter by category",
        options=category_options,
        default=category_options,
        key="category_filter_{0}".format(len(issue_items)),
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


def render_issues_tab(result: StructuredCompareResult):
    render_issues_from_list([issue.to_dict() for issue in result.issues])


def render_project_issues_tab(project_result):
    render_issues_from_list(project_result.get("issues", []))


def render_suggestions_tab(result: StructuredCompareResult):
    if not result.suggestions:
        st.info("No suggestions were returned.")
        return
    for item in result.suggestions:
        with st.container(border=True):
            st.markdown("**{0}**".format(item.title))
            st.write(item.description)


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


def render_raw_tab(result: StructuredCompareResult):
    payload = result.to_dict()
    st.download_button(
        label="Download JSON",
        data=json.dumps(payload, ensure_ascii=False, indent=2),
        file_name="code_review_result.json",
        mime="application/json",
        use_container_width=True,
    )
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


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
                st.metric("Issues", int(item.get("issues_count", 0)))
            with meta_col3:
                st.metric("High/Critical", int(item.get("high_count", 0)))
            with meta_col4:
                st.metric("Suggestions", int(item.get("suggestions_count", 0)))
            st.caption(
                "Language: {0} · Added lines: {1} · Removed lines: {2}".format(
                    item.get("language", "text"),
                    int(item.get("diff_added", 0)),
                    int(item.get("diff_removed", 0)),
                )
            )
            st.write(item.get("summary", "No summary available."))
            st.code(json.dumps(item.get("result", {}), ensure_ascii=False, indent=2), language="json")


def render_history_tab():
    st.subheader("History")
    items = list_history_entries(HISTORY_LIMIT)
    if not items:
        st.info("No comparisons saved yet.")
        return

    for index, item in enumerate(items):
        result = item.get("result", {})
        review_mode = item.get("review_mode", "file_compare")
        score_value = float(item.get("score", 0) or 0)
        title = "{0} · {1} · {2} → {3} · {4}/{5} · score {6:.1f}".format(
            item.get("created_at", ""),
            review_mode,
            item.get("file_a_name", ""),
            item.get("file_b_name", ""),
            item.get("provider_name", ""),
            item.get("model_name", ""),
            score_value,
        )
        with st.expander(title, expanded=(index == 0)):
            if review_mode == "multi_file_review":
                st.write(result.get("summary", "No summary."))
                st.caption(
                    "Files reviewed: {0} · Issues: {1} · Suggestions: {2}".format(
                        int(result.get("files_reviewed", 0)),
                        len(result.get("issues", [])),
                        len(result.get("suggestions", [])),
                    )
                )
            else:
                st.write(result.get("summary", "No summary."))
                st.caption(
                    "Issues: {0} · Suggestions: {1}".format(
                        len(result.get("issues", [])),
                        len(result.get("suggestions", [])),
                    )
                )
            st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")


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
                            add_history_entry(
                                file_a_name="{0} files".format(len(files_a)),
                                file_b_name="{0} files".format(len(files_b)),
                                provider_name=st.session_state.selected_provider,
                                model_name=model_name,
                                result_payload=project_result,
                                review_mode="multi_file_review",
                                score=float(project_result.get("project_score", 0)),
                            )
                        except Exception as exc:
                            st.session_state.project_result = None
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
                            add_history_entry(
                                file_a_name=file_a.name,
                                file_b_name=file_b.name,
                                provider_name=st.session_state.selected_provider,
                                model_name=model_name,
                                result_payload=result.to_dict(),
                                review_mode=mode,
                                score=result.score,
                            )
                        except Exception as exc:
                            st.session_state.compare_result = None
                            st.session_state.last_error = "Unexpected error: {0}".format(exc)

            if st.session_state.last_error:
                st.error(st.session_state.last_error)

            render_previews()

            result = st.session_state.compare_result
            if result:
                render_result_summary(result)
                tab1, tab2, tab3, tab4 = st.tabs(["Changes", "Issues", "Suggestions", "Raw JSON"])
                with tab1:
                    render_changes_tab(result)
                with tab2:
                    render_issues_tab(result)
                with tab3:
                    render_suggestions_tab(result)
                with tab4:
                    render_raw_tab(result)

    with history_tab:
        render_history_tab()


if __name__ == "__main__":
    main()
