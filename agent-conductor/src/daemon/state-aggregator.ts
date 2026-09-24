/**
 * State Aggregator
 * ---------------------------------------------------------------------------
 * Fuses the four data sources into the single `SERVER_STATE_UPDATE.data`
 * snapshot the React Control Tower renders:
 *
 *   cmux surfaces  (cmux-ipc)      -> terminal sessions + buffer tails
 *   Chrome tabs    (chrome-harvester)
 *   listening ports(process-discovery)
 *   process facts  (process-discovery) -> cwd, git branch, cpu, mem
 *
 * It also carries the small amount of *state* the pure engines need but cannot
 * derive from a single sample:
 *   - `listenSince`  : first time a (port,pid) pair was seen LISTENing
 *   - `lastActivity` : last time a surface's buffer tail changed (fallback for
 *                      cmux builds that don't expose last_output_at)
 */

import * as os from 'node:os';
import type {
  BrowserTabSnapshot,
  ConflictSnapshot,
  RepositorySummary,
  ServerStateUpdate,
  SurfaceSnapshot,
  SwarmSnapshot,
  SystemVitals,
} from '../shared/types.js';
import { CmuxIPCClient, type CmuxSurface } from './cmux-ipc.js';
import { harvestChromeTabs } from './chrome-harvester.js';
import {
  getMetrics,
  gitBranchOf,
  gitRootOf,
  listListeningPorts,
  type PortListener,
} from './process-discovery.js';
import {
  HeuristicEngine,
  detectExactDuplicates,
  detectPortConflicts,
  type PortListenerRecord,
  type SurfaceMeta,
  type SurfaceMetrics,
} from './dedup-engine.js';
import { createLogger } from './logger.js';
import * as path from 'node:path';

const log = createLogger('aggregator');

interface SurfaceActivity {
  bufferHash: string;
  lastOutputAt: number;
  lastInputAt: number;
}

export interface AggregatorSurfaceRef {
  surfaceId: string;
  pid: number;
  cwd: string;
}

export class StateAggregator {
  private readonly cmux: CmuxIPCClient;

  /** (port + '@' + pid) -> epoch ms first observed LISTENing. */
  private readonly listenSince = new Map<string, number>();
  /** surfaceId -> activity tracking for the heuristic engine. */
  private readonly activity = new Map<string, SurfaceActivity>();
  /** Latest surface id -> {pid,cwd} for prune / focus / stream lookups. */
  private surfaceRefs = new Map<string, AggregatorSurfaceRef>();

  constructor(cmux: CmuxIPCClient) {
    this.cmux = cmux;
  }

  /** Resolve a surface id to its PID/CWD from the most recent snapshot. */
  refFor(surfaceId: string): AggregatorSurfaceRef | undefined {
    return this.surfaceRefs.get(surfaceId);
  }

  async buildSnapshot(swarm: SwarmSnapshot): Promise<ServerStateUpdate['data']> {
    const now = Date.now();

    // --- gather in parallel -------------------------------------------------
    const [rawSurfaces, chromeTabs, portListeners] = await Promise.all([
      this.safeListSurfaces(),
      harvestChromeTabs(),
      listListeningPorts(),
    ]);

    // --- listenSince bookkeeping -----------------------------------------
    const liveKeys = new Set<string>();
    const portRecords: PortListenerRecord[] = [];
    for (const l of portListeners) {
      const key = `${l.port}@${l.pid}`;
      liveKeys.add(key);
      if (!this.listenSince.has(key)) this.listenSince.set(key, now);
      portRecords.push({
        port: l.port,
        pid: l.pid,
        command: l.command,
        cwd: '', // filled lazily below only where needed
        listenSince: new Date(this.listenSince.get(key) as number),
      });
    }
    // forget ports that are no longer bound
    for (const key of [...this.listenSince.keys()]) {
      if (!liveKeys.has(key)) this.listenSince.delete(key);
    }

    // --- per-surface enrichment ------------------------------------------
    const surfaceMetas: SurfaceMeta[] = rawSurfaces.map((s) => ({
      id: s.id,
      pid: s.pid ?? 0,
      cwd: s.cwd ?? '',
      command: s.command ?? '',
    }));

    const surfaces: SurfaceSnapshot[] = [];
    const nextRefs = new Map<string, AggregatorSurfaceRef>();

    for (const s of rawSurfaces) {
      const pid = s.pid ?? 0;
      const cwd = s.cwd ?? '';
      const command = s.command ?? '';

      const [metrics, gitBranch, gitRoot] = await Promise.all([
        pid ? getMetrics(pid) : Promise.resolve({ pid: 0, cpuPercent: 0, memoryMB: 0 }),
        gitBranchOf(cwd),
        gitRootOf(cwd),
      ]);

      // Ports owned directly by this surface's PID.
      const ports = [
        ...new Set(portListeners.filter((l) => l.pid === pid).map((l) => l.port)),
      ].sort((a, b) => a - b);

      const act = this.trackActivity(s, now);

      const heurMetrics: SurfaceMetrics = {
        surfaceId: s.id,
        pid,
        cwd,
        command,
        cpuPercent: metrics.cpuPercent,
        lastOutputTimestamp: new Date(act.lastOutputAt),
        lastInputTimestamp: new Date(act.lastInputAt),
        unprocessedBufferTail: s.buffer_tail ?? '',
      };
      const state = HeuristicEngine.classifySurface(heurMetrics, surfaceMetas, portRecords);

      surfaces.push({
        surfaceId: s.id,
        pid,
        cwd,
        binaryName: s.command ? (s.command.trim().split(/\s+/)[0] as string) : '',
        command,
        gitBranch,
        ports,
        state,
        cpuPercent: metrics.cpuPercent,
        memoryMB: metrics.memoryMB,
        lastActive: new Date(Math.max(act.lastOutputAt, act.lastInputAt)).toISOString(),
      });

      nextRefs.set(s.id, { surfaceId: s.id, pid, cwd });
      void gitRoot; // resolved again in the repo rollup below (cached by git)
    }
    this.surfaceRefs = nextRefs;
    // drop activity entries for surfaces that disappeared
    for (const id of [...this.activity.keys()]) {
      if (!nextRefs.has(id)) this.activity.delete(id);
    }

    // --- repository rollup ---------------------------------------------
    const repositories = await this.rollupRepositories(surfaces);

    // --- browser tab <-> repo association -----------------------------
    const portToRepo = this.buildPortToRepoIndex(portListeners, repositories, surfaces);
    const browserTabs: BrowserTabSnapshot[] = chromeTabs.map((t, i) => ({
      tabId: `chrome-tab-${t.windowId}-${t.tabIndex}`,
      windowId: t.windowId,
      title: t.title,
      url: t.url,
      isActive: t.isActive,
      associatedRepo: t.localPort != null ? portToRepo.get(t.localPort) ?? null : null,
    }));
    void chromeTabs.length;

    // --- conflicts ----------------------------------------------------
    const unresolvedConflicts: ConflictSnapshot[] = [];
    for (const [key, group] of detectExactDuplicates(surfaceMetas)) {
      unresolvedConflicts.push({
        groupId: key,
        type: 'EXACT_DUPLICATE',
        surfaceIds: group.map((g) => g.id),
      });
    }
    for (const [port, group] of detectPortConflicts(portRecords)) {
      unresolvedConflicts.push({
        groupId: `port:${port}`,
        type: 'PORT_CONFLICT',
        surfaceIds: group.map((g) => `pid:${g.pid}`),
      });
    }

    return {
      system: readSystemVitals(),
      repositories,
      surfaces,
      browserTabs,
      unresolvedConflicts,
      swarm,
    };
  }

  // -----------------------------------------------------------------------

  private async safeListSurfaces(): Promise<CmuxSurface[]> {
    if (!this.cmux.isConnected) return [];
    try {
      return await this.cmux.listSurfaces();
    } catch (err) {
      log.warn('cmux surface.list failed', err instanceof Error ? err.message : err);
      return [];
    }
  }

  /**
   * Update last-output / last-input timestamps. If cmux gave us explicit
   * `last_output_at` / `last_input_at` we trust those; otherwise we detect a
   * change in the buffer tail as a proxy for "produced output".
   */
  private trackActivity(s: CmuxSurface, now: number): SurfaceActivity {
    const prev = this.activity.get(s.id);
    const hash = cheapHash(s.buffer_tail ?? '');

    const explicitOut = s.last_output_at ? Date.parse(s.last_output_at) : NaN;
    const explicitIn = s.last_input_at ? Date.parse(s.last_input_at) : NaN;

    const next: SurfaceActivity = {
      bufferHash: hash,
      lastOutputAt: Number.isFinite(explicitOut)
        ? explicitOut
        : prev
          ? prev.bufferHash !== hash
            ? now
            : prev.lastOutputAt
          : now,
      lastInputAt: Number.isFinite(explicitIn) ? explicitIn : prev ? prev.lastInputAt : now,
    };
    this.activity.set(s.id, next);
    return next;
  }

  private async rollupRepositories(
    surfaces: SurfaceSnapshot[],
  ): Promise<RepositorySummary[]> {
    const byRoot = new Map<string, RepositorySummary>();
    for (const s of surfaces) {
      if (!s.cwd) continue;
      const root = await gitRootOf(s.cwd);
      if (!root) continue;
      let entry = byRoot.get(root);
      if (!entry) {
        entry = {
          repoName: path.basename(root),
          rootPath: root,
          currentBranch: await gitBranchOf(root),
          activeSurfaces: [],
        };
        byRoot.set(root, entry);
      }
      entry.activeSurfaces.push(s.surfaceId);
    }
    return [...byRoot.values()];
  }

  private buildPortToRepoIndex(
    listeners: PortListener[],
    repositories: RepositorySummary[],
    surfaces: SurfaceSnapshot[],
  ): Map<number, string> {
    const index = new Map<number, string>();
    for (const l of listeners) {
      // Prefer: a surface whose PID owns this port -> its repo.
      const owningSurface = surfaces.find((s) => s.pid === l.pid);
      if (owningSurface?.cwd) {
        const repo = repositories.find((r) => underPath(owningSurface.cwd, r.rootPath));
        if (repo) {
          index.set(l.port, repo.repoName);
          continue;
        }
      }
    }
    return index;
  }
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function readSystemVitals(): SystemVitals {
  const cores = os.cpus().length || 1;
  const load1 = os.loadavg()[0] ?? 0;
  const totalBytes = os.totalmem();
  const freeBytes = os.freemem();
  return {
    cpuLoad: Math.round(((load1 / cores) * 100) * 10) / 10,
    memoryUsageGB: Math.round(((totalBytes - freeBytes) / 1024 ** 3) * 10) / 10,
    totalMemoryGB: Math.round((totalBytes / 1024 ** 3) * 10) / 10,
  };
}

function underPath(child: string, parent: string): boolean {
  const rel = path.relative(parent, child);
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel));
}

/** Fast, allocation-light 32-bit string hash (FNV-1a). Not cryptographic. */
function cheapHash(s: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0;
  }
  return h.toString(16);
}
