"use client";
import { Info } from "lucide-react";
import type { FileType } from "@/lib/types";

interface ParameterControlsProps {
  trimSeconds: number;
  onTrimChange: (v: number) => void;
  fileType?: FileType;
}

export default function ParameterControls({
  trimSeconds, onTrimChange, fileType = "video",
}: ParameterControlsProps) {
  if (fileType === "pptx") {
    return (
      <div className="flex items-center gap-2 text-xs text-ctp-overlay0 bg-ctp-surface0/30 rounded-xl px-3 py-3 border border-white/5">
        <Info size={13} />
        Los elementos en el área serán eliminados de todas las diapositivas.
      </div>
    );
  }

  if (fileType !== "video") return null;

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <span className="text-xs font-semibold text-ctp-subtext1">Recortar Final</span>
        <span className="text-[10px] text-ctp-overlay0">(remover intro/outro)</span>
      </div>
      <div className="flex items-center gap-3">
        <input
          type="number"
          min={0}
          step={0.5}
          value={trimSeconds === 0 ? "" : trimSeconds}
          onChange={(e) => onTrimChange(e.target.value === "" ? 0 : Math.max(0, Number(e.target.value)))}
          placeholder="0"
          className="w-28 px-3 py-2 rounded-xl text-sm font-mono text-ctp-text bg-ctp-surface0/50 border border-white/10 focus:outline-none focus:border-ctp-mauve/50 transition-colors"
        />
        <span className="text-xs text-ctp-overlay1">segundos</span>
      </div>
    </div>
  );
}
