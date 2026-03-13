import os
import json
import shutil
from typing import Any, Optional, Dict, List
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

CLIENT_SECRETS_PATH = os.path.join(os.path.dirname(__file__), "oauth_credentials.json")
TOKEN_PATH = os.path.join(os.path.dirname(__file__), "token.json")
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def save_client_secrets(source_path: str) -> Optional[str]:
    """Copies the OAuth2 client secrets file. Returns an error string or None."""
    try:
        with open(source_path) as f:
            data = json.load(f)
        if "installed" not in data and "web" not in data:
            return (
                "Not a valid OAuth2 credentials file. "
                "Download 'Desktop app' credentials from Google Cloud Console "
                "→ APIs & Services → Credentials."
            )
        # Skip copy if source is already the destination file
        if os.path.abspath(source_path) != os.path.abspath(CLIENT_SECRETS_PATH):
            shutil.copyfile(source_path, CLIENT_SECRETS_PATH)
        return None
    except Exception as e:
        return str(e)


def get_credentials() -> Optional[Credentials]:
    """Returns valid OAuth2 user credentials, refreshing or re-running the flow as needed."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except ValueError:
            os.remove(TOKEN_PATH)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_PATH):
                return None
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def run_auth_flow() -> bool:
    """Runs the OAuth2 browser flow. Returns True on success."""
    creds = get_credentials()
    return creds is not None and creds.valid


def get_docs_service():
    creds = get_credentials()
    if not creds:
        return None
    return build("docs", "v1", credentials=creds)


def get_drive_service():
    creds = get_credentials()
    if not creds:
        return None
    return build("drive", "v3", credentials=creds)


# ─── Drive Operations ─────────────────────────────────────────────────────────


def verify_folder_access(folder_id: str) -> bool:
    """Returns True if the authenticated user can access the folder."""
    service = get_drive_service()
    if not service:
        return False
    try:
        service.files().get(
            fileId=folder_id,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return True
    except Exception:
        return False


def list_files_in_folder(folder_id: str) -> List[Dict[str, str]]:
    """Returns [{id, name, mimeType}, ...] for all non-trashed files in folder."""
    service = get_drive_service()
    if not service:
        return []
    try:
        result = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id, name, mimeType)",
                orderBy="name",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return result.get("files", [])
    except Exception as e:
        print(f"Error listing files: {e}")
        return []


def find_file_in_folder(name: str, folder_id: str) -> Optional[str]:
    """Returns file_id of the first file with this name in folder, else None."""
    for f in list_files_in_folder(folder_id):
        if f["name"] == name:
            return f["id"]
    return None


def create_doc_in_folder(name: str, folder_id: str) -> Optional[str]:
    """Creates a new Google Doc in the folder. Returns doc_id."""
    service = get_drive_service()
    if not service:
        return None
    try:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [folder_id],
        }
        f = (
            service.files()
            .create(body=metadata, fields="id", supportsAllDrives=True)
            .execute()
        )
        return f.get("id")
    except Exception as e:
        print(f"Error creating doc '{name}': {e}")
        return None


def get_or_create_doc(name: str, folder_id: str) -> Optional[str]:
    """Gets existing doc by name in folder, or creates it. Returns doc_id."""
    existing = find_file_in_folder(name, folder_id)
    if existing:
        return existing
    return create_doc_in_folder(name, folder_id)


def delete_file_by_id(file_id: str) -> bool:
    """Permanently deletes a file from Drive by ID."""
    service = get_drive_service()
    if not service:
        return False
    try:
        service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        return True
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False


def create_folder_in_folder(name: str, parent_id: str) -> Optional[str]:
    """Creates a subfolder inside *parent_id*. Returns the new folder's ID."""
    service = get_drive_service()
    if not service:
        return None
    try:
        metadata: Dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        f = (
            service.files()
            .create(body=metadata, fields="id", supportsAllDrives=True)
            .execute()
        )
        return f.get("id")
    except Exception as e:
        print(f"Error creating folder '{name}': {e}")
        return None


def list_files_recursive(
    folder_id: str, _prefix: str = ""
) -> List[Dict[str, str]]:
    """Walk a folder tree and return every file/subfolder with a ``path`` key.

    Each entry has keys: ``id``, ``name``, ``mimeType``, ``path``.
    """
    results: List[Dict[str, str]] = []
    for f in list_files_in_folder(folder_id):
        path = f"{_prefix}{f['name']}"
        entry = {**f, "path": path}
        results.append(entry)
        if f["mimeType"] == "application/vnd.google-apps.folder":
            results.extend(list_files_recursive(f["id"], f"{path}/"))
    return results


def move_file_to_folder(file_id: str, new_parent_id: str) -> bool:
    """Move a file to a different folder."""
    service = get_drive_service()
    if not service:
        return False
    try:
        # Get current parents to remove
        f = (
            service.files()
            .get(fileId=file_id, fields="parents", supportsAllDrives=True)
            .execute()
        )
        previous_parents = ",".join(f.get("parents", []))
        service.files().update(
            fileId=file_id,
            addParents=new_parent_id,
            removeParents=previous_parents,
            fields="id, parents",
            supportsAllDrives=True,
        ).execute()
        return True
    except Exception as e:
        print(f"Error moving file: {e}")
        return False


def copy_file_by_id(
    file_id: str, new_name: str, parent_id: str
) -> Optional[str]:
    """Copy a file into *parent_id* with a new name. Returns the copy's ID."""
    service = get_drive_service()
    if not service:
        return None
    try:
        body: Dict[str, Any] = {"name": new_name, "parents": [parent_id]}
        f = (
            service.files()
            .copy(fileId=file_id, body=body, fields="id", supportsAllDrives=True)
            .execute()
        )
        return f.get("id")
    except Exception as e:
        print(f"Error copying file: {e}")
        return None


def rename_file_by_id(file_id: str, new_name: str) -> bool:
    """Rename a file in Drive."""
    service = get_drive_service()
    if not service:
        return False
    try:
        service.files().update(
            fileId=file_id,
            body={"name": new_name},
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        return True
    except Exception as e:
        print(f"Error renaming file: {e}")
        return False


# ─── Docs Operations ──────────────────────────────────────────────────────────


def read_doc_text(doc_id: str) -> Optional[str]:
    service = get_docs_service()
    if not service:
        return None
    try:
        document = service.documents().get(documentId=doc_id).execute()
        return extract_text(document.get("body").get("content"))
    except Exception as e:
        print(f"Error reading doc: {e}")
        return None


def extract_text(elements: Optional[List[Dict[str, Any]]]) -> str:
    text = ""
    if not elements:
        return text
    for item in elements:
        if "paragraph" in item:
            for element in item.get("paragraph", {}).get("elements", []):
                if "textRun" in element:
                    text += element.get("textRun", {}).get("content", "")
        elif "table" in item:
            for row in item.get("table", {}).get("tableRows", []):
                for cell in row.get("tableCells", []):
                    text += extract_text(cell.get("content"))
        elif "tableOfContents" in item:
            text += extract_text(item.get("tableOfContents", {}).get("content"))
    return text


def overwrite_doc(doc_id: str, content: str) -> bool:
    """Replaces all content in a Google Doc with the given text."""
    service = get_docs_service()
    if not service:
        return False
    try:
        doc = service.documents().get(documentId=doc_id).execute()
        body_content = doc.get("body", {}).get("content", [])
        end_index = body_content[-1].get("endIndex", 2) if body_content else 2

        requests = []
        if end_index > 2:
            requests.append(
                {
                    "deleteContentRange": {
                        "range": {"startIndex": 1, "endIndex": end_index - 1}
                    }
                }
            )
        requests.append({"insertText": {"location": {"index": 1}, "text": content}})
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
        return True
    except Exception as e:
        print(f"Error overwriting doc: {e}")
        return False


def append_to_doc(doc_id: str, text: str) -> bool:
    service = get_docs_service()
    if not service:
        return False
    try:
        document = service.documents().get(documentId=doc_id).execute()
        body = document.get("body", {})
        content = body.get("content", [])
        end_index = 1
        if content:
            last_element = content[-1]
            end_index = last_element["endIndex"] - 1
        requests = [
            {
                "insertText": {
                    "location": {"index": end_index},
                    "text": text,
                }
            }
        ]
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
        return True
    except Exception as e:
        print(f"Error appending to doc: {e}")
        return False
