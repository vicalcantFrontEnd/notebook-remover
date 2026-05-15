import type { FileType, RemovalMethod } from "./types";

export const MAX_UPLOAD_SIZE_MB = 500;

export const ALLOWED_FORMATS = [
  ".mp4", ".mkv", ".avi", ".mov", ".webm",
  ".jpg", ".jpeg", ".png", ".webp",
  ".pdf",
  ".pptx",
];

export const ALLOWED_MIME_TYPES = [
  "video/mp4", "video/x-matroska", "video/avi",
  "video/quicktime", "video/webm",
  "image/jpeg", "image/png", "image/webp",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
];

// Accept string for file input
export const FILE_ACCEPT = [
  "video/*",
  "image/jpeg", "image/png", "image/webp",
  ".pdf", ".pptx",
].join(",");

export const DEFAULT_SENSITIVITY = 30;
export const DEFAULT_INPAINT_RADIUS = 3;
export const DEFAULT_TRIM_SECONDS = 0;
export const SENSITIVITY_RANGE = { min: 5, max: 80, step: 5 };
export const RADIUS_RANGE = { min: 1, max: 15, step: 1 };
export const TRIM_RANGE = { min: 0, max: 30, step: 0.5 };

/** Available removal methods per file type */
export const METHODS_BY_TYPE: Record<FileType, RemovalMethod[]> = {
  video: ["box"],
  image: ["box"],
  pdf: ["box"],
  pptx: ["delete_shapes"],
};

/** Detect file type from filename extension */
export function detectFileType(filename: string): FileType {
  const ext = filename.toLowerCase().split(".").pop() ?? "";
  if (["mp4", "mkv", "avi", "mov", "webm"].includes(ext)) return "video";
  if (["jpg", "jpeg", "png", "webp"].includes(ext)) return "image";
  if (ext === "pdf") return "pdf";
  if (ext === "pptx") return "pptx";
  return "video";
}
