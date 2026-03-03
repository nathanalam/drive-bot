# AI Chief of Staff (Drive-Bot)

This project runs an autonomous AI Chief of Staff directly from your terminal. It continuously polls a task list, executes those tasks using a local [Ollama](https://ollama.com/) instance, and uses a shared **Google Drive folder** as both its persistent workspace and the communication channel with you.

## Features
- **Local First & Private**: All intelligence is powered by your local Ollama instance — no cloud AI.
- **Continuous Loop**: Runs in a continuous loop, executing tasks and asking for input when blocked.
- **Google Drive Workspace**: The agent owns a Drive folder. Its todo list, memories, and skills all live there as Google Docs, and it can freely create, read, update, and delete additional files in that folder.
- **Code Execution**: The agent can write and run Python code in a sandboxed subprocess. The `drive_bot_tools` module is available inside executed code for authenticated access to all Google APIs.
- **Google Custom Search**: The agent can search the web via `drive_bot_tools.search()` inside code execution — results are fed back into the agent's next reasoning step.
- **Manager Communication**: A `Manager Chat` document inside the workspace folder serves as the live communication channel between you and the agent.

## Setup Instructions

1. **Install Prerequisites**: Ensure you have [uv](https://docs.astral.sh/uv/) installed. You must also have [Ollama](https://ollama.com/) installed and running locally with at least one model pulled (e.g., `ollama pull gemma3:12b`).

2. **Set Up Google Cloud**:
   - Create a Google Cloud Project and enable the **Google Docs API**, **Google Drive API**, and optionally the **Custom Search API**.
   - In **APIs & Services → Credentials**, create an **OAuth 2.0 Client ID** of type **Desktop app** and download the JSON file.
   - For Custom Search: create a [Programmable Search Engine](https://programmablesearchengine.google.com/) and generate an **API key** in Google Cloud Console → APIs & Services → Credentials.

3. **Create the Drive Workspace Folder**:
   - Create a new folder in Google Drive.
   - Share it with your service account's email address with **Editor** permissions.
   - Copy the folder ID from its URL: `https://drive.google.com/drive/folders/FOLDER_ID`

4. **Run the Initialization Wizard**:
    ```bash
    uv run main.py
    ```

5. **Follow the Wizard**. The CLI will guide you to:
    - Select your active Ollama model.
    - Provide the path to your OAuth2 Desktop app credentials JSON file.
    - Authorize the app in your browser (one-time — token is saved to `token.json`).
    - Provide the Google Drive Folder ID for the workspace.
    - Optionally configure Google Custom Search (API key + Search Engine ID).

   On first run, the wizard automatically creates a `Manager Chat` document inside the workspace folder. Open it in Google Drive to send instructions to the agent.

## Workspace Structure

Once running, the agent manages the following documents inside the workspace folder:

| Document | Purpose |
|---|---|
| `Manager Chat` | Live communication channel — you write here, the agent reads and responds |
| `todo` | The agent's current task queue |
| `memories` | The agent's persistent key-value knowledge store |
| `skills` | Learned procedures and workflows |

The agent can also create, read, update, and delete arbitrary files in the folder as part of its work, and can run Python code that calls any of these APIs programmatically via `drive_bot_tools`.

## Development

You can format and check your code using the predefined make targets:

- Ensure typing and standards are consistent:
    ```bash
    make check
    ```
- Auto-format the project:
    ```bash
    make format
    ```
