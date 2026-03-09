
# Code Compare AI

Code Compare AI is an AI-powered developer tool designed to compare source code files and perform intelligent code review using modern AI models.

The application analyzes differences between two versions of code and generates structured technical feedback including:

- Summary of changes
- Possible bugs introduced
- Performance risks
- Code quality issues
- Refactoring suggestions
- Code review score

Starting with **v7**, the tool introduces **Diff Review mode**, allowing the AI to focus on actual code changes instead of comparing entire files.

---

# Features

- Compare two code files using AI
- Diff-based code review
- Multiple review modes
- Multi-provider architecture
- Support for **Gemini, OpenAI and Ollama**
- Model selection directly in the UI
- Prompt editing through modal dialog
- Support for prompt templates (.md)
- Custom prompt creation
- Structured AI review output (JSON)
- Issue severity classification
- SQLite persistent review history
- Raw JSON inspection
- Clean Streamlit interface

---

# Review Modes

The application supports different review strategies depending on how the code should be analyzed.

## File Compare

Compares two files entirely.

Use this mode when you want a **complete comparison between two versions of a file**.

Input:

- File A
- File B

The AI analyzes the full contents of both files.

---

## Diff Review

Introduced in **v7**.

This mode focuses only on the **actual code changes** between two files.

The application generates a **unified diff** and sends it to the AI together with both file versions.

This allows the AI to focus on:

- modified lines
- newly introduced logic
- potential regressions

Diff Review is recommended when reviewing **code changes between versions**.

---

# Architecture

The application uses a provider abstraction layer so that AI services can be replaced without modifying the UI.

Streamlit UI
↓
Compare Service
↓
Review Mode Engine
↓
Provider Factory
↓
Gemini | OpenAI | Ollama

Benefits:

- Easy provider switching
- Future support for additional AI models
- Clean separation of responsibilities
- Easier testing

---

# Project Structure

code_compare_ai
│
├── app.py
├── config.py
├── utils.py
├── requirements.txt
├── run.bat
├── README.md
├── .gitignore
├── .env
│
├── core
│   ├── compare_service.py
│   ├── models.py
│   ├── prompts.py
│   └── result_parser.py
│
├── providers
│   ├── base.py
│   ├── factory.py
│   ├── gemini_provider.py
│   ├── openai_provider.py
│   └── ollama_provider.py
│
├── prompts
│   ├── compare_prompt.md
│   └── delphi_compare_prompt.md
│
└── custom_prompts

---

# Installation

Clone the repository

git clone https://github.com/DelphiCreative/Python.git

cd Python/code_compare_ai

Create virtual environment

python -m venv venv

Activate environment

Windows:
venv\Scripts\activate

Install dependencies

pip install -r requirements.txt

---

# Running

run.bat

or

streamlit run app.py

Then open

http://localhost:8501

---

# Author

Developed by **Diego Cataneo**

GitHub
https://github.com/DelphiCreative

YouTube
https://youtube.com/@delphicreative
