import json
import os
import time
from ollama_client import chat
from google_auth_doc import append_to_doc, read_doc_text
from rich.console import Console
from rich.panel import Panel

console = Console()


class StateManager:
    def __init__(self, data_dir="."):
        self.todo_file = os.path.join(data_dir, "todo.json")
        self.memories_file = os.path.join(data_dir, "memories.json")
        self.skills_file = os.path.join(data_dir, "skills.json")
        self.config_file = os.path.join(data_dir, "config.json")
        self.ensure_files()

    def ensure_files(self):
        for f, default in [
            (self.todo_file, []),
            (self.memories_file, {}),
            (self.skills_file, {}),
            (self.config_file, {}),
        ]:
            if not os.path.exists(f):
                with open(f, "w") as fh:
                    json.dump(default, fh)

    def load(self, f):
        with open(f, "r") as fh:
            return json.load(fh)

    def save(self, f, data):
        with open(f, "w") as fh:
            json.dump(data, fh, indent=2)

    def get_config(self):
        return self.load(self.config_file)

    def save_config(self, cfg):
        self.save(self.config_file, cfg)

    def get_todos(self):
        return self.load(self.todo_file)

    def save_todos(self, t):
        self.save(self.todo_file, t)

    def get_memories(self):
        return self.load(self.memories_file)

    def save_memories(self, m):
        self.save(self.memories_file, m)

    def get_skills(self):
        return self.load(self.skills_file)

    def save_skills(self, s):
        self.save(self.skills_file, s)


class AIAgent:
    def __init__(self):
        self.state = StateManager()
        self.config = self.state.get_config()

    def system_prompt(self):
        return f"""You are an AI Chief of Staff. You continuously run in a loop, process tasks, manage memories, and ask your manager for tasks if needed.
You have the following skills: {json.dumps(self.state.get_skills())}
Your current memories: {json.dumps(self.state.get_memories())}
Your current tasks: {json.dumps(self.state.get_todos())}

You must respond with ONLY a JSON object representing your action. Valid actions:
1. {{"action": "think", "thought": "your thoughts"}}
2. {{"action": "add_memory", "key": "memory_key", "value": "memory_value"}}
3. {{"action": "update_skill", "skill": "skill_name", "details": "skill_details"}}
4. {{"action": "add_task", "task": "description"}}
5. {{"action": "complete_task", "task_index": 0, "result": "result summary"}}
6. {{"action": "ask_manager", "question": "what to do next?"}}
"""

    def parse_response(self, text):
        # find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
        return None

    def run_step(self, doc_input=None):
        model = self.config.get("model")
        doc_id = self.config.get("doc_id")

        messages = [{"role": "system", "content": self.system_prompt()}]
        if doc_input:
            messages.append(
                {"role": "user", "content": f"Message from manager: {doc_input}"}
            )
        else:
            todos = self.state.get_todos()
            if not todos:
                messages.append(
                    {
                        "role": "user",
                        "content": "You have no tasks in your To-Do list. You should ask your manager for tasks.",
                    }
                )
            else:
                messages.append(
                    {"role": "user", "content": "What is your next action?"}
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
                if doc_id:
                    msg = f"\n[AI]: Completed task: {task['desc']}\nResult: {action.get('result', '')}\n"
                    append_to_doc(doc_id, msg)
                return "task_completed", task["desc"]

        elif act_type == "ask_manager":
            q = action.get("question", "What should I do next?")
            if doc_id:
                msg = f"\n[AI]: {q}\n"
                append_to_doc(doc_id, msg)
                console.print(
                    "[yellow]Asked manager via Google Doc. Waiting for response...[/yellow]"
                )
                self._wait_for_manager(doc_id)
            else:
                ans = console.input(f"[yellow]Agent asks: {q}[/yellow]\nYour reply: ")
                return "manager_replied", ans

        return act_type, action.get("thought", "")

    def _wait_for_manager(self, doc_id):
        # A simple polling mechanism. Checks the doc every 10 seconds for a response after [AI] marker.
        while True:
            time.sleep(10)
            text = read_doc_text(doc_id)
            if not text:
                continue
            # Logic: look for text after the last [AI]: snippet
            parts = text.split("[AI]:")
            if len(parts) > 1:
                last_ai_msg_and_after = parts[-1]
                # If manager replied, there should be some meaningful text after the AI's question
                lines = last_ai_msg_and_after.split("\n")
                manager_reply = "\n".join(
                    lines[1:]
                ).strip()  # Skip the first line which is AI's question
                if len(manager_reply) > 5:
                    console.print(
                        f"[green]Received response from manager:[/green] {manager_reply}"
                    )
                    # Clear the doc to avoid re-reading the same reply?
                    # For simplicity, we just return it and let the AI process it.
                    # A better way is to append a unique marker like [Manager]:
                    if "[Manager]:" in manager_reply:
                        return manager_reply.split("[Manager]:")[-1].strip()
                    return manager_reply
