import { useEffect, useRef, useState, useCallback } from 'react';

interface RealtimeData {
  type: string;
  total_bytes_per_sec: number;
  total_bytes: number;
  tasks: Array<{ task_id: number; speed: number }>;
}

export function useWebSocket() {
  const [data, setData] = useState<RealtimeData | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/realtime`);

    ws.onopen = () => setConnected(true);
    ws.onmessage = (e) => {
      try {
        setData(JSON.parse(e.data));
      } catch {}
    };
    ws.onclose = () => {
      setConnected(false);
      setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  return { data, connected };
}
