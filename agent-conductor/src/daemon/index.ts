/**
 * Agent Conductor daemon — entry point.
 * ---------------------------------------------------------------------------
 * Wires the modules together:
 *
 *   cmux IPC  <-->  StateAggregator  -->  WebSocket snapshot (1000ms)
 *                                    ^
 *   Chrome / lsof / ps  ------------ |
 *
 *   SentinelWatcher  --halt-->  pause SwarmPipeline + red cmux status pill
 *   WebSocket control msgs  -->  kill PIDs / focus surface / reset sentinel
 *   Terminal subscriptions  -->  poll cmux buffer tails, push TERMINAL_DATA
 *
 * Run:  npm run daemon        (tsx watch)
 *       npm run daemon:once   (single process, no reload)
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createLogger } from './logger.js';
import { CmuxIPCClient } from './cmux-ipc.js';
import { StateAggregator } from './state-aggregator.js';
import { ConductorWebSocketServer, type CommandHandlers } from './websocket-server.js';
import { SentinelWatcher, defaultWatcherConfig } from './sentinel.js';
import {
  SwarmPipeline,
  purgeLlamaSlot,
  freshOllamaThread,
  type SwarmPipelineOptions,
} from './swarm-pipeline.js';
import type { SwarmSnapshot, TargetTier } from '../shared/types.js';
import { recentLogLines } from './logger.js';

// ---------------------------------------------------------------------------
// Tiny .env loader (avoids a dependency; Node's --env-file is still flagged on
// some versions). Only sets keys that aren't already in the environment.
// ---------------------------------------------------------------------------
function loadDotEnv(): void {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const envPath = path.resolve(here, '../../.env');
  if (!fs.existsSync(envPath)) return;
  for (const line of fs.readFileSync(envPath, 'utf-8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
    if (!(key in process.env)) process.env[key] = val;
  }
}
loadDotEnv();

const log = createLogger('daemon');

const CONFIG = {
  cmuxSocketPath: process.env.CMUX_SOCKET_PATH || '/tmp/cmux.sock',
  wsHost: process.env.CONDUCTOR_WS_HOST || '127.0.0.1',
  wsPort: Number.parseInt(process.env.CONDUCTOR_WS_PORT || '8787', 10),
  snapshotIntervalMs: Number.parseInt(process.env.SNAPSHOT_INTERVAL_MS || '1000', 10),
  llamaHost: process.env.LLAMA_HOST || '127.0.0.1',
  llamaPort: Number.parseInt(process.env.LLAMA_PORT || '8080', 10),
};

// ===========================================================================
// Bootstrap
// ===========================================================================

async function main(): Promise<void> {
  log.info('Agent Conductor daemon starting', CONFIG);

  // --- cmux IPC (non-fatal if cmux isn't running yet) --------------------
  const cmux = new CmuxIPCClient({ socketPath: CONFIG.cmuxSocketPath });
  cmux.on('connect', () => log.info('cmux socket connected'));
  cmux.on('disconnect', () => log.warn('cmux socket dropped — reconnecting in background'));
  cmux.on('reconnecting', () => log.debug('cmux retry loop armed'));
  cmux.on('error', (err) => log.debug('cmux socket error', err.message));
  cmux.on('parse_error', (_e, raw) => log.warn('cmux sent unparseable frame', raw.slice(0, 200)));
  await cmux.connect().catch((err) => {
    log.warn(`cmux not reachable at ${CONFIG.cmuxSocketPath} — will keep retrying`, err.message);
  });

  // --- Sentinel --------------------------------------------------------
  const sentinel = new SentinelWatcher(defaultWatcherConfig());

  // --- Swarm pipeline ------------------------------------------------
  // `runWorker` is the integration seam: plug your Gemini / llama-server /
  // Ollama call here. The stub below just records the attempt so the state
  // machine and the UI have something to show.
  const swarmOptions: SwarmPipelineOptions = {
    workers: {
      GEMINI_COMPLEX_UI: ['gemini-worker-1'],
      LOCAL_CODEGEN: ['local-slot-0', 'local-slot-1'],
    },
    runWorker: async (task, workerId) => {
      log.info(`[worker ${workerId}] executing ${task.id} (${task.targetTier}): ${task.title}`);
      // TODO integrator: dispatch to the real model here.
      return { ok: true, detail: 'stub worker — no model wired' };
    },
    wipeContext: async (workerId, tier: TargetTier) => {
      if (tier === 'LOCAL_CODEGEN') {
        // Map worker slot name -> llama-server slot index.
        const slotId = Number.parseInt(workerId.replace(/\D+/g, ''), 10) || 0;
        return purgeLlamaSlot(CONFIG.llamaHost, CONFIG.llamaPort, slotId);
      }
      // Cloud / Ollama-style workers: just drop the thread.
      freshOllamaThread();
      return true;
    },
  };
  const swarm = new SwarmPipeline(swarmOptions);
  swarm.on('phase', (id, phase) => log.debug(`[swarm] ${id} -> ${phase}`));
  swarm.on('pipeline_complete', (name) => log.info(`[swarm] pipeline "${name}" complete`));

  // Sentinel halt -> pause pipeline, flag cmux, notify.
  sentinel.on('halt', async (e) => {
    swarm.halt(`${e.reason}: ${e.detail}`);
    if (cmux.isConnected) {
      await cmux
        .setSidebarStatus('sentinel', 'HALTED', 'error', '#ff3b30')
        .catch((err) => log.debug('sidebar status set failed', err.message));
      await cmux
        .triggerNotification('Agent Conductor', `Pipeline halted: ${e.reason}`)
        .catch(() => undefined);
    }
  });
  sentinel.on('reset', async () => {
    swarm.resume();
    if (cmux.isConnected) {
      await cmux
        .setSidebarStatus('sentinel', 'OK', 'checkmark', '#34c759')
        .catch(() => undefined);
    }
  });

  // --- State aggregator --------------------------------------------
  const aggregator = new StateAggregator(cmux);

  const buildSwarmSnapshot = (): SwarmSnapshot => ({
    halted: sentinel.isHalted,
    haltReason: sentinel.haltInfo ? `${sentinel.haltInfo.reason}: ${sentinel.haltInfo.detail}` : null,
    activeTasks: swarm.statusSnapshot(),
    recentLog: recentLogLines().slice(-40),
  });

  // --- Terminal streamer (declared before handlers; assigned after wss) ---
  // cmux's socket does not push terminal output, so we poll the buffer tail of
  // subscribed surfaces and emit the delta as TERMINAL_DATA. It is only ever
  // invoked from an async WebSocket message handler, which cannot run before
  // the synchronous assignment below completes.
  let terminalStreamer: TerminalStreamer;

  // --- WebSocket server + control handlers ------------------------
  const handlers: CommandHandlers = {
    async pruneSurface(surfaceId, signal) {
      const ref = aggregator.refFor(surfaceId);
      if (!ref || ref.pid <= 1) throw new Error(`unknown or unsafe surface ${surfaceId}`);
      killPid(ref.pid, signal);
      return { killedPid: ref.pid };
    },
    async focusSurface(surfaceId) {
      if (!cmux.isConnected) throw new Error('cmux not connected');
      await cmux.focusSurface(surfaceId);
    },
    async resolveConflict(keepSurfaceId, pruneSurfaceIds, signal) {
      const killedPids: number[] = [];
      for (const id of pruneSurfaceIds) {
        const ref = aggregator.refFor(id);
        if (ref && ref.pid > 1) {
          killPid(ref.pid, signal);
          killedPids.push(ref.pid);
        }
      }
      log.info(`resolved conflict: kept ${keepSurfaceId}, pruned ${killedPids.join(', ')}`);
      return { killedPids };
    },
    async resetSentinel() {
      sentinel.reset();
    },
    onTerminalSubscribe(surfaceId, subscribe) {
      terminalStreamer.setSubscribed(surfaceId, subscribe);
    },
  };

  const wss = new ConductorWebSocketServer({
    host: CONFIG.wsHost,
    port: CONFIG.wsPort,
    snapshotIntervalMs: CONFIG.snapshotIntervalMs,
    buildSnapshot: () => aggregator.buildSnapshot(buildSwarmSnapshot()),
    handlers,
  });
  wss.start();
  terminalStreamer = new TerminalStreamer(cmux, wss);

  // --- graceful shutdown ---------------------------------------
  const shutdown = async (sig: string): Promise<void> => {
    log.info(`received ${sig}, shutting down`);
    terminalStreamer.stop();
    await wss.stop().catch(() => undefined);
    cmux.dispose();
    process.exit(0);
  };
  process.on('SIGINT', () => void shutdown('SIGINT'));
  process.on('SIGTERM', () => void shutdown('SIGTERM'));

  log.info(`daemon ready — Control Tower can connect to ws://${CONFIG.wsHost}:${CONFIG.wsPort}`);
}

// ===========================================================================
// Helpers
// ===========================================================================

/** Guarded `process.kill`. Refuses pid<=1 and swallows ESRCH (already gone). */
function killPid(pid: number, signal: NodeJS.Signals): void {
  if (pid <= 1) throw new Error(`refusing to signal pid ${pid}`);
  try {
    process.kill(pid, signal);
    log.info(`sent ${signal} to pid ${pid}`);
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    if (code === 'ESRCH') {
      log.info(`pid ${pid} already exited`);
      return;
    }
    throw err;
  }
}

/**
 * Polls cmux surface buffer tails for surfaces with active subscribers and
 * pushes the newly-appended text to the WebSocket server.
 */
class TerminalStreamer {
  private readonly subscribed = new Set<string>();
  private readonly lastTail = new Map<string, string>();
  private timer: NodeJS.Timeout | null = null;
  private readonly log = createLogger('terminal');

  constructor(
    private readonly cmux: CmuxIPCClient,
    private readonly wss: ConductorWebSocketServer,
    private readonly pollMs = 250,
  ) {}

  setSubscribed(surfaceId: string, subscribe: boolean): void {
    if (subscribe) {
      this.subscribed.add(surfaceId);
      if (!this.timer) this.start();
    } else {
      this.subscribed.delete(surfaceId);
      this.lastTail.delete(surfaceId);
      if (this.subscribed.size === 0) this.stop();
    }
  }

  private start(): void {
    this.timer = setInterval(() => void this.poll(), this.pollMs);
    this.log.info('terminal streamer started');
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.lastTail.clear();
  }

  private async poll(): Promise<void> {
    if (!this.cmux.isConnected || this.subscribed.size === 0) return;
    let surfaces;
    try {
      surfaces = await this.cmux.listSurfaces();
    } catch {
      return;
    }
    for (const s of surfaces) {
      if (!this.subscribed.has(s.id)) continue;
      const tail = s.buffer_tail ?? '';
      const prev = this.lastTail.get(s.id) ?? '';
      if (tail === prev) continue;
      // Emit only the appended suffix when the new tail extends the old one;
      // otherwise (buffer scrolled / cleared) emit the whole tail.
      const delta = tail.startsWith(prev) ? tail.slice(prev.length) : tail;
      this.lastTail.set(s.id, tail);
      if (delta) this.wss.pushTerminalData(s.id, delta);
    }
  }
}

main().catch((err) => {
  log.error('fatal', err instanceof Error ? err.stack : err);
  process.exit(1);
});
