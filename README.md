# AI Chief of Staff (Drive-Bot)

This project runs an autonomous AI Chief of Staff directly from your terminal. It continuously polls a localized task list, executes those tasks using an a local [Ollama](https://ollama.com/) instance, and directly interfaces with a Google Doc to ask clarifying questions and receive new instructions when its "To-Do" list runs empty!

## Features
- **Local First & Private**: Chatting and intelligence are powered completely by your local Ollama instance.
- **Continuous Loop**: Runs in its own continuous loop to execute tasks and ask for inputs when blocked.
- **Google Doc Integration**: Out-of-the-box support for using a shared Google Doc as the communication channel between you (the Manager) and the AI.
- **State Management**: Simple persistent state saved to JSON for your agent's memories, skills, and current tasks.

## Setup Instructions

1. **Install Prerequisites**: Ensure you have [uv](https://docs.astral.sh/uv/) installed. You must also have [Ollama](https://ollama.com/) installed and running locally. We recommend pulling at least one capable model (e.g., `ollama pull llama3`).
2. **Setup Google Cloud**: You'll need to create a Google Cloud Project, enable the **Google Docs API**, and generate a **Service Account JSON Key**.
3. **Run the Initialization Wizard**:
    Start the project by simply running:
    ```bash
    uv run main.py
    ```
4. **Follow the Wizard**: The CLI will guide you to:
    - Select your active Ollama model.
    - Path to your Google Service Account's `.json` key.
    - Provide the ID of a Google Doc. **Make sure this Google Doc has been shared with your Service Account's email address with "Editor" access.**

## Development

You can format and check your code using our predefined make targets:

- Ensure typing and standards are consistent:
    ```bash
    make check
    ```
- Auto-format the project:
    ```bash
    make format
    ```
