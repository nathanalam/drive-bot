# Agent Architecture

The AI Chief of Staff uses **Pydantic AI** to expose Drive workspace operations as native function tools. The LLM (via local Ollama) decides which tools to call — no manual JSON parsing or action dispatch.

## Core Components

- **`Agent[AgentDeps, str]`** (Pydantic AI): The central agent with tools registered via `@agent.tool` decorators. Uses `OpenAIModel` pointed at Ollama's OpenAI-compatible endpoint (`localhost:11434/v1`).
- **`AgentDeps`**: A dataclass injected into every tool via `RunContext`. Holds `folder_id`, `chat_doc_id`, search credentials, and cached state-doc IDs.
- **Dynamic system prompt**: A `@agent.system_prompt` decorator loads live state (tasks, memories, skills) from Drive on every run.
- **Google Drive Workspace**: The agent has full read/write/delete control over its assigned Drive folder. State documents, the manager chat log, and any files the agent creates all live here.
- **Manager Chat**: A Google Doc named `Manager Chat` inside the workspace folder. The agent appends `[AI]:` messages when it needs input; the manager writes replies directly into the doc.
- **Code Executor** (`code_executor.py`): Runs agent-authored Python snippets in a subprocess. `drive_bot_tools` is importable inside executed code.

## Local Files

| File | Purpose |
|---|---|
| `config.json` | Bootstrap config: model name, `folder_id`, `chat_doc_id`, `search_api_key`, `search_cx` |
| `oauth_credentials.json` | OAuth2 Desktop app client secrets |
| `token.json` | OAuth2 access + refresh token |

## Tools

All tools are registered on the Pydantic AI `Agent` and called by the LLM via native function calling:

| Tool | Description |
|---|---|
| `list_workspace_files` | List top-level files in the Drive workspace folder |
| `list_all_files` | Recursively list every file and subfolder with full paths |
| `list_folder(folder_id)` | List direct children of a specific subfolder by ID |
| `read_file(name)` | Read a file's text content |
| `write_file(name, content)` | Create or overwrite a file |
| `append_to_file(name, text)` | Append text to an existing file |
| `replace_in_file(name, old, new)` | Find-and-replace text inside a file |
| `delete_file(name)` | Delete a file from the workspace |
| `create_folder(name, parent_folder_id?)` | Create a subfolder (defaults to workspace root) |
| `move_file(file_name, target_folder_id)` | Move a file to a different folder |
| `copy_file(file_name, new_name, target_folder_id?)` | Copy a file |
| `rename_file(file_name, new_name)` | Rename a file |
| `add_task(task)` | Append a task to the persistent todo list |
| `complete_task(task_index, result)` | Remove a task and log completion to Manager Chat |
| `add_memory(key, value)` | Store a key-value pair in persistent memory |
| `update_skill(skill_name, details)` | Save a named procedure |
| `ask_manager(question)` | Post a question to Manager Chat (non-blocking) |
| `check_manager_reply` | Check whether the manager has replied in Manager Chat |
| `execute_python(code)` | Run Python in a sandboxed subprocess (30s timeout) |
| `web_search(query)` | Google Custom Search |

## Data Flow

```
main.py : run_loop()  [tick-based, every 10s]
  ├─> deps.check_manager_chat()       [non-blocking poll for manager reply]
  ├─> deps.load_state("todo")         [load current tasks]
  ├─> build context-aware prompt      [includes reply / tasks / pending Q]
  └─> agent.run_sync(prompt, deps=AgentDeps)
       ├─> @agent.system_prompt       [loads todo, memories, skills from Drive]
       ├─> LLM decides which tools to call (native function calling)
       └─> tool execution
            ├─> list_workspace_files   → list_files_in_folder()
            ├─> read_file              → find_file_in_folder() + read_doc_text()
            ├─> write_file             → get_or_create_doc() + overwrite_doc()
            ├─> delete_file            → find_file_in_folder() + delete_file_by_id()
            ├─> add_task / complete_task → load_state() / save_state()
            ├─> add_memory / update_skill → load_state() / save_state()
            ├─> ask_manager            → append_to_doc() [returns immediately]
            ├─> check_manager_reply    → check_manager_chat()
            ├─> execute_python         → code_executor.run_code()
            └─> web_search             → Google Custom Search API
```

## Development

Always run the linter and type checker before committing:

```bash
make check     # runs both: uv run ruff check . && uv run ty check .
make format    # auto-fix: uv run ruff format . && uv run ruff check --fix .
```

Or individually:

```bash
uv run ruff check .   # lint
uv run ty check .     # type check
```
