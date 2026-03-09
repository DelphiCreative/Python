# Code Compare AI v10

AI-powered code review tool that analyzes file changes, detects potential issues, and generates structured technical feedback using multiple AI providers.

## What is new in v10

- Automatic language detection based on file extension
- Language-aware prompt selection for Delphi, Python, C#, SQL and JavaScript/TypeScript
- Improved score presentation with visual quality panels
- Existing review modes preserved:
  - File Compare
  - Diff Review
  - Multi-File Review
  - Git Review

## Supported AI providers

- Gemini
- OpenAI
- Ollama

## Main capabilities

- Compare two files with structured AI review output
- Focus on modified lines with Diff Review
- Review multiple matched files in one run
- Review modified files from a local Git repository
- Persist history in SQLite
- Filter issues by severity and category
- Download raw JSON review output

## Language-aware prompts

When the default prompt template is selected, the application automatically switches to a specialized prompt according to the detected language:

- `.pas`, `.dpr` -> Delphi / Object Pascal
- `.py` -> Python
- `.cs` -> C#
- `.sql` -> SQL
- `.js`, `.ts` -> JavaScript / TypeScript

Custom prompt templates still work normally. If you select a custom prompt, the automatic language-based switch is not applied.

## Run

```bash
python -m venv venv
venv\Scriptsctivate
pip install -r requirements.txt
streamlit run app.py
```

## Suggested commit message

```text
feat: add language-aware prompts and visual score panels (v10)
```

## Author

Diego Cataneo  
GitHub: https://github.com/DelphiCreative  
YouTube: https://youtube.com/@delphicreative


## Ollama local stability

This version adds configurable local execution settings for Ollama:

- `OLLAMA_TIMEOUT_SECONDS`
- `OLLAMA_MAX_PROMPT_CHARS`

You can also test the Ollama connection directly from the sidebar.
