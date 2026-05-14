"use client";
import { useState, useCallback, useRef } from "react";
import type { Region } from "@/lib/types";

interface UseRegionSelectorProps {
  videoWidth: number;
  videoHeight: number;
  canvasWidth: number;
  canvasHeight: number;
}

export function useRegionSelector({ videoWidth, videoHeight, canvasWidth, canvasHeight }: UseRegionSelectorProps) {
  const [region, setRegion] = useState<Region | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragStart = useRef<{ x: number; y: number } | null>(null);
  const dragCurrent = useRef<{ x: number; y: number } | null>(null);

  const scale = Math.min(canvasWidth / videoWidth, canvasHeight / videoHeight, 1);
  const displayW = videoWidth * scale;
  const displayH = videoHeight * scale;
  const offsetX = (canvasWidth - displayW) / 2;
  const offsetY = (canvasHeight - displayH) / 2;

  const canvasToVideo = useCallback((cx: number, cy: number) => {
    const vx = Math.max(0, Math.min(videoWidth, (cx - offsetX) / scale));
    const vy = Math.max(0, Math.min(videoHeight, (cy - offsetY) / scale));
    return { x: Math.round(vx), y: Math.round(vy) };
  }, [videoWidth, videoHeight, scale, offsetX, offsetY]);

  const videoToCanvas = useCallback((vx: number, vy: number) => ({
    x: offsetX + vx * scale,
    y: offsetY + vy * scale,
  }), [scale, offsetX, offsetY]);

  const onMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    dragStart.current = { x: cx, y: cy };
    dragCurrent.current = { x: cx, y: cy };
    setIsDragging(true);
  }, []);

  const isDraggingRef = useRef(false);
  isDraggingRef.current = isDragging;

  const onMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current || !dragStart.current) return;
    const rect = e.currentTarget.getBoundingClientRect();
    dragCurrent.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const onMouseUp = useCallback(() => {
    if (!dragStart.current || !dragCurrent.current) {
      setIsDragging(false);
      return;
    }
    const s = dragStart.current;
    const c = dragCurrent.current;
    if (Math.abs(c.x - s.x) < 8 || Math.abs(c.y - s.y) < 8) {
      setIsDragging(false);
      return;
    }
    const v1 = canvasToVideo(Math.min(s.x, c.x), Math.min(s.y, c.y));
    const v2 = canvasToVideo(Math.max(s.x, c.x), Math.max(s.y, c.y));
    setRegion({ x: v1.x, y: v1.y, w: v2.x - v1.x, h: v2.y - v1.y });
    setIsDragging(false);
    dragStart.current = null;
    dragCurrent.current = null;
  }, [canvasToVideo]);

  return {
    region, setRegion, isDragging,
    dragStart: dragStart.current, dragCurrent: dragCurrent.current,
    scale, displayW, displayH, offsetX, offsetY,
    videoToCanvas, canvasToVideo,
    onMouseDown, onMouseMove, onMouseUp,
  };
}
