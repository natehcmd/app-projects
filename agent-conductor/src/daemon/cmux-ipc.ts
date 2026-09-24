/**
 * cmux Socket IPC Engine  (spec §1)
 * ---------------------------------------------------------------------------
 * `cmux` is a native AppKit/Swift macOS terminal for AI agents. It exposes a
 * Unix Domain Socket (default `/tmp/cmux.sock`, `/tmp/cmux-debug.sock` for debug
 * builds) that speaks newline-terminated JSON-RPC.
 *
 * This client is deliberately resilient because the daemon is long-lived and
 * cmux can be quit / relaunched underneath it at any time:
 *   - exponential backoff reconnect (1s -> 16s cap), reset on a clean connect
 *   - a partial-frame buffer (`\n` delimited), so a TCP read that splits a JSON
 *     object mid-way is reassembled correctly
 *   - per-request correlation map with a timeout, so a dropped reply rejects
 *     the caller instead of leaking the promise forever
 *   - never throws asynchronously: transport errors surface as `error` events
 *     and as rejections on the specific `send()` promise
 */

import * as net from 'node:net';
import { EventEmitter } from 'node:events';

export interface JSONRPCRequest {
  id: string;
  method: string;
  params?: Record<string, unknown>;
}

export interface JSONRPCResponse {
  id: string;
  ok: boolean;
  result?: unknown;
  error?: string;
}

export interface CmuxIPCOptions {
  socketPath?: string;
  /** Reject a pending request if cmux does not answer within this window. */
  requestTimeoutMs?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
}

type PendingResolver = {
  resolve: (result: unknown) => void;
  reject: (err: Error) => void;
  timer: NodeJS.Timeout;
};

export declare interface CmuxIPCClient {
  on(event: 'connect', listener: () => void): this;
  on(event: 'disconnect', listener: () => void): this;
  on(event: 'reconnecting', listener: (delayMs: number) => void): this;
  on(event: 'error', listener: (err: Error) => void): this;
  on(event: 'parse_error', listener: (err: unknown, raw: string) => void): this;
  /** Unsolicited server->client notifications (no matching request id). */
  on(event: 'message', listener: (msg: JSONRPCResponse) => void): this;
}

export class CmuxIPCClient extends EventEmitter {
  private readonly socketPath: string;
  private readonly requestTimeoutMs: number;
  private readonly initialBackoffMs: number;
  private readonly maxBackoffMs: number;

  private socket: net.Socket | null = null;
  private backoffMs: number;
  private connected = false;
  private disposed = false;
  private reconnectTimer: NodeJS.Timeout | null = null;
  /** True once we've emitted `reconnecting` for the current down period. */
  private reconnectAnnounced = false;

  private readonly pending = new Map<string, PendingResolver>();
  private buffer = '';

  constructor(options: CmuxIPCOptions = {}) {
    super();
    this.socketPath =
      options.socketPath || process.env.CMUX_SOCKET_PATH || '/tmp/cmux.sock';
    this.requestTimeoutMs = options.requestTimeoutMs ?? 5_000;
    this.initialBackoffMs = options.initialBackoffMs ?? 1_000;
    this.maxBackoffMs = options.maxBackoffMs ?? 16_000;
    this.backoffMs = this.initialBackoffMs;
  }

  get isConnected(): boolean {
    return this.connected;
  }

  /**
   * Open the socket. Resolves on the first successful connect; if the socket is
   * unavailable it rejects, but the client keeps retrying in the background so a
   * later `send()` can succeed once cmux comes back.
   */
  connect(): Promise<void> {
    if (this.disposed) return Promise.reject(new Error('CmuxIPCClient disposed'));

    return new Promise<void>((resolve, reject) => {
      const socket = net.createConnection({ path: this.socketPath });
      this.socket = socket;
      let settled = false;

      socket.on('connect', () => {
        this.connected = true;
        this.backoffMs = this.initialBackoffMs; // reset backoff on a clean link
        this.reconnectAnnounced = false;
        this.emit('connect');
        settled = true;
        resolve();
      });

      socket.setEncoding('utf-8');
      socket.on('data', (chunk: string) => {
        this.buffer += chunk;
        this.drainBuffer();
      });

      socket.on('error', (err: Error) => {
        this.emit('error', err);
        if (!settled) {
          settled = true;
          reject(err);
        }
      });

      socket.on('close', () => {
        const wasConnected = this.connected;
        this.connected = false;
        this.socket = null;
        this.failAllPending(new Error('cmux socket closed'));
        // Only announce a "disconnect" when we drop a link we actually had.
        // Failed reconnect attempts while cmux is simply not running must stay
        // quiet — they are handled entirely by scheduleReconnect().
        if (wasConnected) this.emit('disconnect');
        this.scheduleReconnect();
      });
    });
  }

  /** Stop reconnecting and tear down. Idempotent. */
  dispose(): void {
    this.disposed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.failAllPending(new Error('CmuxIPCClient disposed'));
    this.socket?.destroy();
    this.socket = null;
  }

  private scheduleReconnect(): void {
    if (this.disposed) return;
    if (this.reconnectTimer) return;
    const delay = this.backoffMs;
    // Announce the retry loop only once per down period so a cmux that is
    // simply not running doesn't flood the log every backoff cycle.
    if (!this.reconnectAnnounced) {
      this.emit('reconnecting', delay);
      this.reconnectAnnounced = true;
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect().catch(() => {
        // Widen the backoff window; the next 'close' will schedule again.
        this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs);
        this.scheduleReconnect();
      });
    }, delay);
  }

  private drainBuffer(): void {
    let nl: number;
    while ((nl = this.buffer.indexOf('\n')) !== -1) {
      const raw = this.buffer.slice(0, nl).trim();
      this.buffer = this.buffer.slice(nl + 1);
      if (!raw) continue;

      let parsed: JSONRPCResponse;
      try {
        parsed = JSON.parse(raw) as JSONRPCResponse;
      } catch (err) {
        this.emit('parse_error', err, raw);
        continue;
      }

      const waiter = this.pending.get(parsed.id);
      if (waiter) {
        clearTimeout(waiter.timer);
        this.pending.delete(parsed.id);
        if (parsed.ok) waiter.resolve(parsed.result);
        else waiter.reject(new Error(parsed.error || 'Unknown cmux IPC error'));
      } else {
        this.emit('message', parsed);
      }
    }
  }

  private failAllPending(err: Error): void {
    for (const [, waiter] of this.pending) {
      clearTimeout(waiter.timer);
      waiter.reject(err);
    }
    this.pending.clear();
  }

  /**
   * Fire a JSON-RPC call. Rejects if the socket is down, the write fails, or no
   * response arrives inside `requestTimeoutMs`.
   */
  send<T = unknown>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    const id = `req_${Math.random().toString(36).slice(2, 11)}`;
    const payload: JSONRPCRequest = { id, method, params };

    return new Promise<T>((resolve, reject) => {
      if (!this.connected || !this.socket) {
        reject(new Error('cmux socket disconnected'));
        return;
      }

      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`cmux IPC timeout after ${this.requestTimeoutMs}ms for ${method}`));
      }, this.requestTimeoutMs);

      this.pending.set(id, {
        resolve: (result) => resolve(result as T),
        reject,
        timer,
      });

      this.socket.write(JSON.stringify(payload) + '\n', (err) => {
        if (err) {
          clearTimeout(timer);
          this.pending.delete(id);
          reject(err);
        }
      });
    });
  }

  // -------------------------------------------------------------------------
  // Typed convenience wrappers for the calls the daemon actually makes.
  // The shapes below mirror the CLI/socket table in spec §1.1.
  // -------------------------------------------------------------------------

  listWorkspaces(): Promise<CmuxWorkspace[]> {
    return this.send<CmuxWorkspace[]>('workspace.list');
  }

  currentWorkspace(): Promise<CmuxWorkspace | null> {
    return this.send<CmuxWorkspace | null>('workspace.current');
  }

  listSurfaces(): Promise<CmuxSurface[]> {
    return this.send<CmuxSurface[]>('surface.list');
  }

  selectWorkspace(workspaceId: string): Promise<void> {
    return this.send('workspace.select', { workspace_id: workspaceId });
  }

  /** Focus a specific surface by selecting it in cmux. */
  focusSurface(surfaceId: string): Promise<void> {
    return this.send('surface.select', { surface_id: surfaceId });
  }

  sendText(surfaceId: string, text: string): Promise<void> {
    return this.send('surface.send_text', { surface_id: surfaceId, text });
  }

  triggerNotification(title: string, body: string, subtitle?: string): Promise<void> {
    return this.send('notification.create', { title, subtitle, body });
  }

  setSidebarStatus(
    key: string,
    value: string,
    icon: string,
    color: string,
  ): Promise<void> {
    return this.send('sidebar.set_status', { key, value, icon, color });
  }

  setSidebarProgress(progress: number, label: string): Promise<void> {
    return this.send('sidebar.set_progress', { progress, label });
  }

  appendSidebarLog(
    level: 'info' | 'warn' | 'error',
    source: string,
    message: string,
  ): Promise<void> {
    return this.send('sidebar.log', { level, source, message });
  }

  dumpSidebarState(): Promise<unknown> {
    return this.send('sidebar.sidebar_state');
  }
}

// ---------------------------------------------------------------------------
// Shapes returned by cmux. Kept intentionally permissive (extra fields allowed)
// because the daemon only relies on the members it reads here.
// ---------------------------------------------------------------------------

export interface CmuxWorkspace {
  id: string;
  title?: string;
  cwd?: string;
  is_current?: boolean;
}

export interface CmuxSurface {
  id: string;
  workspace_id?: string;
  pid?: number;
  cwd?: string;
  /** Full command line as cmux understands it, e.g. "npm run dev". */
  command?: string;
  title?: string;
  /** Last ~1000 chars of the rendered ANSI buffer, if cmux exposes it. */
  buffer_tail?: string;
  last_output_at?: string;
  last_input_at?: string;
}
