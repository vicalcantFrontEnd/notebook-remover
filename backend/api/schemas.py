from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class FileType(str, Enum):
    video = "video"
    image = "image"
    pdf = "pdf"
    pptx = "pptx"


class RemovalMethod(str, Enum):
    pixel = "pixel"
    box = "box"
    crop = "crop"
    delete_shapes = "delete_shapes"
    lama = "lama"


class VideoInfo(BaseModel):
    file_id: str
    filename: str
    width: int
    height: int
    fps: float
    duration: float
    total_frames: int
    has_audio: bool
    first_frame_base64: str = ""


class FileInfo(BaseModel):
    file_id: str
    filename: str
    file_type: FileType
    width: int
    height: int
    fps: float = 0.0
    duration: float = 0.0
    total_frames: int = 0
    has_audio: bool = False
    page_count: int = 0
    first_frame_base64: str = ""


class Region(BaseModel):
    x: int
    y: int
    w: int
    h: int


class DetectRequest(BaseModel):
    pass  # no body needed, uses file_id from path


class DetectResponse(BaseModel):
    region: Region
    confidence: str = "auto"


class PreviewRequest(BaseModel):
    region: Region
    method: RemovalMethod = RemovalMethod.pixel
    sensitivity: int = Field(default=30, ge=5, le=80)
    inpaint_radius: int = Field(default=3, ge=1, le=15)


class PreviewResponse(BaseModel):
    preview_base64: str
    method: str


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobCreate(BaseModel):
    file_id: str
    region: Region
    method: RemovalMethod = RemovalMethod.pixel
    sensitivity: int = Field(default=30, ge=5, le=80)
    inpaint_radius: int = Field(default=3, ge=1, le=15)
    trim_end_seconds: float = Field(default=0.0, ge=0, le=30)
    file_type: FileType = FileType.video


class JobInfo(BaseModel):
    job_id: str
    file_id: str
    filename: str
    status: JobStatus
    progress: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    eta_seconds: float | None = None
    created_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    method: str = "pixel"


class JobListResponse(BaseModel):
    jobs: list[JobInfo]


class ProgressMessage(BaseModel):
    type: str = "progress"
    job_id: str
    status: str
    progress: float
    current_frame: int
    total_frames: int
    eta_seconds: float | None = None
    error: str | None = None
