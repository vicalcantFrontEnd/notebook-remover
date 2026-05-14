"use client";
import { useState, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Zap, Target, Unlock, FileText, AlertCircle } from "lucide-react";
import { ALLOWED_MIME_TYPES, ALLOWED_FORMATS, FILE_ACCEPT } from "@/lib/constants";

const FORMAT_BADGES = [
  { label: "MP4",  cls: "text-ctp-blue   bg-ctp-blue/10   border-ctp-blue/20"   },
  { label: "MKV",  cls: "text-ctp-blue   bg-ctp-blue/10   border-ctp-blue/20"   },
  { label: "MOV",  cls: "text-ctp-blue   bg-ctp-blue/10   border-ctp-blue/20"   },
  { label: "JPG",  cls: "text-ctp-peach  bg-ctp-peach/10  border-ctp-peach/20"  },
  { label: "PNG",  cls: "text-ctp-peach  bg-ctp-peach/10  border-ctp-peach/20"  },
  { label: "WebP", cls: "text-ctp-peach  bg-ctp-peach/10  border-ctp-peach/20"  },
  { label: "PDF",  cls: "text-ctp-red    bg-ctp-red/10    border-ctp-red/20"    },
  { label: "PPTX", cls: "text-ctp-mauve  bg-ctp-mauve/10  border-ctp-mauve/20"  },
];

const FEATURES = [
  { label: "Procesado rápido",       icon: <Zap size={13} /> },
  { label: "Precisión pixel a pixel", icon: <Target size={13} /> },
  { label: "Sin límite de tamaño",    icon: <Unlock size={13} /> },
  { label: "Múltiples formatos",      icon: <FileText size={13} /> },
];

interface DropZoneProps {
  onFileSelected: (file: File) => void;
  isUploading: boolean;
}

export default function DropZone({ onFileSelected, isUploading }: DropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSelect = useCallback((file: File) => {
    setError(null);
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
    if (!ALLOWED_MIME_TYPES.includes(file.type) && !ALLOWED_FORMATS.includes(ext)) {
      setError("Formato no soportado. Usa video, imagen (JPG/PNG/WebP), PDF o PPTX.");
      return;
    }
    onFileSelected(file);
  }, [onFileSelected]);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) validateAndSelect(file);
  }, [validateAndSelect]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-65px)] px-4 py-16">

      {/* ── Hero ── */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-10">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.05 }}
          className="inline-flex items-center gap-2 bg-ctp-surface0/50 border border-white/8 rounded-full px-4 py-1.5 mb-6"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-ctp-mauve animate-pulse" />
          <span className="text-xs text-ctp-subtext0 font-medium tracking-wide">Potenciado por IA</span>
        </motion.div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight leading-tight mb-4">
          <span className="text-ctp-text">Elimina Marcas</span>
          <br />
          <span className="bg-gradient-to-r from-ctp-mauve via-ctp-blue to-ctp-lavender bg-clip-text text-transparent">
            de Agua al Instante
          </span>
        </h1>
        <p className="text-ctp-subtext0 text-base max-w-md mx-auto leading-relaxed">
          Sube tu archivo y elimina marcas de agua con precisión — videos, imágenes, PDFs y presentaciones.
        </p>
      </motion.div>

      {/* ── Upload zone ── */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="w-full max-w-xl">
        <motion.div
          onDrop={onDrop}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onClick={() => !isUploading && inputRef.current?.click()}
          animate={{ scale: isDragOver ? 1.012 : 1 }}
          transition={{ type: "spring", stiffness: 400, damping: 30 }}
          className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-colors duration-200 ${
            isDragOver
              ? "border-ctp-mauve/70 bg-ctp-mauve/5"
              : "border-ctp-surface1/60 bg-ctp-surface0/10 hover:border-ctp-surface2/70 hover:bg-ctp-surface0/20"
          }`}
        >
          <input ref={inputRef} type="file" accept={FILE_ACCEPT} className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) validateAndSelect(f); }} />

          <AnimatePresence mode="wait">
            {isUploading ? (
              <motion.div key="uploading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="relative w-14 h-14 mx-auto mb-4">
                  <div className="absolute inset-0 rounded-full border-2 border-ctp-surface1" />
                  <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-ctp-mauve border-r-ctp-blue animate-spin" />
                  <div className="absolute inset-2 rounded-full bg-ctp-surface0/50 flex items-center justify-center">
                    <Upload size={16} className="text-ctp-mauve" strokeWidth={2} />
                  </div>
                </div>
                <p className="text-ctp-text font-semibold mb-1">Analizando archivo…</p>
                <p className="text-sm text-ctp-subtext0">Detectando marca de agua automáticamente</p>
              </motion.div>
            ) : (
              <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className={`w-16 h-16 mx-auto mb-5 rounded-2xl flex items-center justify-center transition-colors ${
                  isDragOver ? "bg-ctp-mauve/20" : "bg-ctp-surface0/60"
                }`}>
                  <Upload size={32} className={isDragOver ? "text-ctp-mauve" : "text-ctp-overlay1"} strokeWidth={1.5} />
                </div>
                {isDragOver ? (
                  <p className="text-ctp-mauve font-bold text-lg">Suelta para subir</p>
                ) : (
                  <>
                    <p className="text-ctp-text font-semibold text-lg mb-1.5">Arrastra tu archivo aquí</p>
                    <p className="text-sm text-ctp-subtext0">
                      o{" "}
                      <span className="text-ctp-blue hover:text-ctp-lavender transition-colors underline underline-offset-2 cursor-pointer">
                        haz clic para buscar
                      </span>
                    </p>
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Format badges */}
        <div className="flex flex-wrap justify-center gap-1.5 mt-4">
          {FORMAT_BADGES.map(({ label, cls }) => (
            <span key={label} className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${cls}`}>{label}</span>
          ))}
        </div>

        <AnimatePresence>
          {error && (
            <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="mt-3 flex items-center gap-2 text-sm text-ctp-red bg-ctp-red/10 border border-ctp-red/20 px-4 py-3 rounded-xl">
              <AlertCircle size={14} className="shrink-0" />
              {error}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* ── Feature row ── */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}
        className="flex flex-wrap justify-center gap-5 mt-8">
        {FEATURES.map(({ label, icon }) => (
          <span key={label} className="flex items-center gap-1.5 text-xs text-ctp-overlay1">
            <span className="text-ctp-overlay0">{icon}</span>
            {label}
          </span>
        ))}
      </motion.div>
    </div>
  );
}
