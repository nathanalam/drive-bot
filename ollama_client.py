import requests

OLLAMA_BASE_URL = "http://localhost:11434/api"


def check_ollama() -> bool:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/tags", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def list_models() -> list[str]:
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/tags", timeout=5)
        response.raise_for_status()
        data = response.json()
        return [model["name"] for model in data.get("models", [])]
    except Exception as e:
        print(f"Error fetching Ollama models: {e}")
        return []


def chat(model: str, messages: list[dict[str, str]]) -> str:
    payload = {"model": model, "messages": messages, "stream": False, "format": "json"}
    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/chat", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["message"]["content"]
    except Exception as e:
        print(f"Error communicating with Ollama: {e}")
        return ""
