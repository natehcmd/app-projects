/**
 * Out-of-Band Sentinel Log Watcher  (spec §4.5)
 * ---------------------------------------------------------------------------
 * Watches subprocess output and system channels asynchronously. On a critical
 * break condition it latches "halted", emits `halt`, and the daemon:
 *   1. kills active worker child PIDs
 *   2. clears task queues (pauses the SwarmPipeline)
 *   3. sets a red status pill on the cmux sidebar
 *
 * The latch is intentionally sticky — once halted it stays halted until an
 * operator calls `reset()` (surfaced in the UI as "Reset Sentinel"), so a
 * flapping build can't thrash the pipeline.
 */

import { EventEmitter } from 'node:events';
import type { Readable } from 'node:stream';
import { createLogger } from './logger.js';

const log = createLogger('sentinel');

export type LogSource = 'stdout' | 'stderr' | 'ipc';

export interface WatcherConfig {
  haltOnBrokenSocket: boolean;
  haltOnBuildFailures: boolean;
  buildFailurePatterns: RegExp[];
}

export interface HaltEvent {
  reason: string;
  detail: string;
  timestamp: Date;
}

/** Sensible starting config for a compiler + IPC watch. */
export function defaultWatcherConfig(): WatcherConfig {
  return {
    haltOnBrokenSocket: true,
    haltOnBuildFailures: true,
    buildFailurePatterns: [
      /Error: Cannot find module/,
      /\bTS\d{3,5}\b/, // TypeScript compiler diagnostics
      /Fatal error:/i,
      /BUILD FAILED/,
      /No such file or directory/,
      /error\[E\d+\]/, // rustc
      /\bFAIL\b.*\.(test|spec)\./,
    ],
  };
}

export declare interface SentinelWatcher {
  on(event: 'halt', listener: (e: HaltEvent) => void): this;
  on(event: 'reset', listener: () => void): this;
}

export class SentinelWatcher extends EventEmitter {
  private readonly config: WatcherConfig;
  private halted = false;
  private lastHalt: HaltEvent | null = null;

  private static readonly SOCKET_BREAK_MARKERS = [
    'ECONNREFUSED',
    'Socket connection refused',
    'ENOENT /tmp/cmux.sock',
    'ENOENT /tmp/cmux-debug.sock',
    'EPIPE',
  ];

  constructor(config: WatcherConfig = defaultWatcherConfig()) {
    super();
    this.config = config;
  }

  get isHalted(): boolean {
    return this.halted;
  }

  get haltInfo(): HaltEvent | null {
    return this.lastHalt;
  }

  /** Feed one line of output from a compiler, server log, or the cmux IPC link. */
  handleLogLine(line: string, source: LogSource): void {
    if (this.halted) return;

    if (this.config.haltOnBrokenSocket) {
      if (SentinelWatcher.SOCKET_BREAK_MARKERS.some((m) => line.includes(m))) {
        this.trip('IPC_SOCKET_BROKEN', `broken socket in ${source} logs: "${truncate(line)}"`);
        return;
      }
    }

    if (this.config.haltOnBuildFailures) {
      for (const pattern of this.config.buildFailurePatterns) {
        if (pattern.test(line)) {
          this.trip(
            'BUILD_BREAK_DETECTED',
            `pattern ${pattern} matched in ${source}: "${truncate(line)}"`,
          );
          return;
        }
      }
    }
  }

  /**
   * Convenience: pipe a child process stream straight into the watcher,
   * splitting on newlines. Returns a detach function.
   */
  attachStream(stream: Readable, source: LogSource): () => void {
    let carry = '';
    const onData = (chunk: Buffer | string): void => {
      carry += chunk.toString();
      let nl: number;
      while ((nl = carry.indexOf('\n')) !== -1) {
        const line = carry.slice(0, nl);
        carry = carry.slice(nl + 1);
        if (line.trim()) this.handleLogLine(line, source);
      }
    };
    stream.on('data', onData);
    return () => stream.off('data', onData);
  }

  private trip(reason: string, detail: string): void {
    this.halted = true;
    this.lastHalt = { reason, detail, timestamp: new Date() };
    log.error(`[SENTINEL HALT] ${reason} — ${detail}`);
    this.emit('halt', this.lastHalt);
  }

  /** Operator-initiated clear after remediation. */
  reset(): void {
    if (!this.halted) return;
    this.halted = false;
    this.lastHalt = null;
    log.info('[sentinel] halt latch cleared by operator');
    this.emit('reset');
  }
}

function truncate(s: string, max = 240): string {
  return s.length > max ? `${s.slice(0, max)}…` : s;
}
