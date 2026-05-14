"""
Google Drive API service.
Downloads files and lists folder contents using a Service Account.
"""

import io
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from ..config import settings

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# MIME type for Google Drive folders
_FOLDER_MIME = "application/vnd.google-apps.folder"

# Extensions we care about in Drive
_TARGET_EXTENSIONS = {".mp4", ".m4a", ".png", ".pdf"}


def _get_service():
    """Build an authenticated Drive v3 service."""
    creds = service_account.Credentials.from_service_account_file(
        settings.google_credentials_path,
        scopes=_SCOPES,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_folder(folder_id: str) -> list[dict]:
    """
    List all items (files + subfolders) in a Drive folder.
    Returns list of {id, name, mimeType, size}.
    """
    service = _get_service()
    results = []
    page_token: Optional[str] = None

    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageToken=page_token,
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        results.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return results


def list_subfolders(folder_id: str) -> list[dict]:
    """Return only subfolders of a given folder."""
    items = list_folder(folder_id)
    return [i for i in items if i["mimeType"] == _FOLDER_MIME]


def list_target_files(folder_id: str) -> list[dict]:
    """Return only files with supported extensions in a folder."""
    items = list_folder(folder_id)
    files = []
    for item in items:
        if item["mimeType"] == _FOLDER_MIME:
            continue
        name = item.get("name", "")
        if Path(name).suffix.lower() in _TARGET_EXTENSIONS:
            files.append(item)
    return files


def scan_drive_tree(root_folder_id: str) -> list[dict]:
    """
    Traverse 3-level Drive hierarchy:
        root_folder / Categoria / Tema / files

    Returns a flat list of file records:
        {
            drive_file_id, filename, categoria_id, categoria_name,
            tema_id, tema_name, size
        }
    """
    records = []

    categorias = list_subfolders(root_folder_id)
    for cat in categorias:
        temas = list_subfolders(cat["id"])
        for tema in temas:
            files = list_target_files(tema["id"])
            for f in files:
                records.append({
                    "drive_file_id": f["id"],
                    "filename": f["name"],
                    "categoria_id": cat["id"],
                    "categoria_name": cat["name"],
                    "tema_id": tema["id"],
                    "tema_name": tema["name"],
                    "size": int(f.get("size", 0)),
                })

    return records


def download_file(file_id: str) -> bytes:
    """
    Download a file from Google Drive by its ID.
    Returns raw bytes.
    """
    service = _get_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request, chunksize=8 * 1024 * 1024)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()
