from contextlib import asynccontextmanager
import traceback
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .api.router import router
from .api.pipeline_router import router as pipeline_router
from .api.websocket import job_progress_ws
from .services.job_service import job_service
from .services.cleanup_service import cleanup_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    job_service.start()
    cleanup_service.start()
    yield
    # Shutdown
    await job_service.stop()
    await cleanup_service.stop()


app = FastAPI(
    title="Watermark Remover API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

app.include_router(router)
app.include_router(pipeline_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"\n{'='*60}\nUNHANDLED ERROR: {request.url}\n{tb}{'='*60}\n", flush=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.websocket("/api/ws/jobs/{job_id}")
async def ws_job_progress(websocket: WebSocket, job_id: str):
    await job_progress_ws(websocket, job_id)
