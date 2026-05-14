"use client";
import { useEffect, useRef, useCallback, useState } from "react";
import type { ProgressMessage } from "@/lib/types";
import { getWebSocketUrl } from "@/lib/api";

export function useWebSocket(jobId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<ProgressMessage | null>(null);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (!jobId) return;
    const ws = new WebSocket(getWebSocketUrl(jobId));
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      // Reconnect after 2s if not intentional
      setTimeout(() => {
        if (wsRef.current === ws) connect();
      }, 2000);
    };
    ws.onmessage = (event) => {
      try {
        const msg: ProgressMessage = JSON.parse(event.data);
        setLastMessage(msg);
      } catch {}
    };
    ws.onerror = () => ws.close();
  }, [jobId]);

  useEffect(() => {
    connect();
    return () => {
      const ws = wsRef.current;
      wsRef.current = null;
      ws?.close();
    };
  }, [connect]);

  const disconnect = useCallback(() => {
    const ws = wsRef.current;
    wsRef.current = null;
    ws?.close();
  }, []);

  return { lastMessage, connected, disconnect };
}
