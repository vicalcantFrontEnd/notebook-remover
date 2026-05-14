"use client";
import { useState, useEffect, useRef } from "react";

export function useETA(progress: number, isProcessing: boolean) {
  const [eta, setEta] = useState<string>("");
  const startTimeRef = useRef<number>(0);
  const lastProgressRef = useRef<number>(0);

  useEffect(() => {
    if (isProcessing && progress > 0 && startTimeRef.current === 0) {
      startTimeRef.current = Date.now();
      lastProgressRef.current = progress;
    }
    if (!isProcessing) {
      startTimeRef.current = 0;
      lastProgressRef.current = 0;
      setEta("");
      return;
    }
    if (progress <= 0 || progress >= 100) {
      setEta(progress >= 100 ? "Listo!" : "");
      return;
    }
    const elapsed = (Date.now() - startTimeRef.current) / 1000;
    if (elapsed < 2) return;
    const rate = progress / elapsed;
    const remaining = (100 - progress) / rate;
    if (remaining < 60) setEta(`${Math.ceil(remaining)}s restante`);
    else setEta(`${Math.ceil(remaining / 60)}m restante`);
  }, [progress, isProcessing]);

  return eta;
}
