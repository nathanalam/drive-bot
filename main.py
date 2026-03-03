import os
import time
from rich.console import Console
from rich.prompt import Prompt, Confirm

from ollama_client import check_ollama, list_models
from google_auth_doc import (
    save_client_secrets,
    run_auth_flow,
    get_or_create_doc,
    verify_folder_access,
)
from agent import AIAgent, load_config, save_config

console = Console()


def setup():
    console.print("[bold green]Welcome to AI Chief of Staff setup![/bold green]")
    config = load_config()

    # 1. Ollama
    if not check_ollama():
        console.print(
            "[red]Ollama is not running. Please start Ollama before continuing.[/red]"
        )
        return False

    models = list_models()
    if not models:
        console.print(
            "[red]No models found in Ollama. Please pull a model (e.g., 'ollama pull llama3').[/red]"
        )
        return False

    console.print(f"Found running Ollama models: {', '.join(models)}")
    config["model"] = Prompt.ask(
        "Which model would you like to use?",
        choices=models,
        default=models[0],
    )

    # 2. OAuth2 credentials
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

    # 3. Drive Folder (workspace)
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

    # 4. Create Manager Chat doc inside the workspace folder
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

    # 5. Custom Search (optional)
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
    if not config.get("model"):
        if not setup():
            return

    agent = AIAgent()
    console.print(
        f"[bold blue]Starting agent loop with model {config['model']}...[/bold blue]\n"
        "Press Ctrl+C to stop."
    )

    input_text = None
    input_source = "manager"
    try:
        while True:
            console.print("\n[blue]... Agent Iteration ...[/blue]")
            action, result = agent.run_step(input_text, input_source)
            input_text = None
            input_source = "result"
            if action == "manager_replied":
                input_text = result
                input_source = "manager"
            elif action in ("files_listed", "file_read", "code_result", "think"):
                input_text = result
            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[bold red]Agent loop stopped by manager.[/bold red]")


def main():
    config = load_config()
    if not config.get("model"):
        setup()
    run_loop()


if __name__ == "__main__":
    main()
