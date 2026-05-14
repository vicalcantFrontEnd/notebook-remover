"use client";
import { motion } from "framer-motion";
import { Download } from "lucide-react";
import type { QueueItem } from "@/hooks/useBatchQueue";
import ProgressBar from "./ProgressBar";
import { useETA } from "@/hooks/useETA";

interface BatchQueueItemProps {
  item: QueueItem;
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
  onDownload: (jobId: string) => void;
}

const STATUS_CFG = {
  pending:    { dot: "bg-ctp-overlay0",  label: "Pendiente",  labelCls: "text-ctp-overlay0"  },
  queued:     { dot: "bg-ctp-yellow",    label: "En cola",    labelCls: "text-ctp-yellow"    },
  processing: { dot: "bg-ctp-blue animate-pulse", label: "Procesando", labelCls: "text-ctp-blue" },
  completed:  { dot: "bg-ctp-green",     label: "Completado", labelCls: "text-ctp-green"     },
  failed:     { dot: "bg-ctp-red",       label: "Error",      labelCls: "text-ctp-red"       },
  cancelled:  { dot: "bg-ctp-overlay0",  label: "Cancelado",  labelCls: "text-ctp-overlay0"  },
} as const;

export default function BatchQueueItem({ item, onCancel, onRemove, onDownload }: BatchQueueItemProps) {
  const eta = useETA(item.progress, item.status === "processing");
  const isActive = item.status === "processing";
  const cfg = STATUS_CFG[item.status as keyof typeof STATUS_CFG] ?? STATUS_CFG.pending;

  return (
    <motion.div layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0, marginBottom: 0 }}
      className={`rounded-xl border p-4 transition-all ${
        isActive  ? "border-ctp-blue/25 bg-ctp-blue/5" :
        item.status === "completed" ? "border-ctp-green/20 bg-ctp-green/5" :
        item.status === "failed"    ? "border-ctp-red/20  bg-ctp-red/5"    :
        "border-white/5 bg-ctp-surface0/20"
      }`}>

      <div className="flex items-center gap-3 mb-3">
        <span className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
        <span className="text-sm text-ctp-text font-medium truncate flex-1">{item.filename}</span>
        <span className={`text-[11px] font-semibold shrink-0 ${cfg.labelCls}`}>{cfg.label}</span>
      </div>

      {isActive && (
        <div className="space-y-2 mb-3">
          <ProgressBar progress={item.progress} isProcessing eta={eta} />
          {item.totalFrames > 0 && (
            <div className="flex justify-between text-[11px] text-ctp-overlay0">
              <span>Cuadro {item.currentFrame} / {item.totalFrames}</span>
              {eta && <span>{eta}</span>}
            </div>
          )}
        </div>
      )}

      {item.status === "queued" && <ProgressBar progress={0} isProcessing={false} />}
      {item.error && <p className="text-xs text-ctp-red mb-2">{item.error}</p>}

      <div className="flex items-center gap-2 justify-end">
        {item.status === "processing" && (
          <button onClick={() => onCancel(item.id)}
            className="text-xs px-3 py-1.5 rounded-lg bg-ctp-red/10 hover:bg-ctp-red/20 text-ctp-red border border-ctp-red/20 transition-colors font-medium">
            Cancelar
          </button>
        )}
        {item.status === "completed" && item.jobId && (
          <button onClick={() => onDownload(item.jobId!)}
            className="relative text-xs px-4 py-1.5 rounded-lg overflow-hidden font-semibold transition-opacity hover:opacity-90">
            <div className="absolute inset-0 bg-gradient-to-r from-ctp-mauve to-ctp-blue" />
            <span className="relative text-white flex items-center gap-1.5">
              <Download size={11} strokeWidth={2.5} />
              Descargar
            </span>
          </button>
        )}
        {["completed","failed","cancelled","pending"].includes(item.status) && (
          <button onClick={() => onRemove(item.id)}
            className="text-xs px-3 py-1.5 rounded-lg bg-ctp-surface0/50 hover:bg-ctp-surface0/80 text-ctp-overlay0 hover:text-ctp-subtext0 border border-white/5 transition-colors">
            Eliminar
          </button>
        )}
      </div>
    </motion.div>
  );
}
