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
    HISTORY_LIMIT,
    MAX_FILE_SIZE_KB,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from core.compare_service import CompareService
from core.models import CompareRequest, ProviderConfig, StructuredCompareResult
from core.prompts import (
    build_compare_prompt,
    build_diff_review_prompt,
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
    st.title("Code Compare AI v7")
    st.caption("Diff Review added: compare complete files or focus the review on changed lines using the same interface.")

    action_col1, action_col2, _ = st.columns([1, 1, 4])
    with action_col1:
        if st.button("Edit prompt", use_container_width=True):
            prompt_editor_dialog()
    with action_col2:
        if st.button("Clear result", use_container_width=True):
            st.session_state.compare_result = None
            st.session_state.last_error = ""
            st.session_state.last_code_a = ""
            st.session_state.last_code_b = ""
            st.session_state.last_file_a_name = ""
            st.session_state.last_file_b_name = ""
            st.session_state.last_diff_text = ""
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


def render_upload_area():
    col1, col2 = st.columns(2)
    with col1:
        file_a = st.file_uploader("File A", type=None, key="file_a", help="Upload the original or reference file.")
    with col2:
        file_b = st.file_uploader("File B", type=None, key="file_b", help="Upload the changed or candidate file.")
    return file_a, file_b


def validate_file_size(uploaded_file):
    max_size_bytes = MAX_FILE_SIZE_KB * 1024
    if uploaded_file.size > max_size_bytes:
        raise ValueError("File '{0}' exceeds the limit of {1} KB.".format(uploaded_file.name, MAX_FILE_SIZE_KB))


def compare_files(file_a, file_b):
    validate_file_size(file_a)
    validate_file_size(file_b)

    code_a = read_uploaded_file(file_a)
    code_b = read_uploaded_file(file_b)
    review_mode = st.session_state.selected_review_mode
    diff_text = generate_unified_diff(file_a.name, code_a, file_b.name, code_b)

    if review_mode == "diff_review":
        prompt_text = build_diff_review_prompt(
            template=st.session_state.prompt_text,
            file_a_name=file_a.name,
            file_b_name=file_b.name,
            code_a=code_a,
            code_b=code_b,
            diff_text=diff_text,
            response_language=st.session_state.response_language,
        )
    else:
        prompt_text = build_compare_prompt(
            template=st.session_state.prompt_text,
            file_a_name=file_a.name,
            file_b_name=file_b.name,
            code_a=code_a,
            code_b=code_b,
            response_language=st.session_state.response_language,
        )

    provider_name = st.session_state.selected_provider
    model_name = get_current_model(provider_name)

    provider_config = ProviderConfig(
        provider_name=provider_name,
        model_name=model_name,
        api_key=get_effective_api_key(provider_name),
        base_url=st.session_state.ollama_base_url.strip(),
        timeout_seconds=REQUEST_TIMEOUT_SECONDS,
    )

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
    result = service.compare(request, provider_config)
    return result, code_a, code_b, diff_text, model_name


def add_history_entry(file_a_name, file_b_name, provider_name, model_name, result: StructuredCompareResult):
    entry = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_a_name": file_a_name,
        "file_b_name": file_b_name,
        "provider_name": provider_name,
        "model_name": model_name,
        "review_mode": st.session_state.selected_review_mode,
        "score": result.score,
        "result": result.to_dict(),
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


def render_changes_tab(result: StructuredCompareResult):
    if not result.changes_detected:
        st.info("No structured list of changes was returned.")
        return
    for item in result.changes_detected:
        st.markdown("- {0}".format(item))


def render_issues_tab(result: StructuredCompareResult):
    if not result.issues:
        st.success("No structured issues were found.")
        return

    severity_filter = st.multiselect(
        "Filter by severity",
        options=["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
    )
    category_options = sorted({issue.category for issue in result.issues})
    category_filter = st.multiselect(
        "Filter by category",
        options=category_options,
        default=category_options,
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


def render_suggestions_tab(result: StructuredCompareResult):
    if not result.suggestions:
        st.info("No suggestions were returned.")
        return
    for item in result.suggestions:
        with st.container(border=True):
            st.markdown("**{0}**".format(item.title))
            st.write(item.description)


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


def render_history_tab():
    st.subheader("History")
    items = list_history_entries(HISTORY_LIMIT)
    if not items:
        st.info("No comparisons saved yet.")
        return

    for index, item in enumerate(items):
        result = item.get("result", {})
        title = "{0} · {1} · {2} → {3} · {4}/{5} · score {6:.1f}".format(
            item.get("created_at", ""),
            item.get("review_mode", "file_compare"),
            item.get("file_a_name", ""),
            item.get("file_b_name", ""),
            item.get("provider_name", ""),
            item.get("model_name", ""),
            float(item.get("score", 0) or 0),
        )
        with st.expander(title, expanded=(index == 0)):
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
        if st.session_state.selected_review_mode == "diff_review":
            st.info("Diff Review focuses the AI analysis on the changed lines while still using the full files as context.")
        file_a, file_b = render_upload_area()
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
                        st.session_state.last_error = ""
                        st.session_state.last_code_a = code_a
                        st.session_state.last_code_b = code_b
                        st.session_state.last_file_a_name = file_a.name
                        st.session_state.last_file_b_name = file_b.name
                        st.session_state.last_diff_text = diff_text
                        add_history_entry(file_a.name, file_b.name, st.session_state.selected_provider, model_name, result)
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
