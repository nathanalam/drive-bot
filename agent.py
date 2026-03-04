import json
import os
import time
from ollama_client import chat
from google_auth_doc import (
    append_to_doc,
    read_doc_text,
    overwrite_doc,
    get_or_create_doc,
    list_files_in_folder,
    find_file_in_folder,
    delete_file_by_id,
)
from code_executor import run_code
from rich.console import Console
from rich.panel import Panel

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


class DriveStateManager:
    """Manages todo, memories, and skills as Google Docs in the Drive workspace folder."""

    DEFAULTS: dict = {
        "todo": [],
        "memories": {},
        "skills": {},
    }

    def __init__(self, folder_id: str):
        self.folder_id = folder_id
        self._ids: dict = {}  # name -> doc_id cache

    def _doc_id(self, name: str) -> str | None:
        if name not in self._ids:
            self._ids[name] = get_or_create_doc(name, self.folder_id)
        return self._ids[name]

    def _load(self, name: str):
        doc_id = self._doc_id(name)
        text = (read_doc_text(doc_id) or "").strip()
        if not text:
            return self.DEFAULTS[name]
        try:
            return json.loads(text)
        except Exception:
            return self.DEFAULTS[name]

    def _save(self, name: str, data):
        doc_id = self._doc_id(name)
        if doc_id:
            overwrite_doc(doc_id, json.dumps(data, indent=2))

    def get_todos(self):
        return self._load("todo")

    def save_todos(self, t):
        self._save("todo", t)

    def get_memories(self):
        return self._load("memories")

    def save_memories(self, m):
        self._save("memories", m)

    def get_skills(self):
        return self._load("skills")

    def save_skills(self, s):
        self._save("skills", s)


class AIAgent:
    def __init__(self):
        self.config = load_config()
        self.folder_id = self.config["folder_id"]
        self.chat_doc_id = self.config.get("chat_doc_id")
        self.state = DriveStateManager(self.folder_id)

    def system_prompt(self):
        return f"""You are an AI Chief of Staff running autonomously in a loop. You execute tasks, manage files in a Google Drive workspace, and report back to your manager.

RULES — follow these strictly:
- When your manager gives you an instruction, act on it immediately. Use add_task to record it, then complete it.
- Only use ask_manager when your task list is completely empty and you have nothing left to do.
- Never ask the manager a vague question like "what to do next?" if you already have an instruction. Execute it.
- Produce real, concrete outputs: write files, run code, create documents. Do not just think in circles.
- After completing a task, use complete_task to mark it done and report the result.

Current state:
- Skills: {json.dumps(self.state.get_skills())}
- Memories: {json.dumps(self.state.get_memories())}
- Tasks: {json.dumps(self.state.get_todos())}

Respond with ONLY a single JSON object. Valid actions:
1. {{"action": "think", "thought": "reasoning before a complex action"}}
2. {{"action": "add_memory", "key": "key", "value": "value"}}
3. {{"action": "update_skill", "skill": "name", "details": "step-by-step procedure"}}
4. {{"action": "add_task", "task": "clear description of what to do"}}
5. {{"action": "complete_task", "task_index": 0, "result": "what was produced or accomplished"}}
6. {{"action": "ask_manager", "question": "I have finished all my tasks. What should I work on next?"}}
7. {{"action": "list_files"}}
8. {{"action": "create_file", "name": "filename", "content": "full content"}}
9. {{"action": "read_file", "name": "filename"}}
10. {{"action": "write_file", "name": "filename", "content": "full content"}}
11. {{"action": "delete_file", "name": "filename"}}
12. {{"action": "run_code", "code": "import drive_bot_tools as tools\\nresults = tools.search('query')\\nfor r in results: print(r['title'], r['link'])"}}
    - Runs Python in a sandboxed subprocess. Import drive_bot_tools for Google API access:
        tools.search(query, num=10)     — Google Custom Search → list of {{title, link, snippet}}
        tools.list_files()              — list Drive workspace files
        tools.read_file(name)           — read file text
        tools.write_file(name, content) — create or overwrite a file
        tools.delete_file(name)         — delete a file
    - All stdout is captured and returned as the action result. Timeout: 30 seconds.
"""

    def parse_response(self, text):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return None

    def run_step(self, context=None, context_source="manager"):
        model = self.config.get("model")

        messages = [{"role": "system", "content": self.system_prompt()}]
        if context:
            if context_source == "manager":
                user_msg = (
                    f"Message from manager: {context}\n"
                    "Use add_task to record this instruction, then start working on it."
                )
            else:
                user_msg = f"Result of your last action: {context}\nWhat is your next action?"
            messages.append({"role": "user", "content": user_msg})
        else:
            todos = self.state.get_todos()
            if not todos:
                messages.append(
                    {
                        "role": "user",
                        "content": "Your task list is empty. Use ask_manager to request new work.",
                    }
                )
            else:
                messages.append(
                    {"role": "user", "content": "You have tasks. What is your next action?"}
                )

        response = chat(model, messages)
        action = self.parse_response(response)

        if not action:
            console.print(f"[red]Failed to parse action:[/red] {response}")
            return "thought", "Failed to parse JSON"

        act_type = action.get("action")
        console.print(
            Panel(
                f"Action: {act_type}\nDetails: {json.dumps(action, indent=2)}",
                title="Agent Action",
            )
        )

        if act_type == "add_memory":
            mems = self.state.get_memories()
            mems[action["key"]] = action["value"]
            self.state.save_memories(mems)
            return "memory_added", f"Added memory {action['key']}"

        elif act_type == "update_skill":
            skills = self.state.get_skills()
            skills[action["skill"]] = action["details"]
            self.state.save_skills(skills)
            return "skill_updated", f"Updated skill {action['skill']}"

        elif act_type == "add_task":
            todos = self.state.get_todos()
            todos.append({"status": "pending", "desc": action["task"]})
            self.state.save_todos(todos)
            return "task_added", f"Added task: {action['task']}"

        elif act_type == "complete_task":
            idx = action.get("task_index", -1)
            todos = self.state.get_todos()
            if 0 <= idx < len(todos):
                task = todos.pop(idx)
                self.state.save_todos(todos)
                if self.chat_doc_id:
                    msg = f"\n[AI]: Completed task: {task['desc']}\nResult: {action.get('result', '')}\n"
                    append_to_doc(self.chat_doc_id, msg)
                return "task_completed", task["desc"]

        elif act_type == "ask_manager":
            q = action.get("question", "What should I do next?")
            if self.chat_doc_id:
                append_to_doc(self.chat_doc_id, f"\n[AI]: {q}\n")
                console.print(
                    "[yellow]Asked manager via Google Doc. Waiting for response...[/yellow]"
                )
                reply = self._wait_for_manager(self.chat_doc_id)
                return "manager_replied", reply
            else:
                ans = console.input(f"[yellow]Agent asks: {q}[/yellow]\nYour reply: ")
                return "manager_replied", ans

        elif act_type == "list_files":
            files = list_files_in_folder(self.folder_id)
            if files:
                summary = "\n".join(
                    f"- {f['name']} ({f['mimeType'].split('.')[-1]})" for f in files
                )
            else:
                summary = "(workspace is empty)"
            console.print(f"[cyan]Files in workspace:[/cyan]\n{summary}")
            return "files_listed", f"Files in your Drive workspace:\n{summary}"

        elif act_type == "create_file":
            name = action.get("name", "untitled")
            content = action.get("content", "")
            doc_id = get_or_create_doc(name, self.folder_id)
            if doc_id and content:
                overwrite_doc(doc_id, content)
            console.print(f"[green]Created file:[/green] {name}")
            return "file_created", f"Created file '{name}'"

        elif act_type == "read_file":
            name = action.get("name", "")
            file_id = find_file_in_folder(name, self.folder_id)
            if not file_id:
                return "file_read", f"File '{name}' not found in workspace."
            content = read_doc_text(file_id) or ""
            console.print(f"[cyan]Read file:[/cyan] {name}")
            return "file_read", f"Contents of '{name}':\n{content}"

        elif act_type == "write_file":
            name = action.get("name", "untitled")
            content = action.get("content", "")
            doc_id = get_or_create_doc(name, self.folder_id)
            if doc_id:
                overwrite_doc(doc_id, content)
            console.print(f"[green]Wrote file:[/green] {name}")
            return "file_written", f"Wrote content to '{name}'"

        elif act_type == "delete_file":
            name = action.get("name", "")
            file_id = find_file_in_folder(name, self.folder_id)
            if not file_id:
                return "file_deleted", f"File '{name}' not found in workspace."
            delete_file_by_id(file_id)
            console.print(f"[red]Deleted file:[/red] {name}")
            return "file_deleted", f"Deleted '{name}' from workspace"

        elif act_type == "run_code":
            code = action.get("code", "")
            if not code:
                return "code_result", "No code provided."
            console.print("[yellow]Executing code...[/yellow]")
            stdout, stderr, returncode = run_code(code)
            parts = []
            if stdout:
                parts.append(f"stdout:\n{stdout.rstrip()}")
            if stderr:
                parts.append(f"stderr:\n{stderr.rstrip()}")
            if returncode != 0:
                parts.append(f"Exit code: {returncode}")
            output = "\n".join(parts).strip() or "(no output)"
            console.print(f"[cyan]Code result:[/cyan]\n{output}")
            return "code_result", output

        return act_type, action.get("thought", "")

    def _wait_for_manager(self, doc_id):
        while True:
            time.sleep(10)
            text = read_doc_text(doc_id)
            if not text:
                continue
            parts = text.split("[AI]:")
            if len(parts) > 1:
                last_ai_msg_and_after = parts[-1]
                lines = last_ai_msg_and_after.split("\n")
                manager_reply = "\n".join(lines[1:]).strip()
                if len(manager_reply) > 5:
                    console.print(
                        f"[green]Received response from manager:[/green] {manager_reply}"
                    )
                    if "[Manager]:" in manager_reply:
                        return manager_reply.split("[Manager]:")[-1].strip()
                    return manager_reply
