/**
 * Real-Time WebSocket API  (spec §7)
 * ---------------------------------------------------------------------------
 * Drives the React Control Tower.
 *
 *   Server -> Client:
 *     SERVER_STATE_UPDATE   full snapshot, every `snapshotIntervalMs` (1000ms)
 *     COMMAND_EXEC_OK       ack of a control action
 *     COMMAND_EXEC_ERROR    control action failed (never a thrown socket error)
 *     TERMINAL_DATA         incremental terminal output for subscribed clients
 *
 *   Client -> Server:
 *     PRUNE_SURF_REQUEST | FOCUS_SURF_REQUEST | RESOLVE_CONFLICT_REQUEST |
 *     TERMINAL_SUBSCRIBE | RESET_SENTINEL_REQUEST
 *
 * The server owns transport concerns only. Every actual side effect (killing a
 * PID, focusing a cmux surface, resetting the Sentinel) is delegated to the
 * `CommandHandlers` the daemon injects.
 */

import { WebSocketServer, WebSocket, type RawData } from 'ws';
import type {
  ClientMessage,
  ServerStateUpdate,
  CommandExecOk,
  CommandExecError,
  TerminalData,
} from '../shared/types.js';
import { isClientMessage } from '../shared/types.js';
import { createLogger } from './logger.js';

const log = createLogger('ws');

export interface CommandHandlers {
  pruneSurface(surfaceId: string, signal: NodeJS.Signals): Promise<{ killedPid?: number }>;
  focusSurface(surfaceId: string): Promise<void>;
  resolveConflict(
    keepSurfaceId: string,
    pruneSurfaceIds: string[],
    signal: NodeJS.Signals,
  ): Promise<{ killedPids: number[] }>;
  resetSentinel(): Promise<void>;
  /** Called when a client (un)subscribes to a surface's terminal stream. */
  onTerminalSubscribe(surfaceId: string, subscribe: boolean): void;
}

export interface ConductorWSOptions {
  host: string;
  port: number;
  snapshotIntervalMs: number;
  buildSnapshot: () => Promise<ServerStateUpdate['data']>;
  handlers: CommandHandlers;
}

interface ClientRec {
  socket: WebSocket;
  /** Surface ids this client wants TERMINAL_DATA for. */
  terminalSubs: Set<string>;
}

export class ConductorWebSocketServer {
  private readonly opts: ConductorWSOptions;
  private wss: WebSocketServer | null = null;
  private broadcastTimer: NodeJS.Timeout | null = null;
  private readonly clients = new Set<ClientRec>();

  constructor(opts: ConductorWSOptions) {
    this.opts = opts;
  }

  start(): void {
    this.wss = new WebSocketServer({ host: this.opts.host, port: this.opts.port });
    log.info(`listening on ws://${this.opts.host}:${this.opts.port}`);

    this.wss.on('connection', (socket) => {
      const rec: ClientRec = { socket, terminalSubs: new Set() };
      this.clients.add(rec);
      log.info(`client connected (${this.clients.size} total)`);

      // Push an immediate snapshot so the UI paints without waiting a full tick.
      void this.sendSnapshotTo(rec);

      socket.on('message', (data) => void this.onMessage(rec, data));
      socket.on('close', () => {
        // Tell the daemon to release any streams this client alone held open.
        for (const sid of rec.terminalSubs) this.opts.handlers.onTerminalSubscribe(sid, false);
        this.clients.delete(rec);
        log.info(`client disconnected (${this.clients.size} total)`);
      });
      socket.on('error', (err) => log.warn('client socket error', err.message));
    });

    this.wss.on('error', (err) => log.error('server error', err.message));

    this.broadcastTimer = setInterval(() => {
      void this.broadcastSnapshot();
    }, this.opts.snapshotIntervalMs);
  }

  async stop(): Promise<void> {
    if (this.broadcastTimer) clearInterval(this.broadcastTimer);
    for (const rec of this.clients) rec.socket.close(1001, 'daemon shutting down');
    await new Promise<void>((resolve) => this.wss?.close(() => resolve()));
    this.clients.clear();
  }

  /** Fan out a terminal chunk to every client subscribed to that surface. */
  pushTerminalData(surfaceId: string, chunk: string): void {
    const msg: TerminalData = { type: 'TERMINAL_DATA', surfaceId, chunk };
    const payload = JSON.stringify(msg);
    for (const rec of this.clients) {
      if (rec.terminalSubs.has(surfaceId) && rec.socket.readyState === WebSocket.OPEN) {
        rec.socket.send(payload);
      }
    }
  }

  /** True if at least one client is watching this surface's terminal. */
  hasTerminalSubscribers(surfaceId: string): boolean {
    for (const rec of this.clients) if (rec.terminalSubs.has(surfaceId)) return true;
    return false;
  }

  // -----------------------------------------------------------------------

  private async broadcastSnapshot(): Promise<void> {
    if (this.clients.size === 0) return;
    let data: ServerStateUpdate['data'];
    try {
      data = await this.opts.buildSnapshot();
    } catch (err) {
      log.error('buildSnapshot failed; skipping this tick', err instanceof Error ? err.message : err);
      return;
    }
    const msg: ServerStateUpdate = {
      type: 'SERVER_STATE_UPDATE',
      timestamp: new Date().toISOString(),
      data,
    };
    const payload = JSON.stringify(msg);
    for (const rec of this.clients) {
      if (rec.socket.readyState === WebSocket.OPEN) rec.socket.send(payload);
    }
  }

  private async sendSnapshotTo(rec: ClientRec): Promise<void> {
    try {
      const data = await this.opts.buildSnapshot();
      const msg: ServerStateUpdate = {
        type: 'SERVER_STATE_UPDATE',
        timestamp: new Date().toISOString(),
        data,
      };
      if (rec.socket.readyState === WebSocket.OPEN) rec.socket.send(JSON.stringify(msg));
    } catch (err) {
      log.warn('initial snapshot failed', err instanceof Error ? err.message : err);
    }
  }

  private async onMessage(rec: ClientRec, data: RawData): Promise<void> {
    let parsed: unknown;
    try {
      parsed = JSON.parse(data.toString());
    } catch {
      this.replyError(rec, 'unknown', 'malformed JSON');
      return;
    }
    if (!isClientMessage(parsed)) {
      this.replyError(rec, 'unknown', 'unrecognised message type');
      return;
    }
    const msg = parsed as ClientMessage;

    try {
      switch (msg.type) {
        case 'PRUNE_SURF_REQUEST': {
          const { killedPid } = await this.opts.handlers.pruneSurface(
            msg.params.surfaceId,
            msg.params.signal,
          );
          this.replyOk(rec, msg.requestId, {
            surfaceId: msg.params.surfaceId,
            killedPid,
            success: true,
          });
          break;
        }
        case 'FOCUS_SURF_REQUEST': {
          await this.opts.handlers.focusSurface(msg.params.surfaceId);
          this.replyOk(rec, msg.requestId, {
            surfaceId: msg.params.surfaceId,
            success: true,
          });
          break;
        }
        case 'RESOLVE_CONFLICT_REQUEST': {
          const { killedPids } = await this.opts.handlers.resolveConflict(
            msg.params.keepSurfaceId,
            msg.params.pruneSurfaceIds,
            msg.params.signal,
          );
          this.replyOk(rec, msg.requestId, {
            success: true,
            detail: `pruned ${killedPids.length} surface(s); kept ${msg.params.keepSurfaceId}`,
          });
          break;
        }
        case 'TERMINAL_SUBSCRIBE': {
          const { surfaceId, subscribe } = msg.params;
          if (subscribe) rec.terminalSubs.add(surfaceId);
          else rec.terminalSubs.delete(surfaceId);
          this.opts.handlers.onTerminalSubscribe(surfaceId, subscribe);
          this.replyOk(rec, msg.requestId, {
            surfaceId,
            success: true,
            detail: subscribe ? 'subscribed' : 'unsubscribed',
          });
          break;
        }
        case 'RESET_SENTINEL_REQUEST': {
          await this.opts.handlers.resetSentinel();
          this.replyOk(rec, msg.requestId, { success: true, detail: 'sentinel reset' });
          break;
        }
      }
    } catch (err) {
      this.replyError(
        rec,
        'requestId' in msg ? msg.requestId : 'unknown',
        err instanceof Error ? err.message : String(err),
      );
    }
  }

  private replyOk(rec: ClientRec, requestId: string, result: CommandExecOk['result']): void {
    const msg: CommandExecOk = {
      type: 'COMMAND_EXEC_OK',
      requestId,
      timestamp: new Date().toISOString(),
      result,
    };
    if (rec.socket.readyState === WebSocket.OPEN) rec.socket.send(JSON.stringify(msg));
  }

  private replyError(rec: ClientRec, requestId: string, error: string): void {
    const msg: CommandExecError = {
      type: 'COMMAND_EXEC_ERROR',
      requestId,
      timestamp: new Date().toISOString(),
      error,
    };
    if (rec.socket.readyState === WebSocket.OPEN) rec.socket.send(JSON.stringify(msg));
  }
}
