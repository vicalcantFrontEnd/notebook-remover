import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from ..config import settings


class UploadService:
    def __init__(self):
        self._files: dict[str, dict] = {}  # file_id -> {path, filename, uploaded_at}
        self._recover_from_disk()

    def _recover_from_disk(self):
        """Scan upload directory to recover file records after a restart/reload."""
        upload_root = settings.upload_dir
        if not upload_root.exists():
            return
        for subdir in upload_root.iterdir():
            if not subdir.is_dir():
                continue
            file_id = subdir.name
            if file_id in self._files:
                continue
            # Find the first video file in the subdir
            for f in subdir.iterdir():
                if f.is_file() and f.suffix.lower() in settings.allowed_extensions:
                    from datetime import datetime
                    self._files[file_id] = {
                        "path": str(f),
                        "filename": f.name,
                        "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime),
                    }
                    break

    async def save_upload(self, file: UploadFile) -> dict:
        """Save uploaded file and return file_id + metadata."""
        if not file.filename:
            raise HTTPException(400, "No filename provided")

        ext = Path(file.filename).suffix.lower()
        if ext not in settings.allowed_extensions:
            raise HTTPException(400, f"Unsupported format: {ext}. Allowed: {settings.allowed_extensions}")

        file_id = uuid.uuid4().hex[:12]
        upload_dir = settings.upload_dir / file_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename

        # Stream to disk (with optional size limit)
        total_size = 0
        max_bytes = settings.max_upload_size_mb * 1024 * 1024 if settings.max_upload_size_mb > 0 else 0
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_size += len(chunk)
                if max_bytes and total_size > max_bytes:
                    f.close()
                    shutil.rmtree(upload_dir)
                    raise HTTPException(413, f"File exceeds {settings.max_upload_size_mb}MB limit")
                f.write(chunk)

        from datetime import datetime
        self._files[file_id] = {
            "path": str(file_path),
            "filename": file.filename,
            "uploaded_at": datetime.now(),
        }

        return {"file_id": file_id, "filename": file.filename, "size": total_size}

    def get_file_path(self, file_id: str) -> str:
        """Get the file path for a file_id, raise 404 if not found."""
        info = self._files.get(file_id)
        if info and Path(info["path"]).exists():
            return info["path"]

        # Try to recover from disk if not in memory
        subdir = settings.upload_dir / file_id
        if subdir.is_dir():
            for f in subdir.iterdir():
                if f.is_file() and f.suffix.lower() in settings.allowed_extensions:
                    from datetime import datetime
                    self._files[file_id] = {
                        "path": str(f),
                        "filename": f.name,
                        "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime),
                    }
                    return str(f)

        raise HTTPException(404, f"File {file_id} not found")

    def get_filename(self, file_id: str) -> str:
        info = self._files.get(file_id)
        if info:
            return info["filename"]
        # Try disk recovery
        try:
            self.get_file_path(file_id)
            info = self._files.get(file_id)
            return info["filename"] if info else "unknown"
        except HTTPException:
            return "unknown"

    def cleanup_file(self, file_id: str):
        info = self._files.pop(file_id, None)
        if info:
            parent = Path(info["path"]).parent
            if parent.exists():
                shutil.rmtree(parent, ignore_errors=True)

upload_service = UploadService()
