"use client";
import { useReducer, useCallback, useRef } from "react";
import type { JobInfo, JobStatus, Region, RemovalMethod } from "@/lib/types";

export interface QueueItem {
  id: string;
  fileId: string;
  filename: string;
  region: Region;
  method: RemovalMethod;
  sensitivity: number;
  inpaintRadius: number;
  trimSeconds: number;
  jobId: string | null;
  status: JobStatus | "pending";
  progress: number;
  currentFrame: number;
  totalFrames: number;
  etaSeconds: number | null;
  error: string | null;
}

type Action =
  | { type: "ADD"; id: string; item: Omit<QueueItem, "id" | "jobId" | "status" | "progress" | "currentFrame" | "totalFrames" | "etaSeconds" | "error"> }
  | { type: "SET_JOB_ID"; id: string; jobId: string }
  | { type: "UPDATE_PROGRESS"; id: string; progress: number; currentFrame: number; totalFrames: number; etaSeconds: number | null; status: JobStatus }
  | { type: "SET_STATUS"; id: string; status: JobStatus | "pending"; error?: string }
  | { type: "REMOVE"; id: string }
  | { type: "UPDATE_FROM_JOB"; jobInfo: JobInfo };

function reducer(state: QueueItem[], action: Action): QueueItem[] {
  switch (action.type) {
    case "ADD":
      return [...state, {
        ...action.item,
        id: action.id,
        jobId: null,
        status: "pending",
        progress: 0,
        currentFrame: 0,
        totalFrames: 0,
        etaSeconds: null,
        error: null,
      }];
    case "SET_JOB_ID":
      return state.map(i => i.id === action.id ? { ...i, jobId: action.jobId, status: "queued" } : i);
    case "UPDATE_PROGRESS":
      return state.map(i => i.id === action.id ? {
        ...i, progress: action.progress, currentFrame: action.currentFrame,
        totalFrames: action.totalFrames, etaSeconds: action.etaSeconds,
        status: action.status,
      } : i);
    case "SET_STATUS":
      return state.map(i => i.id === action.id ? { ...i, status: action.status, error: action.error ?? null } : i);
    case "REMOVE":
      return state.filter(i => i.id !== action.id);
    case "UPDATE_FROM_JOB": {
      const j = action.jobInfo;
      return state.map(i => i.jobId === j.job_id ? {
        ...i, status: j.status, progress: j.progress,
        currentFrame: j.current_frame, totalFrames: j.total_frames,
        etaSeconds: j.eta_seconds, error: j.error,
      } : i);
    }
    default:
      return state;
  }
}

export function useBatchQueue() {
  const [queue, dispatch] = useReducer(reducer, []);
  const nextIdRef = useRef(1);

  const addToQueue = useCallback((item: Omit<QueueItem, "id" | "jobId" | "status" | "progress" | "currentFrame" | "totalFrames" | "etaSeconds" | "error">): string => {
    const id = String(nextIdRef.current++);
    dispatch({ type: "ADD", id, item });
    return id;
  }, []);

  const setJobId = useCallback((id: string, jobId: string) => {
    dispatch({ type: "SET_JOB_ID", id, jobId });
  }, []);

  const updateProgress = useCallback((id: string, progress: number, currentFrame: number, totalFrames: number, etaSeconds: number | null, status: JobStatus) => {
    dispatch({ type: "UPDATE_PROGRESS", id, progress, currentFrame, totalFrames, etaSeconds, status });
  }, []);

  const setStatus = useCallback((id: string, status: JobStatus | "pending", error?: string) => {
    dispatch({ type: "SET_STATUS", id, status, error });
  }, []);

  const removeFromQueue = useCallback((id: string) => {
    dispatch({ type: "REMOVE", id });
  }, []);

  const updateFromJob = useCallback((jobInfo: JobInfo) => {
    dispatch({ type: "UPDATE_FROM_JOB", jobInfo });
  }, []);

  return { queue, addToQueue, setJobId, updateProgress, setStatus, removeFromQueue, updateFromJob };
}
