"""
drive_bot_tools — Google API helpers available inside agent code execution.

Import this module in your run_code snippets:

    import drive_bot_tools as tools

    # Search the web
    results = tools.search("latest AI research")
    for r in results:
        print(r["title"])
        print(r["link"])
        print(r["snippet"])
        print()

    # Work with Drive files
    tools.write_file("report.txt", "My findings...")
    content = tools.read_file("report.txt")
    files = tools.list_files()
    tools.delete_file("old-draft.txt")
"""

import json
import os

from googleapiclient.discovery import build

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_CONFIG_PATH = os.path.join(_BASE_DIR, "config.json")


def _config() -> dict:
    with open(_CONFIG_PATH) as f:
        return json.load(f)


# ─── Custom Search ────────────────────────────────────────────────────────────


def search(query: str, num: int = 10) -> list[dict]:
    """
    Search the web using Google Custom Search.

    Returns a list of dicts with keys: title, link, snippet.
    Raises RuntimeError if Custom Search is not configured.
    """
    cfg = _config()
    api_key = cfg.get("search_api_key")
    cx = cfg.get("search_cx")
    if not api_key or not cx:
        raise RuntimeError(
            "Custom Search is not configured. Re-run setup and provide an API key and Search Engine ID."
        )
    service = build("customsearch", "v1", developerKey=api_key)
    result = service.cse().list(q=query, cx=cx, num=min(num, 10)).execute()
    return [
        {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        }
        for item in result.get("items", [])
    ]


# ─── Drive / Docs ─────────────────────────────────────────────────────────────


def list_files() -> list[dict]:
    """
    List all files in the Drive workspace folder.

    Returns a list of dicts with keys: id, name, mimeType.
    """
    from google_auth_doc import list_files_in_folder

    cfg = _config()
    return list_files_in_folder(cfg["folder_id"])


def read_file(name: str) -> str:
    """
    Read the text content of a named file from the Drive workspace.

    Raises FileNotFoundError if the file does not exist.
    """
    from google_auth_doc import find_file_in_folder, read_doc_text

    cfg = _config()
    file_id = find_file_in_folder(name, cfg["folder_id"])
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    return read_doc_text(file_id) or ""


def write_file(name: str, content: str):
    """
    Write (overwrite) content to a named file in the Drive workspace.
    Creates the file if it does not exist.
    """
    from google_auth_doc import get_or_create_doc, overwrite_doc

    cfg = _config()
    doc_id = get_or_create_doc(name, cfg["folder_id"])
    if not doc_id:
        raise RuntimeError(f"Failed to create or find file '{name}'.")
    overwrite_doc(doc_id, content)


def delete_file(name: str):
    """
    Permanently delete a named file from the Drive workspace.

    Raises FileNotFoundError if the file does not exist.
    """
    from google_auth_doc import find_file_in_folder, delete_file_by_id

    cfg = _config()
    file_id = find_file_in_folder(name, cfg["folder_id"])
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    delete_file_by_id(file_id)
