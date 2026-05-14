"use client";
import { useState, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { Eye, ChevronsLeftRight } from "lucide-react";

interface BeforeAfterSliderProps {
  beforeBase64: string;
  afterBase64: string;
}

export default function BeforeAfterSlider({ beforeBase64, afterBase64 }: BeforeAfterSliderProps) {
  const [position, setPosition] = useState(50);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMove = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setPosition(Math.max(2, Math.min(98, ((clientX - rect.left) / rect.width) * 100)));
  }, []);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    handleMove(e.clientX);
  }, [handleMove]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (e.buttons === 0) return;
    handleMove(e.clientX);
  }, [handleMove]);

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="px-6 pb-5 pt-3">
      <div className="flex items-center gap-2 mb-3">
        <Eye size={13} className="text-ctp-mauve" />
        <span className="text-xs font-semibold text-ctp-subtext1">Comparación Antes / Después</span>
      </div>

      <div ref={containerRef}
        className="relative w-full rounded-xl overflow-hidden border border-white/5 select-none touch-none"
        style={{ height: "clamp(160px, 28vh, 300px)", cursor: "col-resize" }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
      >
        <img src={`data:image/jpeg;base64,${beforeBase64}`} alt="Antes"
          className="absolute inset-0 w-full h-full object-contain bg-ctp-mantle" draggable={false} />

        <div className="absolute inset-0 overflow-hidden" style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}>
          <img src={`data:image/jpeg;base64,${afterBase64}`} alt="Después"
            className="w-full h-full object-contain bg-ctp-mantle" draggable={false} />
        </div>

        {/* Divider line */}
        <div className="absolute top-0 bottom-0 w-px pointer-events-none"
          style={{ left: `${position}%`, background: "rgba(255,255,255,0.7)" }}>
          {/* Handle */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/95 shadow-2xl flex items-center justify-center pointer-events-none">
            <ChevronsLeftRight size={14} className="text-ctp-base" strokeWidth={2.2} />
          </div>
        </div>

        <span className="absolute top-2 left-2 text-[10px] font-semibold bg-black/60 text-white px-2 py-0.5 rounded-md backdrop-blur-sm">ANTES</span>
        <span className="absolute top-2 right-2 text-[10px] font-semibold bg-ctp-mauve/80 text-white px-2 py-0.5 rounded-md backdrop-blur-sm">DESPUÉS</span>
      </div>
    </motion.div>
  );
}
