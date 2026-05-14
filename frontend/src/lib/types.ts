export interface Region {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type FileType = "video" | "image" | "pdf" | "pptx";

export type RemovalMethod = "pixel" | "box" | "crop" | "delete_shapes" | "lama";

export interface VideoInfo {
  file_id: string;
  filename: string;
  width: number;
  height: number;
  fps: number;
  duration: number;
  total_frames: number;
  has_audio: boolean;
  first_frame_base64: string;
}

export interface FileInfo {
  file_id: string;
  filename: string;
  file_type: FileType;
  width: number;
  height: number;
  fps: number;
  duration: number;
  total_frames: number;
  has_audio: boolean;
  page_count: number;
  first_frame_base64: string;
}

export type JobStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";

export interface JobInfo {
  job_id: string;
  file_id: string;
  filename: string;
  status: JobStatus;
  progress: number;
  current_frame: number;
  total_frames: number;
  eta_seconds: number | null;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  method: string;
}

export interface PreviewRequest {
  region: Region;
  method: RemovalMethod;
  sensitivity: number;
  inpaint_radius: number;
}

export interface JobCreateRequest {
  file_id: string;
  region: Region;
  method: RemovalMethod;
  sensitivity: number;
  inpaint_radius: number;
  trim_end_seconds: number;
  file_type: FileType;
}

export interface ProgressMessage {
  type: "progress" | "status" | "done" | "error";
  job_id: string;
  status?: string;
  progress?: number;
  current_frame?: number;
  total_frames?: number;
  eta_seconds?: number | null;
  error?: string | null;
  message?: string;
}
