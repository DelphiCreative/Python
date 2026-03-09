# Code Compare AI v6

Code Compare AI v6 is a Streamlit-based code review tool that compares two files and asks an AI provider to return a structured review in JSON.

## What's new in v6

- Structured JSON output
- Score, issues, suggestions and detected changes
- Severity and category support
- Resilient JSON parser with fallback to raw response
- SQLite history persistence
- Cleaner review UI with overview cards and issue filters
- Raw JSON export

## Providers

- Gemini
- OpenAI
- Ollama

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

Or use:

```bat
run.bat
```

## Notes

- API keys can be entered in the sidebar or provided via `.env`.
- Prompt templates are stored in `prompts/`.
- Custom prompts are stored in `custom_prompts/`.
- History is stored in `data/history.db`.

## Author

Diego Cataneo  
GitHub: https://github.com/DelphiCreative  
YouTube: https://youtube.com/@delphicreative
