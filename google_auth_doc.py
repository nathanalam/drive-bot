import os
import json
import shutil
from typing import Any, Optional, Tuple, Dict, List
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "service_account.json")
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def save_service_account(source_path: str) -> Tuple[Optional[str], Optional[str]]:
    # Validates and saves locally
    try:
        with open(source_path, "r") as f:
            data = json.load(f)
        if "client_email" not in data or "private_key" not in data:
            return None, "Invalid Service Account JSON."
        shutil.copyfile(source_path, CREDENTIALS_PATH)
        return data["client_email"], None
    except Exception as e:
        return None, str(e)


def get_credentials() -> Optional[Credentials]:
    if not os.path.exists(CREDENTIALS_PATH):
        return None
    return Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)


def get_docs_service():
    creds = get_credentials()
    if not creds:
        return None
    return build("docs", "v1", credentials=creds)


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
            if "paragraph" in last_element:
                end_index = last_element["endIndex"] - 1
            elif "table" in last_element:
                end_index = last_element["endIndex"] - 1
            else:
                end_index = last_element["endIndex"] - 1

        requests = [
            {
                "insertText": {
                    "location": {
                        "index": end_index,
                    },
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
