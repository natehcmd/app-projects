/**
 * useConductorSocket — the UI's single connection to the daemon.
 * ---------------------------------------------------------------------------
 *  - keeps the latest SERVER_STATE_UPDATE.data in React state
 *  - auto-reconnects with capped backoff
 *  - correlates COMMAND_EXEC_OK / COMMAND_EXEC_ERROR back to the promise
 *    returned by prune / focus / resolveConflict / resetSentinel
 *  - multiplexes TERMINAL_DATA to per-surface subscribers
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  ClientMessage,
  CommandExecOk,
  KillSignal,
  ServerMessage,
  ServerStateUpdate,
} from '../shared/types.js';

const DEFAULT_URL =
  (import.meta.env.VITE_CONDUCTOR_WS as string | undefined) ?? 'ws://127.0.0.1:8787';

type SnapshotData = ServerStateUpdate['data'];
type TerminalListener = (chunk: string) => void;

export interface ConductorApi {
  connected: boolean;
  snapshot: SnapshotData | null;
  lastUpdate: string | null;
  pruneSurface(surfaceId: string, signal?: KillSignal): Promise<CommandExecOk['result']>;
  focusSurface(surfaceId: string): Promise<CommandExecOk['result']>;
  resolveConflict(
    keepSurfaceId: string,
    pruneSurfaceIds: string[],
    signal?: KillSignal,
  ): Promise<CommandExecOk['result']>;
  resetSentinel(): Promise<CommandExecOk['result']>;
  /** Subscribe to a surface's live terminal stream. Returns an unsubscribe fn. */
  subscribeTerminal(surfaceId: string, listener: TerminalListener): () => void;
}

interface Pending {
  resolve: (result: CommandExecOk['result']) => void;
  reject: (err: Error) => void;
}

export function useConductorSocket(url: string = DEFAULT_URL): ConductorApi {
  const [connected, setConnected] = useState(false);
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pendingRef = useRef(new Map<string, Pending>());
  const terminalSubsRef = useRef(new Map<string, Set<TerminalListener>>());
  const backoffRef = useRef(1000);
  const closedRef = useRef(false);

  const send = useCallback((msg: ClientMessage): void => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) throw new Error('daemon socket not open');
    ws.send(JSON.stringify(msg));
  }, []);

  const request = useCallback(
    (build: (requestId: string) => ClientMessage): Promise<CommandExecOk['result']> => {
      const requestId = `ui_${Math.random().toString(36).slice(2, 11)}`;
      return new Promise((resolve, reject) => {
        pendingRef.current.set(requestId, { resolve, reject });
        try {
          send(build(requestId));
        } catch (err) {
          pendingRef.current.delete(requestId);
          reject(err as Error);
          return;
        }
        // Safety timeout so a lost ack doesn't hang the UI forever.
        setTimeout(() => {
          if (pendingRef.current.has(requestId)) {
            pendingRef.current.delete(requestId);
            reject(new Error('daemon did not acknowledge in time'));
          }
        }, 8000);
      });
    },
    [send],
  );

  // --- connection lifecycle -------------------------------------------
  useEffect(() => {
    closedRef.current = false;

    const connect = (): void => {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        backoffRef.current = 1000;
        // Re-arm any terminal subscriptions that survived a reconnect.
        for (const surfaceId of terminalSubsRef.current.keys()) {
          ws.send(
            JSON.stringify({
              type: 'TERMINAL_SUBSCRIBE',
              requestId: `ui_resub_${surfaceId}`,
              params: { surfaceId, subscribe: true },
            } satisfies ClientMessage),
          );
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (closedRef.current) return;
        const delay = backoffRef.current;
        backoffRef.current = Math.min(delay * 2, 16000);
        setTimeout(connect, delay);
      };

      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        let msg: ServerMessage;
        try {
          msg = JSON.parse(event.data as string) as ServerMessage;
        } catch {
          return;
        }
        switch (msg.type) {
          case 'SERVER_STATE_UPDATE':
            setSnapshot(msg.data);
            setLastUpdate(msg.timestamp);
            break;
          case 'COMMAND_EXEC_OK': {
            const p = pendingRef.current.get(msg.requestId);
            if (p) {
              pendingRef.current.delete(msg.requestId);
              p.resolve(msg.result);
            }
            break;
          }
          case 'COMMAND_EXEC_ERROR': {
            const p = pendingRef.current.get(msg.requestId);
            if (p) {
              pendingRef.current.delete(msg.requestId);
              p.reject(new Error(msg.error));
            }
            break;
          }
          case 'TERMINAL_DATA': {
            const listeners = terminalSubsRef.current.get(msg.surfaceId);
            if (listeners) for (const l of listeners) l(msg.chunk);
            break;
          }
        }
      };
    };

    connect();
    return () => {
      closedRef.current = true;
      wsRef.current?.close();
    };
  }, [url]);

  // --- public API ---------------------------------------------------
  const pruneSurface = useCallback(
    (surfaceId: string, signal: KillSignal = 'SIGTERM') =>
      request((requestId) => ({
        type: 'PRUNE_SURF_REQUEST',
        requestId,
        params: { surfaceId, signal },
      })),
    [request],
  );

  const focusSurface = useCallback(
    (surfaceId: string) =>
      request((requestId) => ({
        type: 'FOCUS_SURF_REQUEST',
        requestId,
        params: { surfaceId },
      })),
    [request],
  );

  const resolveConflict = useCallback(
    (keepSurfaceId: string, pruneSurfaceIds: string[], signal: KillSignal = 'SIGTERM') =>
      request((requestId) => ({
        type: 'RESOLVE_CONFLICT_REQUEST',
        requestId,
        params: { keepSurfaceId, pruneSurfaceIds, signal },
      })),
    [request],
  );

  const resetSentinel = useCallback(
    () => request((requestId) => ({ type: 'RESET_SENTINEL_REQUEST', requestId })),
    [request],
  );

  const subscribeTerminal = useCallback(
    (surfaceId: string, listener: TerminalListener): (() => void) => {
      let set = terminalSubsRef.current.get(surfaceId);
      const isFirst = !set;
      if (!set) {
        set = new Set();
        terminalSubsRef.current.set(surfaceId, set);
      }
      set.add(listener);

      if (isFirst && wsRef.current?.readyState === WebSocket.OPEN) {
        void request((requestId) => ({
          type: 'TERMINAL_SUBSCRIBE',
          requestId,
          params: { surfaceId, subscribe: true },
        })).catch(() => undefined);
      }

      return () => {
        const current = terminalSubsRef.current.get(surfaceId);
        if (!current) return;
        current.delete(listener);
        if (current.size === 0) {
          terminalSubsRef.current.delete(surfaceId);
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            void request((requestId) => ({
              type: 'TERMINAL_SUBSCRIBE',
              requestId,
              params: { surfaceId, subscribe: false },
            })).catch(() => undefined);
          }
        }
      };
    },
    [request],
  );

  return {
    connected,
    snapshot,
    lastUpdate,
    pruneSurface,
    focusSurface,
    resolveConflict,
    resetSentinel,
    subscribeTerminal,
  };
}
