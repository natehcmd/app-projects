/**
 * Minimal levelled logger with a ring buffer.
 *
 * The Swarm pipeline and Sentinel need *traceable* logs (spec Execution
 * Requirement #3), and the React UI wants the last N pipeline lines inside the
 * snapshot. Rather than pull in a logging framework we keep a tiny structured
 * logger that (a) prints to stderr with a stable prefix and (b) retains a
 * bounded in-memory tail that `state-aggregator.ts` folds into the snapshot.
 */

export type LogLevel = 'error' | 'warn' | 'info' | 'debug';

const LEVEL_RANK: Record<LogLevel, number> = { error: 0, warn: 1, info: 2, debug: 3 };

const configuredLevel = (process.env.LOG_LEVEL as LogLevel) || 'info';
const threshold = LEVEL_RANK[configuredLevel] ?? LEVEL_RANK.info;

/** Bounded FIFO of recent human-readable log lines for the UI console. */
class RingBuffer {
  private readonly lines: string[] = [];
  constructor(private readonly capacity: number) {}

  push(line: string): void {
    this.lines.push(line);
    if (this.lines.length > this.capacity) this.lines.splice(0, this.lines.length - this.capacity);
  }

  snapshot(): string[] {
    return this.lines.slice();
  }
}

const ring = new RingBuffer(200);

function emit(level: LogLevel, scope: string, message: string, meta?: unknown): void {
  if (LEVEL_RANK[level] > threshold) return;
  const ts = new Date().toISOString();
  const line = `${ts} [${level.toUpperCase()}] [${scope}] ${message}`;
  ring.push(line);
  // Everything goes to stderr so stdout stays clean for structured output / pipes.
  if (meta !== undefined) {
    console.error(line, meta);
  } else {
    console.error(line);
  }
}

export interface ScopedLogger {
  error(message: string, meta?: unknown): void;
  warn(message: string, meta?: unknown): void;
  info(message: string, meta?: unknown): void;
  debug(message: string, meta?: unknown): void;
}

export function createLogger(scope: string): ScopedLogger {
  return {
    error: (m, meta) => emit('error', scope, m, meta),
    warn: (m, meta) => emit('warn', scope, m, meta),
    info: (m, meta) => emit('info', scope, m, meta),
    debug: (m, meta) => emit('debug', scope, m, meta),
  };
}

/** Recent log tail, newest last — surfaced in `SwarmSnapshot.recentLog`. */
export function recentLogLines(): string[] {
  return ring.snapshot();
}
