import os
import time
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from google_auth_doc import (
    save_client_secrets,
    run_auth_flow,
    get_or_create_doc,
    verify_folder_access,
)
from agent import AgentDeps, create_agent, load_config, save_config

console = Console()

DEFAULT_MODEL = "google/gemini-2.0-flash-001"


def setup():
    console.print("[bold green]Welcome to AI Chief of Staff setup![/bold green]")
    config = load_config()

    # 1. OpenRouter API key
    console.print(
        "\nGet an API key from [bold]https://openrouter.ai/keys[/bold]"
    )
    api_key = Prompt.ask("Enter your OpenRouter API key")
    if not api_key.strip():
        console.print("[red]API key cannot be empty.[/red]")
        return False
    config["openrouter_api_key"] = api_key.strip()

    # 2. Model name
    config["model"] = Prompt.ask(
        "Enter the OpenRouter model to use",
        default=DEFAULT_MODEL,
    )

    # 3. OAuth2 credentials
    console.print(
        "\nIn Google Cloud Console → APIs & Services → Credentials, "
        "create an [bold]OAuth 2.0 Client ID[/bold] of type [bold]Desktop app[/bold] "
        "and download the JSON file."
    )
    creds_path = Prompt.ask(
        "Enter the absolute path to your OAuth2 credentials JSON file"
    )
    if not os.path.exists(creds_path):
        console.print("[red]File not found.[/red]")
        return False

    error = save_client_secrets(creds_path)
    if error:
        console.print(f"[red]{error}[/red]")
        return False

    console.print("Opening browser for Google authorization...")
    if not run_auth_flow():
        console.print("[red]Authorization failed.[/red]")
        return False

    console.print("[green]Authorization successful![/green]")

    # 4. Drive Folder (workspace)
    console.print(
        "\nCreate a Google Drive folder to use as the agent's workspace. "
        "The folder ID is the last segment of its URL:\n"
        "  https://drive.google.com/drive/folders/[bold]FOLDER_ID[/bold]"
    )
    folder_id = Prompt.ask("Enter the Google Drive Folder ID")

    if not verify_folder_access(folder_id):
        console.print(
            "[red]Could not access that folder. "
            "Check the ID and confirm it is shared with the service account email.[/red]"
        )
        return False

    config["folder_id"] = folder_id
    console.print("[green]Folder access confirmed.[/green]")

    # 5. Create Manager Chat doc inside the workspace folder
    console.print("Creating [bold]Manager Chat[/bold] document in workspace...")
    chat_doc_id = get_or_create_doc("Manager Chat", folder_id)
    if not chat_doc_id:
        console.print("[red]Failed to create Manager Chat document.[/red]")
        return False

    config["chat_doc_id"] = chat_doc_id
    console.print(
        "[green]Manager Chat document ready.[/green] "
        "Open it in Google Drive to communicate with the agent."
    )

    # 6. Custom Search (optional)
    if Confirm.ask("\nDo you want to set up Google Custom Search?"):
        console.print(
            "You will need:\n"
            "  1. [bold]Custom Search API[/bold] enabled in your Google Cloud project.\n"
            "  2. A [bold]Programmable Search Engine[/bold] created at "
            "https://programmablesearchengine.google.com/ — copy its Search Engine ID.\n"
            "  3. An [bold]API key[/bold] from Google Cloud Console → APIs & Services → Credentials."
        )
        config["search_api_key"] = Prompt.ask("Enter your Google API key")
        config["search_cx"] = Prompt.ask("Enter your Programmable Search Engine ID")
        console.print("[green]Custom Search configured.[/green]")
    else:
        config.setdefault("search_api_key", None)
        config.setdefault("search_cx", None)

    save_config(config)
    console.print("[bold green]Setup Complete![/bold green]")
    return True


def run_loop():
    config = load_config()
    if not config.get("model") or not config.get("openrouter_api_key"):
        if not setup():
            return

    config = load_config()
    model_name = config["model"]
    api_key = config["openrouter_api_key"]

    deps = AgentDeps(
        folder_id=config["folder_id"],
        chat_doc_id=config.get("chat_doc_id"),
        search_api_key=config.get("search_api_key"),
        search_cx=config.get("search_cx"),
    )

    agent = create_agent(model_name, api_key)

    console.print(
        f"[bold blue]Starting agent with model {model_name}...[/bold blue]\n"
        "The agent will use tools autonomously. Press Ctrl+C to stop."
    )

    tick_interval = 10  # seconds between iterations

    # Continuous loop — each tick checks tasks + manager chat + decides action
    try:
        while True:
            console.print("\n[blue]─── Agent Tick ───[/blue]")

            # 1. Check for a manager reply (non-blocking)
            manager_reply = deps.check_manager_chat()
            if manager_reply and deps.pending_question:
                console.print(
                    f"[green]Manager replied:[/green] {manager_reply}"
                )
                deps.pending_question = None

            # 2. Load current tasks
            todos = deps.load_state("todo", [])

            # 3. Build a context-aware prompt
            prompt_parts: list[str] = []

            if manager_reply:
                prompt_parts.append(
                    f"The manager just replied in the chat: \"{manager_reply}\". "
                    "Process this reply and act on it."
                )

            if todos:
                prompt_parts.append(
                    "You have pending tasks. Review them and take your next action. "
                    "Work through tasks one at a time."
                )

            if deps.pending_question:
                prompt_parts.append(
                    f"You have an outstanding question to the manager: "
                    f"\"{deps.pending_question}\". No reply yet — continue "
                    "working on any other tasks in the meantime."
                )

            if not prompt_parts:
                # Nothing to do and no pending question — ask manager for work
                prompt_parts.append(
                    "Your task list is empty and there are no pending manager "
                    "messages. Use ask_manager to check in and request new work."
                )

            prompt = " ".join(prompt_parts)

            result = agent.run_sync(prompt, deps=deps)

            console.print(
                Panel(
                    result.output,
                    title="Agent Response",
                    border_style="green",
                )
            )

            time.sleep(tick_interval)

    except KeyboardInterrupt:
        console.print("\n[bold red]Agent loop stopped by manager.[/bold red]")



def main():
    config = load_config()
    if not config.get("model") or not config.get("openrouter_api_key"):
        if not setup():
            return
    run_loop()


if __name__ == "__main__":
    main()
