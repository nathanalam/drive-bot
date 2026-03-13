"""
Pydantic AI agent with Google Drive workspace tools.

The agent uses a local Ollama model via OpenAI-compatible API and exposes
Drive file operations, state management, code execution, and web search
as native function tools.
"""

import json
import os
from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from google_auth_doc import (
    append_to_doc,
    read_doc_text,
    overwrite_doc,
    get_or_create_doc,
)
from code_executor import run_code
from rich.console import Console

console = Console()

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(cfg: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Dependencies ──────────────────────────────────────────────────────────────


@dataclass
class AgentDeps:
    """Runtime dependencies injected into every tool via RunContext."""

    folder_id: str
    chat_doc_id: str | None = None
    search_api_key: str | None = None
    search_cx: str | None = None
    # Tracks whether a question is pending for the manager
    pending_question: str | None = None
    # Caches for state doc IDs
    _doc_ids: dict[str, str] = field(default_factory=dict)

    def state_doc_id(self, name: str) -> str:
        """Get-or-create a state doc (todo / memories / skills) and cache its ID."""
        if name not in self._doc_ids:
            doc_id = get_or_create_doc(name, self.folder_id)
            if doc_id:
                self._doc_ids[name] = doc_id
        return self._doc_ids.get(name, "")

    def load_state(self, name: str, default=None):
        doc_id = self.state_doc_id(name)
        if not doc_id:
            return default
        text = (read_doc_text(doc_id) or "").strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except Exception:
            return default

    def save_state(self, name: str, data):
        doc_id = self.state_doc_id(name)
        if doc_id:
            overwrite_doc(doc_id, json.dumps(data, indent=2))

    def check_manager_chat(self) -> str | None:
        """Check the Manager Chat doc for a new manager reply.

        Returns the reply text if the manager has responded after the last
        ``[AI]:`` message, otherwise ``None``.
        """
        if not self.chat_doc_id:
            return None
        text = read_doc_text(self.chat_doc_id)
        if not text:
            return None
        parts = text.split("[AI]:")
        if len(parts) <= 1:
            return None
        # Everything after the last [AI]: message
        after_last_ai = parts[-1]
        lines = after_last_ai.split("\n")
        # Skip the first line (the AI question itself) and look for a reply
        manager_reply = "\n".join(lines[1:]).strip()
        if len(manager_reply) <= 5:
            return None
        # Extract tagged reply or use raw text
        if "[Manager]:" in manager_reply:
            return manager_reply.split("[Manager]:")[-1].strip()
        return manager_reply


# ── Model factory ─────────────────────────────────────────────────────────────


def build_model(model_name: str, api_key: str) -> OpenAIChatModel:
    """Create a Pydantic AI model using OpenRouter."""
    return OpenAIChatModel(
        model_name,
        provider=OpenRouterProvider(api_key=api_key),
    )


# ── Agent definition ──────────────────────────────────────────────────────────


def create_agent(model_name: str, api_key: str) -> Agent[AgentDeps, str]:
    model = build_model(model_name, api_key)

    agent = Agent(
        model,
        deps_type=AgentDeps,
        output_type=str,
        instructions=(
            "You are an AI Chief of Staff. You manage tasks, files, and knowledge "
            "inside a Google Drive workspace folder. Use the available tools to "
            "list, read, create, and delete files, manage your task list and "
            "memories, run Python code, search the web, and communicate with "
            "your manager. Always be proactive: if you have pending tasks, work "
            "on them. If you have none, ask the manager for more work."
        ),
    )

    # ── Dynamic system prompt: inject live state ──────────────────────────

    @agent.system_prompt
    def inject_state(ctx: RunContext[AgentDeps]) -> str:
        deps = ctx.deps
        todos = deps.load_state("todo", [])
        memories = deps.load_state("memories", {})
        skills = deps.load_state("skills", {})
        return (
            f"Current tasks: {json.dumps(todos)}\n"
            f"Memories: {json.dumps(memories)}\n"
            f"Skills: {json.dumps(skills)}"
        )

    # ── Drive tools (auto-generated from drive_bot_tools) ──────────────────

    import drive_bot_tools as _dt
    import inspect as _inspect

    # Each entry: (tool_name, drive_bot_tools_function)
    # Docstrings are taken directly from drive_bot_tools.
    _DRIVE_TOOLS = [
        ("list_workspace_files", _dt.list_files),
        ("list_all_files", _dt.list_all_files),
        ("list_folder", _dt.list_folder),
        ("read_file", _dt.read_file),
        ("write_file", _dt.write_file),
        ("append_to_file", _dt.append_to_file),
        ("replace_in_file", _dt.replace_in_file),
        ("delete_file", _dt.delete_file),
        ("create_folder", _dt.create_folder),
        ("move_file", _dt.move_file),
        ("copy_file", _dt.copy_file),
        ("rename_file", _dt.rename_file),
    ]

    def _make_drive_tool(fn):
        """Wrap a drive_bot_tools function as a plain agent tool."""
        sig = _inspect.signature(fn)

        def wrapper(**kwargs):
            try:
                result = fn(**kwargs)
                if result is None:
                    return "Done."
                if isinstance(result, list):
                    if not result:
                        return "(empty)"
                    lines = []
                    for item in result:
                        if isinstance(item, dict) and "path" in item:
                            lines.append(f"- {item['path']} ({item.get('mimeType', '').split('.')[-1]})")
                        elif isinstance(item, dict):
                            lines.append(f"- {item.get('name', '?')} (id={item.get('id', '?')}, {item.get('mimeType', '').split('.')[-1]})")
                        else:
                            lines.append(f"- {item}")
                    return "\n".join(lines)
                return str(result)
            except Exception as e:
                return f"Error: {e}"

        # Copy everything Pydantic AI needs to build the tool schema
        wrapper.__signature__ = sig
        wrapper.__annotations__ = fn.__annotations__.copy()
        wrapper.__module__ = fn.__module__
        wrapper.__doc__ = fn.__doc__
        wrapper.__name__ = fn.__name__
        return wrapper

    for _tool_name, _tool_fn in _DRIVE_TOOLS:
        tool_wrapper = _make_drive_tool(_tool_fn)
        tool_wrapper.__name__ = _tool_name
        agent.tool_plain(tool_wrapper)



    # ── State management tools ────────────────────────────────────────────

    @agent.tool
    def add_task(ctx: RunContext[AgentDeps], task: str) -> str:
        """Add a new task to the pending task list."""
        todos = ctx.deps.load_state("todo", [])
        todos.append({"status": "pending", "desc": task})
        ctx.deps.save_state("todo", todos)
        return f"Added task: {task}"

    @agent.tool
    def complete_task(ctx: RunContext[AgentDeps], task_index: int, result: str) -> str:
        """Mark a task as complete by its index and record the result."""
        todos = ctx.deps.load_state("todo", [])
        if not (0 <= task_index < len(todos)):
            return f"Invalid task index {task_index}. You have {len(todos)} tasks."
        task = todos.pop(task_index)
        ctx.deps.save_state("todo", todos)
        # Log completion to the manager chat doc
        if ctx.deps.chat_doc_id:
            msg = f"\n[AI]: Completed task: {task['desc']}\nResult: {result}\n"
            append_to_doc(ctx.deps.chat_doc_id, msg)
        return f"Completed task: {task['desc']}"

    @agent.tool
    def add_memory(ctx: RunContext[AgentDeps], key: str, value: str) -> str:
        """Store a key-value pair in persistent memory."""
        memories = ctx.deps.load_state("memories", {})
        memories[key] = value
        ctx.deps.save_state("memories", memories)
        return f"Stored memory '{key}'."

    @agent.tool
    def update_skill(ctx: RunContext[AgentDeps], skill_name: str, details: str) -> str:
        """Save a named skill/procedure for future reference."""
        skills = ctx.deps.load_state("skills", {})
        skills[skill_name] = details
        ctx.deps.save_state("skills", skills)
        return f"Updated skill '{skill_name}'."

    # ── Manager communication ─────────────────────────────────────────────

    @agent.tool
    def ask_manager(ctx: RunContext[AgentDeps], question: str) -> str:
        """Post a question to the Manager Chat doc.

        This is non-blocking: the question is posted and the agent continues
        working. The manager's reply will be picked up automatically on the
        next loop iteration. Do NOT call this repeatedly with the same
        question — one call is enough.
        """
        if not ctx.deps.chat_doc_id:
            return "No Manager Chat document configured."
        append_to_doc(ctx.deps.chat_doc_id, f"\n[AI]: {question}\n")
        ctx.deps.pending_question = question
        console.print(
            f"[yellow]Posted question to Manager Chat: {question}[/yellow]"
        )
        return (
            "Question posted to Manager Chat. "
            "Continue working on any pending tasks. "
            "The manager's reply will be provided in a future iteration."
        )

    @agent.tool
    def check_manager_reply(ctx: RunContext[AgentDeps]) -> str:
        """Check whether the manager has replied in the Manager Chat doc."""
        reply = ctx.deps.check_manager_chat()
        if reply:
            ctx.deps.pending_question = None
            console.print(
                f"[green]Manager replied:[/green] {reply}"
            )
            return f"Manager replied: {reply}"
        if ctx.deps.pending_question:
            return (
                f"No reply yet. Your pending question: "
                f"{ctx.deps.pending_question}"
            )
        return "No pending questions and no new manager messages."

    # ── Code execution ────────────────────────────────────────────────────

    @agent.tool_plain
    def execute_python(code: str) -> str:
        """Run a Python snippet in a sandboxed subprocess.

        The module `drive_bot_tools` is importable inside the snippet and
        exposes the full Drive API:
          - search(query)               — Google Custom Search
          - list_files()                — top-level workspace files
          - list_all_files()            — recursive listing with paths
          - list_folder(folder_id)      — list a subfolder's contents
          - read_file(name)             — read a file's text
          - write_file(name, content)   — create or overwrite
          - append_to_file(name, text)  — append text to a file
          - replace_in_file(name, old, new) — find-and-replace in a file
          - delete_file(name)           — delete a file
          - create_folder(name)         — create a subfolder
          - move_file(name, folder_id)  — move a file
          - copy_file(name, new_name)   — copy a file
          - rename_file(name, new_name) — rename a file

        Returns captured stdout/stderr. Timeout: 30 seconds.
        """
        if not code.strip():
            return "No code provided."
        console.print("[yellow]Executing code...[/yellow]")
        stdout, stderr, returncode = run_code(code)
        parts = []
        if stdout:
            parts.append(f"stdout:\n{stdout.rstrip()}")
        if stderr:
            parts.append(f"stderr:\n{stderr.rstrip()}")
        if returncode != 0:
            parts.append(f"Exit code: {returncode}")
        return "\n".join(parts).strip() or "(no output)"

    # ── Web search ────────────────────────────────────────────────────────

    @agent.tool
    def web_search(ctx: RunContext[AgentDeps], query: str) -> str:
        """Search the web using Google Custom Search. Returns titles, links, and snippets."""
        api_key = ctx.deps.search_api_key
        cx = ctx.deps.search_cx
        if not api_key or not cx:
            return "Web search is not configured. Ask the manager to set it up."
        from googleapiclient.discovery import build as gbuild

        service = gbuild("customsearch", "v1", developerKey=api_key)
        result = service.cse().list(q=query, cx=cx, num=10).execute()
        items = result.get("items", [])
        if not items:
            return "No search results found."
        lines = []
        for item in items:
            lines.append(
                f"- {item.get('title', '')}\n  {item.get('link', '')}\n  {item.get('snippet', '')}"
            )
        return "\n".join(lines)

    return agent

