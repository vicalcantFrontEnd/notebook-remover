import asyncio
import shutil
import time
from pathlib import Path
from ..config import settings


class CleanupService:
    def __init__(self):
        self._task: asyncio.Task | None = None

    def start(self):
        self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        """Periodically clean up old temp files."""
        while True:
            await asyncio.sleep(600)  # Check every 10 minutes
            self._clean_directory(settings.upload_dir)
            self._clean_directory(settings.output_dir)

    def _clean_directory(self, base_dir: Path):
        if not base_dir.exists():
            return
        max_age = settings.cleanup_max_age_hours * 3600
        now = time.time()
        for child in base_dir.iterdir():
            if child.is_dir():
                try:
                    age = now - child.stat().st_mtime
                    if age > max_age:
                        shutil.rmtree(child, ignore_errors=True)
                except Exception:
                    pass

cleanup_service = CleanupService()
