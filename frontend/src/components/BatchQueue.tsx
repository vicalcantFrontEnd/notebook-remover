"use client";
import { motion, AnimatePresence } from "framer-motion";
import { List } from "lucide-react";
import type { QueueItem } from "@/hooks/useBatchQueue";
import BatchQueueItem from "./BatchQueueItem";

interface BatchQueueProps {
  queue: QueueItem[];
  onCancel: (id: string) => void;
  onRemove: (id: string) => void;
  onDownload: (jobId: string) => void;
}

export default function BatchQueue({ queue, onCancel, onRemove, onDownload }: BatchQueueProps) {
  if (queue.length === 0) return null;

  const completed  = queue.filter(i => i.status === "completed").length;
  const processing = queue.filter(i => i.status === "processing").length;

  return (
    <motion.section initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
      <div className="rounded-2xl border border-white/5 bg-ctp-mantle/60 backdrop-blur-sm overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-lg bg-ctp-surface0/80 flex items-center justify-center">
              <List size={13} className="text-ctp-subtext0" />
            </div>
            <h2 className="text-sm font-semibold text-ctp-text">Cola de procesamiento</h2>
          </div>
          <div className="flex items-center gap-2 text-xs">
            {processing > 0 && (
              <span className="flex items-center gap-1.5 text-ctp-blue bg-ctp-blue/10 border border-ctp-blue/20 px-2.5 py-1 rounded-full font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-ctp-blue animate-pulse" />
                {processing} procesando
              </span>
            )}
            <span className="text-ctp-overlay0">{completed}/{queue.length} completados</span>
          </div>
        </div>

        {/* Items */}
        <div className="p-4 space-y-3">
          <AnimatePresence>
            {queue.map((item) => (
              <BatchQueueItem key={item.id} item={item} onCancel={onCancel} onRemove={onRemove} onDownload={onDownload} />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </motion.section>
  );
}
