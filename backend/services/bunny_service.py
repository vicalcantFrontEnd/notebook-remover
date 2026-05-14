"""
Bunny CDN Edge Storage API client.

Storage API endpoint:
  PUT https://{storage_hostname}/{storage_zone}/{path}
  Header: AccessKey: {api_key}

Pull Zone CDN URL:
  https://{pull_zone_hostname}/{path}
"""

import httpx
from ..config import settings


def upload_file(content: bytes, cdn_path: str, filename: str) -> str:
    """
    Upload a file to Bunny CDN Edge Storage.

    Args:
        content:   Raw file bytes.
        cdn_path:  Path inside the storage zone (e.g. "Categoria1/Tema2").
        filename:  Destination filename (e.g. "video_clean.mp4").

    Returns:
        Public CDN URL for the uploaded file.
    """
    storage_hostname = settings.bunny_storage_hostname  # e.g. "storage.bunnycdn.com"
    storage_zone = settings.bunny_storage_zone           # e.g. "mi-zona"
    api_key = settings.bunny_api_key
    pull_zone = settings.bunny_pull_zone_hostname        # e.g. "mi-cdn.b-cdn.net"

    # Build the full storage path: /storage_zone/cdn_path/filename
    object_path = f"/{storage_zone}/{cdn_path}/{filename}"
    url = f"https://{storage_hostname}{object_path}"

    headers = {
        "AccessKey": api_key,
        "Content-Type": "application/octet-stream",
    }

    # Use a long timeout for large video files
    with httpx.Client(timeout=600.0) as client:
        response = client.put(url, content=content, headers=headers)
        response.raise_for_status()

    # Build public CDN URL
    cdn_url = f"https://{pull_zone}/{cdn_path}/{filename}"
    return cdn_url


def file_exists(cdn_path: str, filename: str) -> bool:
    """Check if a file already exists in the storage zone."""
    storage_hostname = settings.bunny_storage_hostname
    storage_zone = settings.bunny_storage_zone
    api_key = settings.bunny_api_key

    object_path = f"/{storage_zone}/{cdn_path}/{filename}"
    url = f"https://{storage_hostname}{object_path}"

    headers = {"AccessKey": api_key}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.head(url, headers=headers)
            return response.status_code == 200
    except Exception:
        return False
