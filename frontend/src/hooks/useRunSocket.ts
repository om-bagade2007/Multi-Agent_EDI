import { useEffect, useReducer } from 'react';
import { applyMessage, initialState } from '../lib/reducer';
import type { Message } from '../types';
export function useRunSocket(runId: string | null) {
  const [state, dispatch] = useReducer(applyMessage, initialState);
  useEffect(() => {
    if (!runId) return;
    let socket: WebSocket;
    let retry: number;
    let disposed = false;
    const connect = () => {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${protocol}//${location.host}/ws/runs/${runId}`);
      socket.onmessage = event => dispatch(JSON.parse(event.data) as Message);
      socket.onclose = () => { if (!disposed) retry = window.setTimeout(connect, 1000); };
    };
    connect();
    return () => { disposed = true; clearTimeout(retry); socket?.close(); };
  }, [runId]);
  return state;
}
