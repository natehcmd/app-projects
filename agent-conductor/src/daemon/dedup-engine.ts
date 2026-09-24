/**
 * Deduplication & Stale-Session Algorithms  (spec §5)
 * ---------------------------------------------------------------------------
 * Pure functions — no I/O. Given normalised surface + port facts gathered by
 * `process-discovery.ts`, this module:
 *
 *   1. groups EXACT duplicates (same command, same resolved CWD)
 *   2. groups dev-port collisions (>1 PID LISTENing on one port)
 *   3. classifies each surface into a state badge:
 *        NEEDS_INPUT | RUNNING | IDLE | DUPLICATE
 *
 * Keeping this side-effect-free makes it trivially unit-testable and lets the
 * daemon run it every tick without worrying about ordering.
 */

import * as path from 'node:path';

// ---------------------------------------------------------------------------
// Inputs
// ---------------------------------------------------------------------------

export interface SurfaceMeta {
  id: string;
  pid: number;
  cwd: string;
  command: string;
}

export interface PortListenerRecord {
  port: number;
  pid: number;
  command: string;
  cwd: string;
  /** When this PID was first observed LISTENing on the port. */
  listenSince: Date;
}

export interface SurfaceMetrics {
  surfaceId: string;
  pid: number;
  cwd: string;
  command: string;
  cpuPercent: number;
  lastOutputTimestamp: Date;
  lastInputTimestamp: Date;
  /** Last ~1000 chars of the rendered terminal ANSI buffer. */
  unprocessedBufferTail: string;
}

export type SurfaceState = 'NEEDS_INPUT' | 'RUNNING' | 'IDLE' | 'DUPLICATE';

// ---------------------------------------------------------------------------
// Normalisation helpers — one definition, reused everywhere so the grouping
// key in `detectExactDuplicates` and the comparison in `classifySurface` can
// never diverge.
// ---------------------------------------------------------------------------

export function normalizeCwd(cwd: string): string {
  if (!cwd) return '';
  // `path.resolve` collapses `.`/`..` and duplicate slashes. We lowercase
  // because macOS's default filesystem (APFS, HFS+) is case-insensitive.
  return path.resolve(cwd).toLowerCase();
}

export function normalizeCommand(command: string): string {
  return command.trim().replace(/\s+/g, ' ');
}

export function dedupKey(cwd: string, command: string): string {
  return `${normalizeCwd(cwd)}::${normalizeCommand(command)}`;
}

// ---------------------------------------------------------------------------
// 5.1 Exact duplicates
// ---------------------------------------------------------------------------

/**
 * Returns groups (keyed `<cwd>::<command>`) that contain more than one surface.
 * Each group's list is sorted oldest-PID-first so callers can treat `[0]` as
 * the "keep" candidate.
 */
export function detectExactDuplicates(
  surfaces: SurfaceMeta[],
): Map<string, SurfaceMeta[]> {
  const groups = new Map<string, SurfaceMeta[]>();
  for (const s of surfaces) {
    const key = dedupKey(s.cwd, s.command);
    const bucket = groups.get(key);
    if (bucket) bucket.push(s);
    else groups.set(key, [s]);
  }

  const duplicates = new Map<string, SurfaceMeta[]>();
  for (const [key, list] of groups) {
    if (list.length > 1) {
      list.sort((a, b) => a.pid - b.pid);
      duplicates.set(key, list);
    }
  }
  return duplicates;
}

// ---------------------------------------------------------------------------
// 5.2 Duplicate dev ports
// ---------------------------------------------------------------------------

/**
 * Returns ports with more than one LISTENer. Each list is sorted longest-
 * listening-first (the incumbent server is `[0]`).
 */
export function detectPortConflicts(
  listeners: PortListenerRecord[],
): Map<number, PortListenerRecord[]> {
  const byPort = new Map<number, PortListenerRecord[]>();
  for (const l of listeners) {
    const bucket = byPort.get(l.port);
    if (bucket) bucket.push(l);
    else byPort.set(l.port, [l]);
  }

  const conflicts = new Map<number, PortListenerRecord[]>();
  for (const [port, list] of byPort) {
    if (list.length > 1) {
      list.sort((a, b) => a.listenSince.getTime() - b.listenSince.getTime());
      conflicts.set(port, list);
    }
  }
  return conflicts;
}

// ---------------------------------------------------------------------------
// 5.3 Heuristic rule engine
// ---------------------------------------------------------------------------

export class HeuristicEngine {
  /** Patterns that indicate the process is blocked waiting on a human. */
  private static readonly INPUT_PROMPT_PATTERNS: RegExp[] = [
    /\?\s+enter your choice:/i,
    /\[y\/n\]/i,
    /\(y\/n\)/i,
    /press enter to continue/i,
    /password:\s*$/i,
    /passphrase.*:\s*$/i,
    /^\s*>\s*$/m, // trailing bare prompt
    /claude\s+waiting\s+for\s+input/i,
    /overwrite\?/i,
    /proceed\?\s*\(/i,
  ];

  /** Patterns for a crash / fatal error that has halted forward progress. */
  private static readonly ERROR_CRASH_PATTERNS: RegExp[] = [
    /fatal error/i,
    /uncaught exception/i,
    /unhandledrejection/i,
    /error: compilation failed/i,
    /\bTS\d{3,5}\b/, // tsc diagnostic code
    /address already in use/i,
    /\beaddrinuse\b/i,
    /panic:/i,
    /segmentation fault/i,
  ];

  private static readonly RUNNING_OUTPUT_WINDOW_MS = 10_000;
  private static readonly IDLE_WINDOW_MS = 30 * 60 * 1000;

  /**
   * Classify one surface. Rule order matters — DUPLICATE and NEEDS_INPUT win
   * over RUNNING so the operator's attention is drawn to the right cards.
   */
  static classifySurface(
    metrics: SurfaceMetrics,
    allSurfaces: SurfaceMeta[],
    _portListeners: PortListenerRecord[],
  ): SurfaceState {
    const now = Date.now();
    const sinceOutput = now - metrics.lastOutputTimestamp.getTime();
    const sinceInput = now - metrics.lastInputTimestamp.getTime();

    // Rule 1 — redundant clone. Same normalised command + CWD as another
    // surface, and this PID is not the lowest (oldest) in the group.
    const key = dedupKey(metrics.cwd, metrics.command);
    const siblings = allSurfaces.filter(
      (s) => s.id !== metrics.surfaceId && dedupKey(s.cwd, s.command) === key,
    );
    if (siblings.length > 0) {
      const minPid = Math.min(metrics.pid, ...siblings.map((s) => s.pid));
      if (metrics.pid > minPid) return 'DUPLICATE';
    }

    // Rule 2 — blocked on input, or crashed and no longer burning CPU.
    const tail = metrics.unprocessedBufferTail ?? '';
    const hasPrompt = this.INPUT_PROMPT_PATTERNS.some((re) => re.test(tail));
    const hasCrash = this.ERROR_CRASH_PATTERNS.some((re) => re.test(tail));
    if (hasPrompt || (hasCrash && metrics.cpuPercent < 2.0)) return 'NEEDS_INPUT';

    // Rule 3 — actively working.
    if (metrics.cpuPercent > 5.0 || sinceOutput < this.RUNNING_OUTPUT_WINDOW_MS) {
      return 'RUNNING';
    }

    // Rule 4 — stale: no I/O for over 30 minutes.
    if (sinceOutput > this.IDLE_WINDOW_MS && sinceInput > this.IDLE_WINDOW_MS) {
      return 'IDLE';
    }

    // Default — quiet but not stale.
    return 'IDLE';
  }
}
