"""
drive_bot_tools — Google API helpers available inside agent code execution.

Import this module in your run_code snippets:

    import drive_bot_tools as tools

    # Search the web
    results = tools.search("latest AI research")

    # Work with Drive files
    tools.write_file("report.txt", "My findings...")
    content = tools.read_file("report.txt")
    tools.append_to_file("report.txt", "\\nMore findings...")
    tools.replace_in_file("report.txt", "old text", "new text")
    files = tools.list_files()
    all_files = tools.list_all_files()  # recursive
    tools.create_folder("Sub Folder")
    tools.move_file("report.txt", target_folder_id)
    tools.copy_file("report.txt", "report-backup.txt")
    tools.rename_file("report.txt", "final-report.txt")
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


def _folder_id() -> str:
    return _config()["folder_id"]


# ─── Custom Search ────────────────────────────────────────────────────────────


def search(query: str, num: int = 10) -> list[dict]:
    """Search the web using Google Custom Search.

    Returns a list of dicts with keys: title, link, snippet.
    """
    cfg = _config()
    api_key = cfg.get("search_api_key")
    cx = cfg.get("search_cx")
    if not api_key or not cx:
        raise RuntimeError("Custom Search is not configured.")
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
    """List top-level files in the workspace. Returns [{id, name, mimeType}]."""
    from google_auth_doc import list_files_in_folder

    return list_files_in_folder(_folder_id())


def list_all_files() -> list[dict]:
    """Recursively list every file/subfolder with full paths.

    Returns [{id, name, mimeType, path}].
    """
    from google_auth_doc import list_files_recursive

    return list_files_recursive(_folder_id())


def list_folder(folder_id: str) -> list[dict]:
    """List direct children of a specific folder by ID."""
    from google_auth_doc import list_files_in_folder

    return list_files_in_folder(folder_id)


def read_file(name: str) -> str:
    """Read the text content of a named file from the workspace."""
    from google_auth_doc import find_file_in_folder, read_doc_text

    file_id = find_file_in_folder(name, _folder_id())
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    return read_doc_text(file_id) or ""


def write_file(name: str, content: str):
    """Create or overwrite a file in the workspace."""
    from google_auth_doc import get_or_create_doc, overwrite_doc

    doc_id = get_or_create_doc(name, _folder_id())
    if not doc_id:
        raise RuntimeError(f"Failed to create or find '{name}'.")
    overwrite_doc(doc_id, content)


def append_to_file(name: str, text: str):
    """Append text to the end of an existing file."""
    from google_auth_doc import find_file_in_folder, append_to_doc

    file_id = find_file_in_folder(name, _folder_id())
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    append_to_doc(file_id, text)


def replace_in_file(name: str, old: str, new: str) -> int:
    """Replace all occurrences of *old* with *new* in a file. Returns count."""
    from google_auth_doc import find_file_in_folder, read_doc_text, overwrite_doc

    file_id = find_file_in_folder(name, _folder_id())
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    content = read_doc_text(file_id) or ""
    count = content.count(old)
    if count:
        overwrite_doc(file_id, content.replace(old, new))
    return count


def delete_file(name: str):
    """Permanently delete a named file from the workspace."""
    from google_auth_doc import find_file_in_folder, delete_file_by_id

    file_id = find_file_in_folder(name, _folder_id())
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    delete_file_by_id(file_id)


def create_folder(name: str, parent_folder_id: str = "") -> str:
    """Create a subfolder. Returns the new folder ID."""
    from google_auth_doc import create_folder_in_folder

    parent = parent_folder_id or _folder_id()
    fid = create_folder_in_folder(name, parent)
    if not fid:
        raise RuntimeError(f"Failed to create folder '{name}'.")
    return fid


def move_file(name: str, target_folder_id: str):
    """Move a file to a different folder."""
    from google_auth_doc import find_file_in_folder, move_file_to_folder

    file_id = find_file_in_folder(name, _folder_id())
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    if not move_file_to_folder(file_id, target_folder_id):
        raise RuntimeError(f"Failed to move '{name}'.")


def copy_file(name: str, new_name: str, target_folder_id: str = "") -> str:
    """Copy a file. Returns the new file ID."""
    from google_auth_doc import find_file_in_folder, copy_file_by_id

    file_id = find_file_in_folder(name, _folder_id())
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    parent = target_folder_id or _folder_id()
    new_id = copy_file_by_id(file_id, new_name, parent)
    if not new_id:
        raise RuntimeError(f"Failed to copy '{name}'.")
    return new_id


def rename_file(name: str, new_name: str):
    """Rename a file in the workspace."""
    from google_auth_doc import find_file_in_folder, rename_file_by_id

    file_id = find_file_in_folder(name, _folder_id())
    if not file_id:
        raise FileNotFoundError(f"'{name}' not found in workspace.")
    if not rename_file_by_id(file_id, new_name):
        raise RuntimeError(f"Failed to rename '{name}'.")
