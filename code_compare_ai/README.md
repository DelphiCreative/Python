# Code Compare AI v8

Code Compare AI v8 builds on v7 and keeps the existing File Compare and Diff Review modes.

## What's new in v8

- Manual Multi-File Review
- No ZIP uploads required
- Match files by file name on both sides
- Per-file score
- Consolidated project score
- Automatic Delphi prompt selection for `.pas` and `.dpr` when using the default prompt
- History support for project reviews

## Review modes

- **File Compare**: compares two full files
- **Diff Review**: focuses the AI on changed lines
- **Multi-File Review**: compares multiple file pairs matched by file name

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

Or use:

```bat
run.bat
```

## Multi-file notes

- Upload multiple files in **Files A** and **Files B**
- Pairing is done by **file name**
- Duplicate names are not supported in multi-file mode
- The number of matched pairs is limited by `MAX_MULTI_FILE_PAIRS` in `.env`

## Author

Diego Cataneo  
GitHub: https://github.com/DelphiCreative  
YouTube: https://youtube.com/@delphicreative
