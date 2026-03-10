# Code Compare AI

AI-powered code review tool designed to analyze code changes and generate structured technical feedback.

This project demonstrates how **Large Language Models (LLMs)** can assist developers during code review by analyzing source code changes, detecting potential issues, and suggesting improvements.

The system supports multiple AI providers including **OpenAI**, **Google Gemini**, and **local models via Ollama**.

---

# Features

### File Compare

Compare two files and generate an AI-powered review of the entire code.

### Diff Review

Analyze only the modified lines between two files using unified diff.

### Multi-File Review

Review multiple files in a single analysis session.

### Git Review

Inspect modified files directly from a local Git repository.

### Multi AI Providers

Switch between different AI providers:

* OpenAI
* Google Gemini
* Ollama (local LLMs)

### Structured AI Output

The system produces structured review results including:

* Summary
* Issues
* Severity levels
* Suggestions
* Code quality score

---

# Architecture

The system follows a modular architecture separating UI, review engine, prompts, and AI providers.

```
Streamlit UI
     ↓
Review Engine
     ↓
Prompt System
     ↓
Provider Layer
     ↓
OpenAI | Gemini | Ollama
```

This design allows the system to support new providers with minimal changes.

---

# Supported Review Modes

| Mode              | Description                                  |
| ----------------- | -------------------------------------------- |
| File Compare      | Compare two files entirely                   |
| Diff Review       | Analyze only modified lines                  |
| Multi-File Review | Review multiple files                        |
| Git Review        | Analyze modified files from a Git repository |

---

# Example AI Review Output

```json
{
  "summary": "Refactoring improved readability but introduced a potential null reference risk.",
  "score": 7.8,
  "issues": [
    {
      "severity": "high",
      "category": "bug",
      "title": "Possible null reference",
      "description": "Object may be null before method invocation."
    }
  ]
}
```

---

# Technologies Used

* Python
* Streamlit
* OpenAI API
* Google Gemini API
* Ollama (local LLMs)
* Git CLI integration

---

# Installation

Clone the repository:

```bash
git clone https://github.com/DelphiCreative/Python.git
cd code_compare_ai
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate the environment:

Windows

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run app.py
```

---

# Configuration

Environment variables can be used to configure providers.

Example `.env`:

```
OPENAI_API_KEY=
GEMINI_API_KEY=

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT_SECONDS=300
OLLAMA_MAX_PROMPT_CHARS=18000
```

---

# Roadmap

Future ideas for the project include:

* language-aware prompts
* repository-wide analysis
* pull request analysis
* policy-based code review

---

# Author

Diego Cataneo

Software developer focused on backend systems and developer productivity tools.

GitHub
https://github.com/DelphiCreative

YouTube
https://youtube.com/@delphicreative
