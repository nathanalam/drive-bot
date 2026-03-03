import os
import time
from rich.console import Console
from rich.prompt import Prompt, Confirm

from ollama_client import check_ollama, list_models
from google_auth_doc import save_service_account
from agent import AIAgent, StateManager

console = Console()


def setup():
    console.print("[bold green]Welcome to AI Chief of Staff setup![/bold green]")
    state = StateManager()
    config = state.get_config()

    # 1. Ollama Setup
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
    selected_model = Prompt.ask(
        "Which model would you like to use?",
        choices=models,
        default=models[0] if models else "",
    )
    config["model"] = selected_model

    # 2. Google Service Account Setup
    use_google = Confirm.ask(
        "Do you want to set up Google Docs integration for manager communication?"
    )
    if use_google:
        sa_path = Prompt.ask(
            "Enter the absolute path to your Google Service Account JSON file"
        )
        if not os.path.exists(sa_path):
            console.print("[red]File not found.[/red]")
            return False

        email, error = save_service_account(sa_path)
        if error:
            console.print(f"[red]Error saving service account:[/red] {error}")
            return False

        console.print(
            f"[green]Service Account configured successfully![/green] Email: [bold]{email}[/bold]"
        )
        console.print(
            "Please create a new Google Doc and share it with this email address with 'Editor' permissions."
        )
        doc_id = Prompt.ask(
            "Enter the Google Document ID (found in the URL: https://docs.google.com/document/d/DOC_ID/edit)"
        )
        config["doc_id"] = doc_id
    else:
        config["doc_id"] = None

    state.save_config(config)
    console.print("[bold green]Setup Complete![/bold green]")
    return True


def run_loop():
    state = StateManager()
    config = state.get_config()
    if "model" not in config:
        if not setup():
            return

    agent = AIAgent()
    console.print(
        f"[bold blue]Starting agent loop with model {config['model']}...[/bold blue]\nPress Ctrl+C to stop."
    )

    input_text = None
    try:
        while True:
            console.print("\n[blue]... Agent Iteration ...[/blue]")
            action, result = agent.run_step(input_text)
            input_text = None
            if action == "manager_replied":
                input_text = result
                console.print(
                    f"[magenta]Manager input ready to process: {input_text}[/magenta]"
                )

            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[bold red]Agent loop stopped by manager.[/bold red]")


def main():
    state = StateManager()
    config = state.get_config()
    if not config.get("model"):
        setup()
    run_loop()


if __name__ == "__main__":
    main()
