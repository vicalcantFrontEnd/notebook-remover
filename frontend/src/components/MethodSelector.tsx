"use client";
import { motion } from "framer-motion";
import { ScanSearch, Grid3x3, Crop, Delete, Sparkles, Check } from "lucide-react";
import type { RemovalMethod, FileType } from "@/lib/types";
import { METHODS_BY_TYPE } from "@/lib/constants";

const METHOD_META: Record<RemovalMethod, { label: string; desc: string; icon: React.ReactNode }> = {
  lama: {
    label: "LaMa IA",
    desc: "Inpainting con inteligencia artificial. Mejor calidad, rellena con contexto real.",
    icon: <Sparkles size={18} strokeWidth={1.8} />,
  },
  pixel: {
    label: "Máscara Pixel",
    desc: "Detecta y elimina sólo los píxeles de la marca. Mejor calidad.",
    icon: <ScanSearch size={18} strokeWidth={1.8} />,
  },
  box: {
    label: "Inpaint Caja",
    desc: "Rellena toda la región rectangular. Rápido y confiable.",
    icon: <Grid3x3 size={18} strokeWidth={1.8} />,
  },
  crop: {
    label: "Recortar y Zoom",
    desc: "Recorta la esquina con la marca y reescala el resultado.",
    icon: <Crop size={18} strokeWidth={1.8} />,
  },
  delete_shapes: {
    label: "Eliminar Elementos",
    desc: "Elimina shapes del área seleccionada. Preserva formato editable.",
    icon: <Delete size={18} strokeWidth={1.8} />,
  },
};

interface MethodSelectorProps {
  method: RemovalMethod;
  onMethodChange: (m: RemovalMethod) => void;
  fileType?: FileType;
}

export default function MethodSelector({ method, onMethodChange, fileType = "video" }: MethodSelectorProps) {
  const allowed = METHODS_BY_TYPE[fileType] ?? METHODS_BY_TYPE.video;
  const methods = (Object.keys(METHOD_META) as RemovalMethod[]).filter(m => allowed.includes(m));

  return (
    <div className="grid grid-cols-1 gap-2">
      {methods.map((m) => {
        const meta = METHOD_META[m];
        const active = method === m;
        return (
          <motion.button key={m} onClick={() => onMethodChange(m)} whileTap={{ scale: 0.98 }}
            className={`relative flex items-start gap-3 p-3.5 rounded-xl border text-left transition-all duration-200 ${
              active
                ? "border-ctp-mauve/40 bg-gradient-to-r from-ctp-mauve/10 to-ctp-blue/8"
                : "border-white/5 bg-ctp-surface0/20 hover:bg-ctp-surface0/40 hover:border-white/10"
            }`}>
            {active && (
              <motion.div layoutId="method-glow" className="absolute inset-0 rounded-xl border border-ctp-mauve/30" transition={{ type: "spring", duration: 0.4 }} />
            )}
            <span className={`mt-0.5 shrink-0 transition-colors ${active ? "text-ctp-mauve" : "text-ctp-overlay1"}`}>
              {meta.icon}
            </span>
            <div className="min-w-0">
              <p className={`text-sm font-semibold ${active ? "text-ctp-text" : "text-ctp-subtext1"}`}>{meta.label}</p>
              <p className="text-[11px] text-ctp-overlay0 mt-0.5 leading-relaxed">{meta.desc}</p>
            </div>
            {active && (
              <div className="ml-auto shrink-0 w-4 h-4 rounded-full bg-gradient-to-br from-ctp-mauve to-ctp-blue flex items-center justify-center">
                <Check size={8} className="text-white" strokeWidth={3.5} />
              </div>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}
