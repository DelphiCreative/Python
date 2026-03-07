# Code Compare AI

Code Compare AI is a developer tool designed to compare two source code
files using modern AI models.

The application analyzes differences between two versions of a file and
generates a structured technical analysis including:

-   Summary of changes
-   Possible bugs introduced
-   Performance risks
-   Code quality issues
-   Refactoring suggestions

The application supports multiple AI providers through the same
interface.

Supported providers:

-   Google Gemini
-   OpenAI
-   Ollama (local models)

The goal of this project is to provide a flexible architecture where AI
providers can be easily swapped without modifying the application
interface.

------------------------------------------------------------------------

# Features

-   Compare two code files using AI
-   Multi-provider architecture
-   Clean Streamlit interface
-   Dynamic credential fields depending on provider
-   Model selection directly in the UI
-   Prompt editing through modal dialog
-   Support for prompt templates (.md)
-   Custom prompt creation
-   Comparison history in the session
-   Works with multiple programming languages

------------------------------------------------------------------------

# Architecture

The application uses a provider abstraction layer so that AI services
can be replaced without modifying the UI.

Streamlit UI ↓ Compare Service ↓ Provider Factory ↓ Gemini \| OpenAI \|
Ollama

Benefits of this architecture:

-   Easy provider switching
-   Future support for additional AI models
-   Clean separation of responsibilities
-   Easier testing

------------------------------------------------------------------------

# Project Structure
```
code_compare_ai/
├── app.py
├── run.bat
├── requirements.txt
├── README.md
├── .gitignore
├── .env
├── core/
│   ├── compare_service.py
│   ├── models.py
│   └── prompts.py
├── providers/
│   ├── base.py
│   ├── openai_provider.py
│   ├── gemini_provider.py
│   └── ollama_provider.py
├── prompts/
│   ├── compare_prompt.md
│   └── delphi_compare_prompt.md
└── custom_prompts/
```

------------------------------------------------------------------------

# Installation

Clone the repository

git clone https://github.com/your-repository/code-compare-ai.git cd
code-compare-ai

Create a virtual environment

python -m venv venv

Activate the environment

Windows

venv`\Scripts`{=tex}`\activate`{=tex}

Install dependencies

pip install -r requirements.txt

------------------------------------------------------------------------

# Configuration

Create a `.env` file in the root folder.

Example:

AI_PROVIDER=gemini

GEMINI_API_KEY=your_api_key

OPENAI_API_KEY=

OLLAMA_BASE_URL=http://localhost:11434

The application also allows API keys to be entered directly in the
interface.

------------------------------------------------------------------------

# Running the Application

The easiest way to start the project is:

run.bat

Or manually:

streamlit run app.py

After running the command, open:

http://localhost:8501

------------------------------------------------------------------------

# Using the Application

1.  Select the AI provider
2.  Select the model
3.  Enter the required credentials
4.  Upload two source code files
5.  Click **Compare**

The AI will generate a structured comparison of the files.

------------------------------------------------------------------------

# Prompt System

Prompts are stored as Markdown templates inside the `prompts` folder.

Example:

prompts/compare_prompt.md

The application supports:

-   Loading prompt templates
-   Editing prompts through the UI
-   Saving custom prompts
-   Selecting response language

Prompt variables:

{{response_language}} {{file_a_name}} {{file_b_name}} {{code_a}}
{{code_b}}

This allows prompt customization without modifying the source code.

------------------------------------------------------------------------

# Supported Providers

## Gemini

Uses Google AI Studio.

Create an API key at:

https://aistudio.google.com

Recommended model:

gemini-1.5-flash

------------------------------------------------------------------------

## OpenAI

Uses the OpenAI API.

Create an API key at:

https://platform.openai.com

Recommended models:

gpt-4.1-mini gpt-4o-mini

------------------------------------------------------------------------

## Ollama

Allows running models locally.

Install Ollama:

https://ollama.com

Example model:

qwen2.5-coder

------------------------------------------------------------------------

# Custom Prompts

Custom prompts can be stored inside:

custom_prompts/

They can be loaded and edited from the UI.

------------------------------------------------------------------------

# Security

Never commit the `.env` file to version control.

Sensitive information includes:

-   API keys
-   credentials
-   local configuration

The `.gitignore` file already excludes these files.

------------------------------------------------------------------------

# Future Improvements

Possible future features:

-   Side-by-side code diff visualization
-   Project-level comparison
-   Pull request analysis
-   Persistent comparison history
-   Syntax highlighted diff viewer
-   Support for additional AI providers

------------------------------------------------------------------------

# Contributing

Contributions are welcome.

Feel free to open issues or submit pull requests.

------------------------------------------------------------------------

# Author

Developed by

Diego Cataneo

Software Developer\
Delphi Specialist

GitHub\
https://github.com/DelphiCreative

YouTube\
https://youtube.com/@delphicreative

------------------------------------------------------------------------

# Delphi Creative

This project is part of the Delphi Creative initiative focused on
sharing knowledge and building tools for developers.
