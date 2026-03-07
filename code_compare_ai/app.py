import traceback
from datetime import datetime

import streamlit as st

from config import (
    AI_PROVIDER,
    DEFAULT_PROMPT_FILE,
    DEFAULT_RESPONSE_LANGUAGE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MAX_FILE_SIZE_KB,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    REQUEST_TIMEOUT_SECONDS,
)
from core.compare_service import CompareService
from core.models import CompareRequest, ProviderConfig
from core.prompts import (
    build_compare_prompt,
    list_prompt_files,
    load_prompt_template,
    save_custom_prompt,
)
from utils import detect_language_from_extension, read_uploaded_file


st.set_page_config(
    page_title="Code Compare AI",
    page_icon="🧠",
    layout="wide",
)

PROVIDER_OPTIONS = ["gemini", "openai", "ollama"]
LANGUAGE_OPTIONS = ["Portuguese (Brazil)", "English"]


def initialize_session():
    prompt_files = list_prompt_files()
    default_prompt_name = DEFAULT_PROMPT_FILE if DEFAULT_PROMPT_FILE in prompt_files else (prompt_files[0] if prompt_files else "")

    defaults = {
        "selected_provider": AI_PROVIDER if AI_PROVIDER in PROVIDER_OPTIONS else "gemini",
        "response_language": DEFAULT_RESPONSE_LANGUAGE if DEFAULT_RESPONSE_LANGUAGE in LANGUAGE_OPTIONS else "Portuguese (Brazil)",
        "selected_prompt_file": default_prompt_name,
        "prompt_text": load_prompt_template(default_prompt_name) if default_prompt_name else "",
        "provider_api_key": "",
        "ollama_base_url": OLLAMA_BASE_URL,
        "compare_result": "",
        "last_error": "",
        "save_prompt_name": "",
        "history": [],
        "gemini_model": GEMINI_MODEL,
        "openai_model": OPENAI_MODEL,
        "ollama_model": OLLAMA_MODEL,
        "last_code_a": "",
        "last_code_b": "",
        "last_file_a_name": "",
        "last_file_b_name": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_session()


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

    selected_prompt_file = st.selectbox(
        "Prompt template",
        prompt_files,
        index=current_index,
        key="modal_selected_prompt_file",
    )

    response_language = st.selectbox(
        "Response language",
        LANGUAGE_OPTIONS,
        index=LANGUAGE_OPTIONS.index(st.session_state.response_language),
        key="modal_response_language",
    )

    edited_prompt = st.text_area(
        "Prompt content",
        value=st.session_state.prompt_text,
        height=220,
        key="modal_prompt_text",
    )

    save_name = st.text_input(
        "Save as custom prompt (.md)",
        value=st.session_state.save_prompt_name,
        key="modal_save_prompt_name",
        placeholder="my_prompt.md",
    )

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

    provider = st.sidebar.selectbox(
        "Provider",
        PROVIDER_OPTIONS,
        index=PROVIDER_OPTIONS.index(st.session_state.selected_provider),
        key="selected_provider",
    )

    st.sidebar.subheader("Connection")

    if provider == "gemini":
        st.sidebar.text_input(
            "Model",
            key="gemini_model",
            help="Example: gemini-1.5-flash",
        )
        st.sidebar.text_input(
            "Gemini API Key",
            value=st.session_state.provider_api_key,
            key="provider_api_key",
            type="password",
            help="Leave empty to use GEMINI_API_KEY from .env",
        )

    elif provider == "openai":
        st.sidebar.text_input(
            "Model",
            key="openai_model",
            help="Example: gpt-4.1-mini",
        )
        st.sidebar.text_input(
            "OpenAI API Key",
            value=st.session_state.provider_api_key,
            key="provider_api_key",
            type="password",
            help="Leave empty to use OPENAI_API_KEY from .env",
        )

    elif provider == "ollama":
        st.sidebar.text_input(
            "Model",
            key="ollama_model",
            help="Example: qwen2.5-coder:7b",
        )
        st.sidebar.text_input(
            "Ollama Base URL",
            value=st.session_state.ollama_base_url,
            key="ollama_base_url",
            help="Leave as default if Ollama is running locally.",
        )

    st.sidebar.divider()
    st.sidebar.subheader("Prompt")
    st.sidebar.caption("Template: `{0}`".format(st.session_state.selected_prompt_file))
    st.sidebar.caption("Response language: `{0}`".format(st.session_state.response_language))

    st.sidebar.divider()
    with st.sidebar.expander("Advanced settings", expanded=False):
        st.caption("Timeout: {0}s".format(REQUEST_TIMEOUT_SECONDS))
        st.caption("Max file size: {0} KB".format(MAX_FILE_SIZE_KB))

def info_card(title, value):
    st.markdown(
        f"""
        <div style="
            border:1px solid #e6e6e6;
            border-radius:8px;
            padding:10px 14px;
            background:#fafafa;
        ">
            <div style="
                font-size:12px;
                color:#888;
                margin-bottom:4px;
            ">
                {title}
            </div>
            <div style="
                font-size:16px;
                font-weight:600;
            ">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_header():
    st.title("Code Compare AI")
    st.caption("Compare 2 code files with Gemini, OpenAI or Ollama using the same interface.")

    action_col1, action_col2, _ = st.columns([1, 1, 4])
    with action_col1:
        if st.button("Edit prompt", use_container_width=True):
            prompt_editor_dialog()
    with action_col2:
        if st.button("Clear result", use_container_width=True):
            st.session_state.compare_result = ""
            st.session_state.last_error = ""
            st.session_state.last_code_a = ""
            st.session_state.last_code_b = ""
            st.session_state.last_file_a_name = ""
            st.session_state.last_file_b_name = ""
            st.rerun()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        info_card("Provider", f"🤖 {st.session_state.selected_provider}")

    with col2:
        info_card("Model", f"🧠 {get_current_model(st.session_state.selected_provider)}")

    with col3:
        info_card("Prompt", f"📄 {st.session_state.selected_prompt_file}")

    with col4:
        info_card("Language", f"🌐 {st.session_state.response_language} ")

def render_upload_area():
    col1, col2 = st.columns(2)

    with col1:
        file_a = st.file_uploader(
            "File A",
            type=None,
            key="file_a",
            help="Upload the original or reference file.",
        )

    with col2:
        file_b = st.file_uploader(
            "File B",
            type=None,
            key="file_b",
            help="Upload the changed or candidate file.",
        )

    return file_a, file_b


def validate_file_size(uploaded_file):
    max_size_bytes = MAX_FILE_SIZE_KB * 1024
    if uploaded_file.size > max_size_bytes:
        raise ValueError(
            "File '{0}' exceeds the limit of {1} KB.".format(
                uploaded_file.name,
                MAX_FILE_SIZE_KB,
            )
        )


def compare_files(file_a, file_b):
    validate_file_size(file_a)
    validate_file_size(file_b)

    code_a = read_uploaded_file(file_a)
    code_b = read_uploaded_file(file_b)

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
    )

    service = CompareService()
    result = service.compare(request, provider_config)
    return result, code_a, code_b, model_name


def add_history_entry(file_a_name, file_b_name, provider_name, model_name, result):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file_a_name": file_a_name,
        "file_b_name": file_b_name,
        "provider_name": provider_name,
        "model_name": model_name,
        "result": result,
    }
    st.session_state.history.insert(0, entry)
    st.session_state.history = st.session_state.history[:10]


def render_previews():
    if not st.session_state.last_code_a or not st.session_state.last_code_b:
        return

    with st.expander("Preview files", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**File A: {0}**".format(st.session_state.last_file_a_name))
            st.code(
                st.session_state.last_code_a,
                language=detect_language_from_extension(st.session_state.last_file_a_name),
            )

        with col2:
            st.markdown("**File B: {0}**".format(st.session_state.last_file_b_name))
            st.code(
                st.session_state.last_code_b,
                language=detect_language_from_extension(st.session_state.last_file_b_name),
            )


def render_history_tab():
    st.subheader("History")

    if not st.session_state.history:
        st.info("No comparisons yet in this session.")
        return

    for index, item in enumerate(st.session_state.history):
        title = "{0} · {1} → {2} · {3}/{4}".format(
            item["timestamp"],
            item["file_a_name"],
            item["file_b_name"],
            item["provider_name"],
            item["model_name"],
        )
        with st.expander(title, expanded=(index == 0)):
            st.markdown(item["result"])


def main():
    render_sidebar()
    render_header()

    compare_tab, history_tab = st.tabs(["Compare", "History"])

    with compare_tab:
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
                        result, code_a, code_b, model_name = compare_files(file_a, file_b)
                        st.session_state.compare_result = result
                        st.session_state.last_error = ""
                        st.session_state.last_code_a = code_a
                        st.session_state.last_code_b = code_b
                        st.session_state.last_file_a_name = file_a.name
                        st.session_state.last_file_b_name = file_b.name
                        add_history_entry(
                            file_a_name=file_a.name,
                            file_b_name=file_b.name,
                            provider_name=st.session_state.selected_provider,
                            model_name=model_name,
                            result=result,
                        )
                    except Exception as exc:
                        st.session_state.compare_result = ""
                        st.session_state.last_error = "Unexpected error: {0}".format(exc)

        if st.session_state.last_error:
            st.error(st.session_state.last_error)
            with st.expander("Technical details", expanded=False):
                st.code(traceback.format_exc())

        render_previews()

        if st.session_state.compare_result:
            st.markdown("## Result")
            st.markdown(st.session_state.compare_result)

    with history_tab:
        render_history_tab()


if __name__ == "__main__":
    main()
