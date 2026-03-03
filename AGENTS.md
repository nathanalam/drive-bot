# Agent Architecture

The AI Chief of Staff acts as an autonomous loop engine that continually processes local task queues.

## Core Components
- **StateManager**: A simple filesystem helper that handles the local JSON caching for:
    - `todos.json`: Represents current pending tasks.
    - `memories.json`: Abstract persistent datastore for the agent.
    - `skills.json`: Represent learned steps or macros over time.
    - `config.json`: Information cached by the startup wizard (model name, and service account IDs).
- **AIAgent**: The core engine that relies on JSON-mode outputs from local Ollama models. It queries the local context and handles dynamic responses using a predefined System Prompt.
- **Google Auth & Docs Integration**: Polling mechanism that watches for new interactions from the manager via an authorized Google Doc when the "To Do" list is completely empty.

## Actions

The agent is capable of outputting specifically structured JSON to trigger different interactions out of the `agent.py`:

- `think`: Simply processes intermediate thinking contexts.
- `add_memory`: Safely writes a key-value abstract representation of past knowledge to `memories.json`.
- `update_skill`: Identifies step-by-step logic the agent might need for the specified workflow into `skills.json`.
- `add_task`: Injects a new manual task into `todos.json`.
- `complete_task`: Removes an executed task from the local queue, and conditionally pushes the result into the Google Doc.
- `ask_manager`: Used when the task queue is entirely empty. The string asks the manager a clarifying next step within Google Docs prefixed with `[AI]:`. The engine then falls into a periodic polling mode to retrieve any new context underneath `[Manager]:` or untagged within the Doc!
