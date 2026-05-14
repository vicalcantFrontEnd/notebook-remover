"use client";
import { motion, AnimatePresence } from "framer-motion";
import { Check, ScanSearch, Loader2, RotateCcw } from "lucide-react";
import type { Region } from "@/lib/types";

interface RegionSelectorProps {
  region: Region | null;
  onAutoDetect: () => void;
  onReset: () => void;
  isLoading: boolean;
}

export default function RegionSelector({ region, onAutoDetect, onReset, isLoading }: RegionSelectorProps) {
  return (
    <div className="space-y-3">
      <AnimatePresence mode="wait">
        {!region ? (
          <motion.p key="hint" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="text-xs text-ctp-overlay0 bg-ctp-surface0/40 rounded-xl px-3 py-2.5 border border-white/5">
            Dibuja en el preview o usa <strong className="text-ctp-subtext0">Auto-detectar</strong> para encontrar la marca automáticamente.
          </motion.p>
        ) : (
          <motion.div key="region-info" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-2 text-xs bg-ctp-green/8 border border-ctp-green/20 rounded-xl px-3 py-2.5">
            <Check size={13} className="text-ctp-green" strokeWidth={2.5} />
            <span className="text-ctp-green font-medium">Área seleccionada:</span>
            <span className="text-ctp-subtext0 font-mono">{region.w}×{region.h}px</span>
            <span className="text-ctp-overlay0">en ({region.x},{region.y})</span>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-wrap gap-2">
        <button onClick={onAutoDetect} disabled={isLoading}
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-ctp-blue/15 hover:bg-ctp-blue/25 text-ctp-blue border border-ctp-blue/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
          {isLoading ? (
            <Loader2 size={12} className="animate-spin" strokeWidth={2.5} />
          ) : (
            <ScanSearch size={12} strokeWidth={2.5} />
          )}
          {isLoading ? "Detectando…" : "Auto-detectar"}
        </button>

        {region && (
          <button onClick={onReset}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold bg-ctp-surface0/50 hover:bg-ctp-surface0/80 text-ctp-subtext0 hover:text-ctp-text border border-white/5 transition-all">
            <RotateCcw size={12} strokeWidth={2.5} />
            Borrar área
          </button>
        )}
      </div>
    </div>
  );
}
