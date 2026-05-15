"use client";
import { useState, useCallback, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Check, Play } from "lucide-react";
import Header from "@/components/Header";
import DropZone from "@/components/DropZone";
import VideoPreview from "@/components/VideoPreview";
import RegionSelector from "@/components/RegionSelector";
import ParameterControls from "@/components/ParameterControls";
import MethodSelector from "@/components/MethodSelector";
import BatchQueue from "@/components/BatchQueue";
import { useBatchQueue } from "@/hooks/useBatchQueue";
import { DEFAULT_INPAINT_RADIUS, DEFAULT_SENSITIVITY, DEFAULT_TRIM_SECONDS } from "@/lib/constants";
import * as api from "@/lib/api";
import type { FileInfo, FileType, Region, RemovalMethod, ProgressMessage } from "@/lib/types";

const FILE_TYPE_LABELS: Record<FileType, string> = {
  video: "Video", image: "Imagen", pdf: "PDF", pptx: "PPTX",
};
const FILE_TYPE_COLORS: Record<FileType, string> = {
  video: "text-ctp-blue  bg-ctp-blue/10  border-ctp-blue/20",
  image: "text-ctp-peach bg-ctp-peach/10 border-ctp-peach/20",
  pdf:   "text-ctp-red   bg-ctp-red/10   border-ctp-red/20",
  pptx:  "text-ctp-mauve bg-ctp-mauve/10 border-ctp-mauve/20",
};

function SectionLabel({ step, label, done }: { step: number; label: string; done?: boolean }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <div className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 transition-all duration-300 ${
        done ? "bg-ctp-green" : "bg-ctp-surface1"
      }`}>
        {done ? (
          <Check size={8} className="text-white" strokeWidth={3.5} />
        ) : (
          <span className="text-[8px] text-ctp-overlay1 font-bold leading-none">{step}</span>
        )}
      </div>
      <span className="text-[11px] font-semibold text-ctp-subtext0 uppercase tracking-wider">{label}</span>
    </div>
  );
}

export default function Home() {
  const [fileInfo,    setFileInfo]    = useState<FileInfo | null>(null);
  const [fileType,    setFileType]    = useState<FileType>("video");
  const [region,      setRegion]      = useState<Region | null>(null);
  const [trimSeconds, setTrimSeconds] = useState(DEFAULT_TRIM_SECONDS);
  const [isUploading, setIsUploading] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);

  const [method, setMethod] = useState<RemovalMethod>(fileType === "pptx" ? "delete_shapes" : "box");

  useEffect(() => {
    setMethod(fileType === "pptx" ? "delete_shapes" : "box");
  }, [fileType]);

  const { queue, addToQueue, setJobId, updateProgress, setStatus, removeFromQueue } = useBatchQueue();
  const wsRefs = useRef<Map<string, WebSocket>>(new Map());

  const handleFileSelected = useCallback(async (file: File) => {
    setIsUploading(true);
    try {
      const { file_id } = await api.uploadVideo(file);
      const info = await api.getFileInfo(file_id);
      setFileInfo(info);
      setFileType(info.file_type);

      const dw = 294, dh = 64;
      setRegion({ x: info.width - dw - 20, y: info.height - dh - 20, w: dw, h: dh });

      setIsDetecting(true);
      try {
        const { region: detected } = await api.detectFileRegion(file_id);
        setRegion(detected);
      } catch { /* se queda con el default */ }
      setIsDetecting(false);
    } catch (err: unknown) {
      alert(`Error al subir: ${err instanceof Error ? err.message : err}`);
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleAutoDetect = useCallback(async () => {
    if (!fileInfo) return;
    setIsDetecting(true);
    try {
      const { region: detected } = await api.detectFileRegion(fileInfo.file_id);
      setRegion(detected);
    } catch (err: unknown) {
      alert(`Error al detectar: ${err instanceof Error ? err.message : err}`);
    } finally {
      setIsDetecting(false);
    }
  }, [fileInfo]);

  const handleReset = useCallback(() => { setRegion(null); }, []);

  const connectWS = useCallback((queueId: string, jobId: string) => {
    const ws = new WebSocket(api.getWebSocketUrl(jobId));
    wsRefs.current.set(queueId, ws);
    ws.onmessage = (event) => {
      try {
        const msg: ProgressMessage = JSON.parse(event.data);
        if (msg.type === "progress") {
          updateProgress(queueId, msg.progress ?? 0, msg.current_frame ?? 0, msg.total_frames ?? 0, msg.eta_seconds ?? null, (msg.status as "processing") ?? "processing");
        } else if (msg.type === "done") {
          const finalStatus = msg.status === "completed" ? "completed" : msg.status === "cancelled" ? "cancelled" : "failed";
          setStatus(queueId, finalStatus, msg.error ?? undefined);
          ws.close(); wsRefs.current.delete(queueId);
        }
      } catch {}
    };
    ws.onerror = () => ws.close();
    ws.onclose = () => wsRefs.current.delete(queueId);
  }, [updateProgress, setStatus]);

  const handleAddToQueue = useCallback(async () => {
    if (!fileInfo || !region) return;
    const queueId = addToQueue({
      fileId: fileInfo.file_id, filename: fileInfo.filename, region, method,
      sensitivity: DEFAULT_SENSITIVITY, inpaintRadius: DEFAULT_INPAINT_RADIUS, trimSeconds,
    });
    try {
      const job = await api.createJob({
        file_id: fileInfo.file_id, region, method,
        sensitivity: DEFAULT_SENSITIVITY, inpaint_radius: DEFAULT_INPAINT_RADIUS,
        trim_end_seconds: trimSeconds, file_type: fileType,
      });
      setJobId(queueId, job.job_id);
      connectWS(queueId, job.job_id);
    } catch (err: unknown) {
      alert(`Error al crear trabajo: ${err instanceof Error ? err.message : err}`);
    }
  }, [fileInfo, fileType, region, method, trimSeconds, addToQueue, setJobId, connectWS]);

  const handleCancel = useCallback(async (queueId: string) => {
    const item = queue.find(i => i.id === queueId);
    if (item?.jobId) { try { await api.cancelJob(item.jobId); } catch {} }
    setStatus(queueId, "cancelled");
    wsRefs.current.get(queueId)?.close();
  }, [queue, setStatus]);

  const handleRemove = useCallback(async (queueId: string) => {
    const item = queue.find(i => i.id === queueId);
    if (item?.jobId) { try { await api.deleteJob(item.jobId); } catch {} }
    removeFromQueue(queueId);
  }, [queue, removeFromQueue]);

  const handleDownload = useCallback((jobId: string) => {
    let downloadName = "archivo_procesado";
    if (fileInfo) {
      const stem = fileInfo.filename.replace(/\.[^.]+$/, "");
      const ext = fileInfo.filename.split(".").pop() ?? "mp4";
      downloadName = `${stem}_clean.${ext}`;
    }
    const a = document.createElement("a");
    a.href = api.getDownloadUrl(jobId);
    a.download = downloadName;
    a.click();
  }, [fileInfo]);

  const handleNewFile = useCallback(() => {
    setFileInfo(null); setRegion(null); setFileType("video");
  }, []);

  useEffect(() => {
    const refs = wsRefs.current;
    return () => { refs.forEach(ws => ws.close()); };
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        {!fileInfo ? (
          <DropZone onFileSelected={handleFileSelected} isUploading={isUploading} />
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">

            {/* ── Breadcrumb nav ── */}
            <div className="flex items-center gap-2 mb-5 text-sm text-ctp-overlay0">
              <button onClick={handleNewFile}
                className="flex items-center gap-1.5 hover:text-ctp-text transition-colors">
                <ChevronLeft size={13} strokeWidth={2.5} />
                Inicio
              </button>
              <ChevronRight size={13} strokeWidth={1.5} className="opacity-30" />
              <span className="text-ctp-subtext0 truncate max-w-xs text-xs">{fileInfo.filename}</span>
            </div>

            {/* ── Two-column editor ── */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-5 items-start">

              {/* Left: video preview */}
              <div className="rounded-2xl border border-white/5 bg-ctp-mantle/60 backdrop-blur-sm overflow-hidden">
                <VideoPreview
                  fileId={fileInfo.file_id}
                  frameBase64={fileInfo.first_frame_base64}
                  videoWidth={fileInfo.width}
                  videoHeight={fileInfo.height}
                  region={region}
                  onRegionChange={(r) => setRegion(r)}
                  filename={fileInfo.filename}
                  fileType={fileType}
                />
              </div>

              {/* Right: settings panel */}
              <div className="lg:sticky lg:top-[73px] lg:max-h-[calc(100vh-93px)] lg:overflow-y-auto lg:pr-0.5">
                <div className="rounded-2xl border border-white/5 bg-ctp-mantle/60 backdrop-blur-sm overflow-hidden">

                  {/* ── File info strip ── */}
                  <div className="flex items-center gap-3 px-4 py-3 bg-ctp-surface0/20 border-b border-white/5">
                    <span className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-md border ${FILE_TYPE_COLORS[fileType]}`}>
                      {FILE_TYPE_LABELS[fileType]}
                    </span>
                    <span className="text-xs text-ctp-subtext1 font-medium truncate flex-1">{fileInfo.filename}</span>
                    <span className="text-[10px] text-ctp-overlay0 shrink-0 tabular-nums">{fileInfo.width}×{fileInfo.height}</span>
                  </div>

                  {/* ── Sección: Área de marca ── */}
                  <div className="px-4 py-4 border-b border-white/5">
                    <SectionLabel step={1} label="Área de marca" done={!!region} />
                    <RegionSelector
                      region={region}
                      onAutoDetect={handleAutoDetect}
                      onReset={handleReset}
                      isLoading={isDetecting}
                    />
                  </div>

                  {/* ── Sección: Método ── */}
                  <div className="px-4 py-4 border-b border-white/5">
                    <SectionLabel step={2} label="Método" done={!!method} />
                    <MethodSelector method={method} onMethodChange={setMethod} fileType={fileType} />
                  </div>

                  {/* ── Sección: Parámetros (video / pptx) ── */}
                  {(fileType === "video" || fileType === "pptx") && (
                    <div className="px-4 py-4 border-b border-white/5">
                      <SectionLabel step={3} label={fileType === "video" ? "Recorte final" : "Configuración"} done={!!region} />
                      <ParameterControls
                        trimSeconds={trimSeconds}
                        onTrimChange={setTrimSeconds}
                        fileType={fileType}
                      />
                    </div>
                  )}

                  {/* ── CTA ── */}
                  <div className="px-4 py-4 space-y-2.5">
                    <button
                      onClick={handleAddToQueue}
                      disabled={!region}
                      className="relative w-full py-3.5 rounded-xl font-semibold text-sm overflow-hidden group disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-ctp-mauve to-ctp-blue transition-opacity group-hover:opacity-85" />
                      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity"
                        style={{ background: "radial-gradient(ellipse at center, rgba(203,166,247,0.4) 0%, transparent 70%)" }} />
                      <span className="relative flex items-center justify-center gap-2 text-white tracking-wide">
                        <Play size={15} strokeWidth={2.5} />
                        Procesar Archivo
                      </span>
                    </button>

                    <button onClick={handleNewFile}
                      className="w-full py-2.5 rounded-xl text-xs text-ctp-overlay0 hover:text-ctp-subtext0 hover:bg-ctp-surface0/40 border border-white/5 transition-all">
                      Cargar otro archivo
                    </button>
                  </div>

                </div>
              </div>
            </div>

            {/* ── Queue ── */}
            {queue.length > 0 && (
              <div className="mt-6">
                <BatchQueue queue={queue} onCancel={handleCancel} onRemove={handleRemove} onDownload={handleDownload} />
              </div>
            )}
          </motion.div>
        )}
      </main>
    </div>
  );
}
