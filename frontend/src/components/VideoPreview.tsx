"use client";
import { useRef, useEffect, useCallback, useState } from "react";
import { motion } from "framer-motion";
import { Grid3x3, Square, ChevronsLeft, ChevronsRight, Play, Pause } from "lucide-react";
import type { Region, FileType } from "@/lib/types";
import { getVideoStreamUrl } from "@/lib/api";

interface VideoPreviewProps {
  fileId: string;
  frameBase64: string;
  videoWidth: number;
  videoHeight: number;
  region: Region | null;
  onRegionChange: (region: Region) => void;
  filename: string;
  fileType?: FileType;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

type DragMode = "idle" | "drawing" | "moving" | "resizing";
type ResizeHandle = "nw" | "n" | "ne" | "e" | "se" | "s" | "sw" | "w";

const HANDLE_HIT_RADIUS = 14; // px, hit area radius for handles
const HANDLE_VISUAL = 9;      // px, visual square side
const MIN_DRAG = 8;           // minimum drag distance to register

const HANDLE_CURSORS: Record<ResizeHandle, string> = {
  nw: "nw-resize", n: "n-resize", ne: "ne-resize",
  e: "e-resize",   se: "se-resize", s: "s-resize",
  sw: "sw-resize", w: "w-resize",
};

export default function VideoPreview({
  fileId,
  frameBase64,
  videoWidth,
  videoHeight,
  region,
  onRegionChange,
  filename,
  fileType = "video",
}: VideoPreviewProps) {
  const videoRef      = useRef<HTMLVideoElement>(null);
  const canvasRef     = useRef<HTMLCanvasElement>(null);
  const containerRef  = useRef<HTMLDivElement>(null);
  const isVideo = fileType === "video";

  const [isPlaying,  setIsPlaying]  = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration,    setDuration]    = useState(0);
  const [isSeeking,   setIsSeeking]   = useState(false);
  const [videoError,  setVideoError]  = useState(false);

  // ── Drag state (refs to avoid stale closures) ────────────────────────────
  const dragModeRef          = useRef<DragMode>("idle");
  const dragHandleRef        = useRef<ResizeHandle | null>(null);
  const dragStartCanvasRef   = useRef<{ x: number; y: number } | null>(null);
  const dragStartRegionRef   = useRef<Region | null>(null);
  const drawStartRef         = useRef<{ x: number; y: number } | null>(null);
  const drawCurrentRef       = useRef<{ x: number; y: number } | null>(null);
  const animFrameRef         = useRef<number>(0);

  const videoStreamUrl = isVideo ? getVideoStreamUrl(fileId) : "";

  // ── Coordinate helpers ───────────────────────────────────────────────────
  const getVideoRect = useCallback(() => {
    const container = containerRef.current;
    if (!container) return { scale: 1, offsetX: 0, offsetY: 0, displayW: videoWidth, displayH: videoHeight };
    const cw = container.clientWidth;
    const ch = container.clientHeight;
    const scale   = Math.min(cw / videoWidth, ch / videoHeight, 1);
    const displayW = videoWidth  * scale;
    const displayH = videoHeight * scale;
    return { scale, offsetX: (cw - displayW) / 2, offsetY: (ch - displayH) / 2, displayW, displayH };
  }, [videoWidth, videoHeight]);

  const getHandlePositions = useCallback(
    (r: Region, scale: number, offsetX: number, offsetY: number) => {
      const rx = offsetX + r.x * scale;
      const ry = offsetY + r.y * scale;
      const rw = r.w * scale;
      const rh = r.h * scale;
      return {
        nw: { x: rx,        y: ry        },
        n:  { x: rx + rw/2, y: ry        },
        ne: { x: rx + rw,   y: ry        },
        e:  { x: rx + rw,   y: ry + rh/2 },
        se: { x: rx + rw,   y: ry + rh   },
        s:  { x: rx + rw/2, y: ry + rh   },
        sw: { x: rx,        y: ry + rh   },
        w:  { x: rx,        y: ry + rh/2 },
      } as Record<ResizeHandle, { x: number; y: number }>;
    },
    []
  );

  // ── Canvas drawing ───────────────────────────────────────────────────────
  const drawOverlay = useCallback(() => {
    const canvas    = canvasRef.current;
    const container = containerRef.current;
    const ctx       = canvas?.getContext("2d");
    if (!canvas || !ctx || !container) return;

    const w = container.clientWidth;
    const h = container.clientHeight;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width  = w;
      canvas.height = h;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const { scale, offsetX, offsetY, displayW, displayH } = getVideoRect();
    const mode = dragModeRef.current;

    // ── Helper: spotlight cutout ────────────────────────────────────────
    const drawSpotlight = (hx: number, hy: number, hw: number, hh: number) => {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.52)";
      ctx.fillRect(offsetX, offsetY, displayW, displayH);
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0,0,0,1)";
      ctx.fillRect(hx, hy, hw, hh);
      ctx.globalCompositeOperation = "source-over";
      ctx.restore();
    };

    // ── Drawing mode ────────────────────────────────────────────────────
    if (mode === "drawing" && drawStartRef.current && drawCurrentRef.current) {
      const s = drawStartRef.current;
      const c = drawCurrentRef.current;
      const dx = Math.min(s.x, c.x);
      const dy = Math.min(s.y, c.y);
      const dw = Math.abs(c.x - s.x);
      const dh = Math.abs(c.y - s.y);

      if (dw > 2 && dh > 2) {
        drawSpotlight(dx, dy, dw, dh);

        // Animated dashed green border
        ctx.strokeStyle = "#a6e3a1";
        ctx.lineWidth = 2;
        ctx.setLineDash([7, 4]);
        ctx.strokeRect(dx, dy, dw, dh);
        ctx.setLineDash([]);

        // Dimension pill in the center of the selection
        const vw = Math.round(dw / scale);
        const vh = Math.round(dh / scale);
        const label = `${vw} × ${vh}`;
        ctx.font = "bold 13px system-ui";
        const tw = ctx.measureText(label).width;
        const lx = dx + dw / 2 - tw / 2 - 6;
        const ly = dy + dh / 2 - 10;
        const bw = tw + 12;
        const bh = 22;
        ctx.fillStyle = "rgba(0,0,0,0.65)";
        ctx.beginPath();
        ctx.roundRect(lx, ly, bw, bh, 4);
        ctx.fill();
        ctx.fillStyle = "#a6e3a1";
        ctx.fillText(label, lx + 6, ly + 15);
      }
      return;
    }

    // ── Confirmed region ────────────────────────────────────────────────
    if (!region) return;

    const rx = offsetX + region.x * scale;
    const ry = offsetY + region.y * scale;
    const rw = region.w * scale;
    const rh = region.h * scale;

    drawSpotlight(rx, ry, rw, rh);

    // Pink selection border
    ctx.strokeStyle = "#f38ba8";
    ctx.lineWidth = 2;
    ctx.strokeRect(rx, ry, rw, rh);

    // Thin inner shadow for depth
    ctx.strokeStyle = "rgba(243,139,168,0.25)";
    ctx.lineWidth = 6;
    ctx.strokeRect(rx + 3, ry + 3, rw - 6, rh - 6);

    // ── Resize handles ──────────────────────────────────────────────────
    const handles = getHandlePositions(region, scale, offsetX, offsetY);
    const hs = HANDLE_VISUAL / 2;

    for (const [hName, pos] of Object.entries(handles) as [ResizeHandle, { x: number; y: number }][]) {
      const isActive = dragHandleRef.current === hName && mode === "resizing";

      // Hit-area visual hint (large transparent circle on hover would need state;
      // we just draw the solid square handle)
      ctx.fillStyle = isActive ? "#f38ba8" : "#ffffff";
      ctx.strokeStyle = "#f38ba8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.rect(pos.x - hs, pos.y - hs, HANDLE_VISUAL, HANDLE_VISUAL);
      ctx.fill();
      ctx.stroke();
    }

    // ── Dimension label ─────────────────────────────────────────────────
    const label = `${region.w} × ${region.h} px`;
    ctx.font = "bold 12px system-ui";
    const tw = ctx.measureText(label).width;
    const lx = rx;
    const ly = ry > 26 ? ry - 8 : ry + rh + 20;
    ctx.fillStyle = "rgba(0,0,0,0.7)";
    ctx.beginPath();
    ctx.roundRect(lx, ly - 15, tw + 12, 20, 4);
    ctx.fill();
    ctx.fillStyle = "#f38ba8";
    ctx.fillText(label, lx + 6, ly);
  }, [region, getVideoRect, getHandlePositions]);

  // ── Hit test ──────────────────────────────────────────────────────────────
  const hitTest = useCallback(
    (cx: number, cy: number): { mode: DragMode; handle?: ResizeHandle } => {
      if (!region) return { mode: "drawing" };

      const { scale, offsetX, offsetY } = getVideoRect();
      const handles = getHandlePositions(region, scale, offsetX, offsetY);

      // Check handles first (smaller targets, higher priority)
      for (const [handle, pos] of Object.entries(handles) as [ResizeHandle, { x: number; y: number }][]) {
        if (Math.abs(cx - pos.x) <= HANDLE_HIT_RADIUS && Math.abs(cy - pos.y) <= HANDLE_HIT_RADIUS) {
          return { mode: "resizing", handle };
        }
      }

      // Check inside selection box
      const rx = offsetX + region.x * scale;
      const ry = offsetY + region.y * scale;
      const rw = region.w * scale;
      const rh = region.h * scale;
      if (cx >= rx && cx <= rx + rw && cy >= ry && cy <= ry + rh) {
        return { mode: "moving" };
      }

      return { mode: "drawing" };
    },
    [region, getVideoRect, getHandlePositions]
  );

  // ── Pointer events (works for mouse + touch) ──────────────────────────────
  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      e.preventDefault();
      const rect = e.currentTarget.getBoundingClientRect();
      const cx = e.clientX - rect.left;
      const cy = e.clientY - rect.top;

      const { offsetX, offsetY, displayW, displayH } = getVideoRect();
      const inVideo = cx >= offsetX && cy >= offsetY && cx <= offsetX + displayW && cy <= offsetY + displayH;
      if (!inVideo) return;

      // Pause video while drawing
      if (isVideo && videoRef.current && !videoRef.current.paused) {
        videoRef.current.pause();
        setIsPlaying(false);
      }

      const hit = hitTest(cx, cy);
      dragModeRef.current = hit.mode;

      if (hit.mode === "drawing") {
        drawStartRef.current   = { x: cx, y: cy };
        drawCurrentRef.current = { x: cx, y: cy };
      } else {
        dragStartCanvasRef.current = { x: cx, y: cy };
        dragStartRegionRef.current = region ? { ...region } : null;
        if (hit.mode === "resizing") dragHandleRef.current = hit.handle!;
      }

      // Capture pointer so drag continues even outside the canvas element
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [getVideoRect, hitTest, isVideo, region]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const cx   = e.clientX - rect.left;
      const cy   = e.clientY - rect.top;
      const mode = dragModeRef.current;

      // ── Idle: just update cursor based on hover position ───────────────
      if (mode === "idle") {
        const hit = hitTest(cx, cy);
        if (hit.mode === "resizing" && hit.handle) {
          e.currentTarget.style.cursor = HANDLE_CURSORS[hit.handle];
        } else if (hit.mode === "moving") {
          e.currentTarget.style.cursor = "move";
        } else {
          e.currentTarget.style.cursor = "crosshair";
        }
        return;
      }

      e.preventDefault();
      const { scale, offsetX, offsetY, displayW, displayH } = getVideoRect();

      if (mode === "drawing") {
        const ccx = Math.max(offsetX, Math.min(offsetX + displayW, cx));
        const ccy = Math.max(offsetY, Math.min(offsetY + displayH, cy));
        drawCurrentRef.current = { x: ccx, y: ccy };
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = requestAnimationFrame(drawOverlay);
      } else if (mode === "moving" && dragStartCanvasRef.current && dragStartRegionRef.current) {
        const orig = dragStartRegionRef.current;
        const dx = (cx - dragStartCanvasRef.current.x) / scale;
        const dy = (cy - dragStartCanvasRef.current.y) / scale;
        const nx = Math.max(0, Math.min(videoWidth  - orig.w, orig.x + dx));
        const ny = Math.max(0, Math.min(videoHeight - orig.h, orig.y + dy));
        onRegionChange({ ...orig, x: Math.round(nx), y: Math.round(ny) });
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = requestAnimationFrame(drawOverlay);
      } else if (
        mode === "resizing" &&
        dragStartCanvasRef.current &&
        dragStartRegionRef.current &&
        dragHandleRef.current
      ) {
        const handle = dragHandleRef.current;
        const orig   = dragStartRegionRef.current;
        const dx = (cx - dragStartCanvasRef.current.x) / scale;
        const dy = (cy - dragStartCanvasRef.current.y) / scale;

        let { x, y, w, h } = orig;
        if (handle.includes("n")) { y = orig.y + dy; h = orig.h - dy; }
        if (handle.includes("s")) { h = orig.h + dy; }
        if (handle.includes("w")) { x = orig.x + dx; w = orig.w - dx; }
        if (handle.includes("e")) { w = orig.w + dx; }

        const MIN_SIZE = 10;
        if (w < MIN_SIZE) { if (handle.includes("w")) x = orig.x + orig.w - MIN_SIZE; w = MIN_SIZE; }
        if (h < MIN_SIZE) { if (handle.includes("n")) y = orig.y + orig.h - MIN_SIZE; h = MIN_SIZE; }
        x = Math.max(0, x);
        y = Math.max(0, y);
        w = Math.min(videoWidth  - x, w);
        h = Math.min(videoHeight - y, h);

        onRegionChange({ x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) });
        cancelAnimationFrame(animFrameRef.current);
        animFrameRef.current = requestAnimationFrame(drawOverlay);
      }
    },
    [drawOverlay, getVideoRect, hitTest, onRegionChange, videoWidth, videoHeight]
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* already released */ }
      const mode = dragModeRef.current;

      if (mode === "drawing") {
        const s = drawStartRef.current;
        const c = drawCurrentRef.current;
        if (s && c) {
          const dw = Math.abs(c.x - s.x);
          const dh = Math.abs(c.y - s.y);
          if (dw >= MIN_DRAG && dh >= MIN_DRAG) {
            const { scale, offsetX, offsetY } = getVideoRect();
            const toV = (px: number, py: number) => ({
              x: Math.max(0, Math.min(videoWidth,  Math.round((px - offsetX) / scale))),
              y: Math.max(0, Math.min(videoHeight, Math.round((py - offsetY) / scale))),
            });
            const v1 = toV(Math.min(s.x, c.x), Math.min(s.y, c.y));
            const v2 = toV(Math.max(s.x, c.x), Math.max(s.y, c.y));
            onRegionChange({ x: v1.x, y: v1.y, w: v2.x - v1.x, h: v2.y - v1.y });
          }
        }
        drawStartRef.current   = null;
        drawCurrentRef.current = null;
      }

      dragModeRef.current        = "idle";
      dragStartCanvasRef.current = null;
      dragStartRegionRef.current = null;
      dragHandleRef.current      = null;
      // useEffect([drawOverlay, region]) handles the final redraw once region state propagates
    },
    [drawOverlay, getVideoRect, onRegionChange, videoWidth, videoHeight]
  );

  // ── Resize observer ───────────────────────────────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => requestAnimationFrame(drawOverlay));
    observer.observe(container);
    return () => observer.disconnect();
  }, [drawOverlay]);

  useEffect(() => { drawOverlay(); }, [drawOverlay, region]);

  // ── Video event handlers ──────────────────────────────────────────────────
  const handleTimeUpdate = () => {
    if (videoRef.current && !isSeeking) setCurrentTime(videoRef.current.currentTime);
  };
  const handleLoadedMetadata = () => {
    if (videoRef.current) { setDuration(videoRef.current.duration); setVideoError(false); }
  };
  const handleCanPlay      = () => setVideoError(false);
  const handleVideoError   = () => setVideoError(true);
  const handleVideoEnded   = () => setIsPlaying(false);

  const handlePlayPause = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) { video.play(); setIsPlaying(true); }
    else              { video.pause(); setIsPlaying(false); }
  };

  const handleSkip = (seconds: number) => {
    const video = videoRef.current;
    if (!video) return;
    const target = Math.max(0, Math.min(video.duration, video.currentTime + seconds));
    video.currentTime = target;
    setCurrentTime(target);
  };

  const handleSeekChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    setCurrentTime(time);
    if (videoRef.current) videoRef.current.currentTime = time;
  };

  const seekPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  const typeLabels: Record<string, string> = {
    video: "Video", image: "Imagen", pdf: "PDF", pptx: "PPTX",
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="px-6 pb-2">
      {/* ── Header row ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm text-ctp-subtext0 truncate max-w-xs">{filename}</span>
          {fileType !== "video" && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-ctp-surface0 text-ctp-blue font-medium">
              {typeLabels[fileType] ?? fileType.toUpperCase()}
            </span>
          )}
        </div>
        <span className="text-xs text-ctp-overlay0">{videoWidth}×{videoHeight}</span>
      </div>

      {/* ── Media container ─────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        className="relative w-full bg-ctp-mantle rounded-lg border border-ctp-surface0 overflow-hidden"
        style={{ height: "clamp(240px, 45vh, 480px)" }}
      >
        {isVideo ? (
          <video
            ref={videoRef}
            src={videoStreamUrl}
            poster={`data:image/jpeg;base64,${frameBase64}`}
            className="w-full h-full object-contain"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onCanPlay={handleCanPlay}
            onError={handleVideoError}
            onEnded={handleVideoEnded}
            crossOrigin="anonymous"
            playsInline
            preload="auto"
          />
        ) : (
          <img
            src={`data:image/jpeg;base64,${frameBase64}`}
            alt="Vista previa"
            className="w-full h-full object-contain"
          />
        )}

        {isVideo && videoError && (
          <div className="absolute inset-0 flex items-center justify-center bg-ctp-mantle/80">
            <p className="text-sm text-ctp-red">Error al cargar el video</p>
          </div>
        )}

        {/* ── Canvas overlay (handles ALL pointer events) ──────────────── */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full"
          style={{ touchAction: "none", cursor: "crosshair" }}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
        />

        {/* ── Instruction hint (shown when no region is selected) ──────── */}
        {!region && (
          <div className="absolute inset-0 flex items-end justify-center pb-3 pointer-events-none">
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="flex items-center gap-1.5 text-xs text-white/70 bg-black/40 px-3 py-1.5 rounded-full backdrop-blur-sm select-none"
            >
              <Grid3x3 size={12} className="shrink-0 opacity-80" strokeWidth={2} />
              Arrastra para marcar el área de la marca de agua
            </motion.div>
          </div>
        )}

        {/* ── Selection info badge (top-left when region exists) ───────── */}
        {region && (
          <div className="absolute top-2 left-2 pointer-events-none">
            <div className="flex items-center gap-1.5 text-[11px] text-white/80 bg-black/50 px-2 py-1 rounded-md backdrop-blur-sm select-none">
              <Square size={10} className="text-ctp-red" strokeWidth={2.5} />
              <span>Arrastra borde/esquina para ajustar · Arrastra interior para mover</span>
            </div>
          </div>
        )}
      </div>

      {/* ── Video player controls ────────────────────────────────────────── */}
      {isVideo && (
        <div className="mt-2 rounded-lg bg-ctp-mantle border border-ctp-surface0 px-3 py-2">
          {/* Seek bar */}
          <div className="relative mb-2">
            <input
              type="range"
              min={0}
              max={duration || 0}
              step={0.1}
              value={currentTime}
              onChange={handleSeekChange}
              onPointerDown={() => setIsSeeking(true)}
              onPointerUp={()   => setIsSeeking(false)}
              onLostPointerCapture={() => setIsSeeking(false)}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-ctp-surface0
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-ctp-blue [&::-webkit-slider-thumb]:cursor-pointer
                [&::-webkit-slider-thumb]:shadow-md [&::-webkit-slider-thumb]:transition-transform
                [&::-webkit-slider-thumb]:hover:scale-125"
              style={{ background: `linear-gradient(to right, #89b4fa ${seekPercent}%, #313244 ${seekPercent}%)` }}
            />
          </div>

          {/* Controls row */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleSkip(-5)}
                className="p-1.5 rounded-md hover:bg-ctp-surface0 text-ctp-subtext0 hover:text-ctp-text transition-colors"
                title="Retroceder 5s"
              >
                <ChevronsLeft size={18} />
              </button>

              <button
                onClick={handlePlayPause}
                className="p-2 rounded-lg hover:bg-ctp-surface0 text-ctp-text transition-colors"
                title={isPlaying ? "Pausar" : "Reproducir"}
              >
                {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" />}
              </button>

              <button
                onClick={() => handleSkip(5)}
                className="p-1.5 rounded-md hover:bg-ctp-surface0 text-ctp-subtext0 hover:text-ctp-text transition-colors"
                title="Adelantar 5s"
              >
                <ChevronsRight size={18} />
              </button>
            </div>

            <span className="text-xs text-ctp-overlay0 tabular-nums">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>
        </div>
      )}
    </motion.div>
  );
}
