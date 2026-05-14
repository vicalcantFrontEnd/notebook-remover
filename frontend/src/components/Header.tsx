"use client";
import { motion } from "framer-motion";
import { ShieldCheck, Wifi } from "lucide-react";

export default function Header() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      className="sticky top-0 z-50 flex items-center justify-between px-6 py-3.5 border-b border-white/5 bg-ctp-crust/80 backdrop-blur-xl"
    >
      <div className="flex items-center gap-3">
        <div className="relative w-8 h-8 rounded-xl overflow-hidden shrink-0">
          <div className="absolute inset-0 bg-gradient-to-br from-ctp-mauve to-ctp-blue" />
          <div className="absolute inset-0 flex items-center justify-center">
            <ShieldCheck size={16} className="text-white" strokeWidth={2.5} />
          </div>
        </div>
        <div className="leading-none">
          <span className="text-base font-bold tracking-tight">
            <span className="bg-gradient-to-r from-ctp-mauve to-ctp-blue bg-clip-text text-transparent">Clear</span>
            <span className="text-ctp-text">Mark</span>
          </span>
          <p className="text-[10px] text-ctp-overlay0 mt-0.5">AI Watermark Remover</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="hidden sm:flex items-center gap-1.5 text-[11px] text-ctp-green bg-ctp-green/10 border border-ctp-green/20 px-2.5 py-1 rounded-full font-medium">
          <Wifi size={11} className="text-ctp-green" strokeWidth={2.5} />
          Online
        </span>
      </div>
    </motion.header>
  );
}
