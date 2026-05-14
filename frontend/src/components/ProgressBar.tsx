"use client";
import { motion } from "framer-motion";

interface ProgressBarProps {
  progress: number;
  isProcessing: boolean;
  eta?: string;
}

export default function ProgressBar({ progress, isProcessing, eta }: ProgressBarProps) {
  const isComplete = progress >= 100;

  return (
    <div className="space-y-1.5">
      <div className={`${isProcessing ? "h-3" : "h-2"} bg-ctp-surface0 rounded-full overflow-hidden transition-all`}>
        <motion.div
          className="h-full rounded-full relative"
          style={{
            background: isComplete
              ? "#a6e3a1"
              : "linear-gradient(90deg, #89b4fa, #b4befe, #cba6f7)",
          }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(progress, 100)}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        >
          {isProcessing && !isComplete && (
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/25 to-transparent animate-[shimmer_1.5s_infinite]" />
          )}
        </motion.div>
      </div>
      <div className="flex justify-between items-center">
        <span className={`text-xs tabular-nums ${isProcessing ? "text-ctp-blue font-medium" : "text-ctp-overlay0"}`}>
          {Math.round(progress)}%
        </span>
        {eta && isProcessing && (
          <span className="text-xs text-ctp-overlay0">{eta}</span>
        )}
      </div>
    </div>
  );
}
