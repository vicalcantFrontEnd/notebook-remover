from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    # ---- Existing settings (unchanged) ----
    upload_dir: Path = Path("temp/uploads")
    output_dir: Path = Path("temp/outputs")
    max_upload_size_mb: int = 0          # 0 = no limit
    allowed_extensions: list[str] = [
        ".mp4", ".mkv", ".avi", ".mov", ".webm",
        ".jpg", ".jpeg", ".png", ".webp",
        ".pdf",
        ".pptx",
        ".m4a", ".mp3", ".aac",          # audio
    ]
    cors_origins: list[str] = ["http://localhost:3000"]
    cleanup_max_age_hours: int = 2
    max_concurrent_jobs: int = 1

    # ---- Google Drive ----
    # Path to the service account JSON credentials file
    google_credentials_path: str = "/app/credentials/google_credentials.json"
    # Root folder ID of "Cursos prácticos memb..." in Drive
    drive_root_folder_id: Optional[str] = None

    # ---- Bunny CDN ----
    bunny_api_key: str = ""
    bunny_storage_zone: str = ""
    # Storage API hostname (e.g. "storage.bunnycdn.com" or "la.storage.bunnycdn.com")
    bunny_storage_hostname: str = "storage.bunnycdn.com"
    # Pull zone hostname (e.g. "mi-cdn.b-cdn.net")
    bunny_pull_zone_hostname: str = ""

    # ---- Pipeline defaults ----
    pipeline_video_method: str = "pixel"    # pixel | box | crop
    pipeline_image_method: str = "pixel"    # pixel | box
    pipeline_pdf_method: str = "box"        # pixel | box
    pipeline_sensitivity: int = 30          # 5–80
    pipeline_inpaint_radius: int = 3        # 1–15
    pipeline_trim_end_seconds: float = 0.0  # trim video end
    # Seconds to trim from the END of audio files (removes spoken watermark)
    audio_trim_end_seconds: float = 0.0

    model_config = {"env_prefix": "WMR_"}


settings = Settings()
