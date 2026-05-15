import type { VideoInfo, FileInfo, Region, PreviewRequest, JobCreateRequest, JobInfo } from "./types";

const BASE = "";  // Uses Next.js rewrite proxy
const BACKEND_DIRECT = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";  // Direct for large uploads (bypasses Next.js body limit)

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function uploadVideo(file: File): Promise<{ file_id: string; filename: string; size: number }> {
  const form = new FormData();
  form.append("file", file);
  // Upload directly to FastAPI backend to bypass Next.js 10MB body limit
  const res = await fetch(`${BACKEND_DIRECT}/api/upload`, { method: "POST", body: form });
  return handleResponse(res);
}

// Legacy video-only info
export async function getVideoInfo(fileId: string): Promise<VideoInfo> {
  const res = await fetch(`${BASE}/api/video/${fileId}/info`);
  return handleResponse(res);
}

// Generic file info (supports all file types)
export async function getFileInfo(fileId: string): Promise<FileInfo> {
  const res = await fetch(`${BASE}/api/file/${fileId}/info`);
  return handleResponse(res);
}

// Legacy video-only detect
export async function detectRegion(fileId: string): Promise<{ region: Region; confidence: string }> {
  const res = await fetch(`${BASE}/api/video/${fileId}/detect`, { method: "POST" });
  return handleResponse(res);
}

// Generic file detect
export async function detectFileRegion(fileId: string): Promise<{ region: Region; confidence: string }> {
  const res = await fetch(`${BASE}/api/file/${fileId}/detect`, { method: "POST" });
  return handleResponse(res);
}

// Legacy video-only preview
export async function previewRemoval(fileId: string, req: PreviewRequest): Promise<{ preview_base64: string; method: string }> {
  const res = await fetch(`${BASE}/api/video/${fileId}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse(res);
}

// Generic file preview
export async function previewFileRemoval(fileId: string, req: PreviewRequest): Promise<{ preview_base64: string; method: string }> {
  const res = await fetch(`${BASE}/api/file/${fileId}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse(res);
}

export async function createJob(req: JobCreateRequest): Promise<JobInfo> {
  const res = await fetch(`${BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return handleResponse(res);
}

export async function listJobs(): Promise<{ jobs: JobInfo[] }> {
  const res = await fetch(`${BASE}/api/jobs`);
  return handleResponse(res);
}

export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/jobs/${jobId}/cancel`, { method: "POST" });
  return handleResponse(res);
}

export function getDownloadUrl(jobId: string): string {
  return `${BACKEND_DIRECT}/api/jobs/${jobId}/download`;
}

export async function deleteJob(jobId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/jobs/${jobId}`, { method: "DELETE" });
  return handleResponse(res);
}

export function getVideoStreamUrl(fileId: string): string {
  // Use direct backend URL to bypass Next.js proxy limitations for streaming
  return `${BACKEND_DIRECT}/api/video/${fileId}/stream`;
}

export function getFileStreamUrl(fileId: string): string {
  return `${BACKEND_DIRECT}/api/file/${fileId}/stream`;
}

export function getVideoStreamUrlProxy(fileId: string): string {
  return `${BASE}/api/video/${fileId}/stream`;
}

export function getWebSocketUrl(jobId: string): string {
  const backendUrl = new URL(BACKEND_DIRECT);
  const protocol = backendUrl.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${backendUrl.host}/api/ws/jobs/${jobId}`;
}
