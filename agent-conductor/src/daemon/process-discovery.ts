/**
 * Process & Git Repository Discovery  (spec §2.3 + §3)
 * ---------------------------------------------------------------------------
 * The OS Integration Layer. Everything that shells out to macOS `ps`, `lsof`
 * and `git` lives here so the rest of the daemon stays platform-agnostic.
 *
 * macOS specifics relied on:
 *   - `ps -o ppid= -p <pid>`      parent PID (whitespace-padded, hence trim)
 *   - `ps -p <pid> -o comm=`      executable path; basename is the binary name
 *   - `ps -p <pid> -o %cpu=,rss=` CPU% and resident set size (KiB on Darwin)
 *   - `lsof -a -p <pid> -d cwd -Fn`  the process's *live* working directory,
 *                                    which `pwd` in a shell cannot give us for
 *                                    an arbitrary PID. The `-Fn` field output
 *                                    prints `n<path>`; we strip the leading `n`.
 *   - `lsof -nP -iTCP -sTCP:LISTEN`  every listening TCP socket + owning PID,
 *                                    used for port<->PID association and the
 *                                    dedup engine's port-conflict detector.
 *
 * All calls are async (`execFile`) so the 1s snapshot loop never blocks the
 * event loop on a slow `lsof`.
 */

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { createLogger } from './logger.js';

const execFileAsync = promisify(execFile);
const log = createLogger('procdisc');

const EXEC_OPTS = { timeout: 4_000, maxBuffer: 8 * 1024 * 1024 } as const;

export interface ProcessContext {
  pid: number;
  ppid: number;
  binaryName: string;
  cwd: string;
  gitBranch: string | null;
  gitRoot: string | null;
}

export interface ProcessMetrics {
  pid: number;
  cpuPercent: number;
  memoryMB: number;
}

export interface PortMapping {
  port: number;
  pid: number;
  command: string;
  cwd: string;
}

export interface PortListener {
  port: number;
  pid: number;
  command: string;
  address: string; // e.g. "*", "127.0.0.1", "[::1]"
}

// ---------------------------------------------------------------------------
// Single-process facts
// ---------------------------------------------------------------------------

async function run(cmd: string, args: string[]): Promise<string> {
  const { stdout } = await execFileAsync(cmd, args, EXEC_OPTS);
  return stdout;
}

/** Parent PID of `pid`, or `0` if it cannot be read (process gone). */
export async function getParentPid(pid: number): Promise<number> {
  try {
    const out = await run('ps', ['-o', 'ppid=', '-p', String(pid)]);
    return Number.parseInt(out.trim(), 10) || 0;
  } catch {
    return 0;
  }
}

/** Basename of the executable backing `pid` (e.g. "node", "cmux", "Vitest"). */
export async function getBinaryName(pid: number): Promise<string> {
  try {
    const out = await run('ps', ['-p', String(pid), '-o', 'comm=']);
    return path.basename(out.trim());
  } catch {
    return '';
  }
}

/**
 * Live working directory of an arbitrary PID via `lsof`. `-Fn` prints one field
 * per line prefixed by its type; the cwd entry is the `n`-prefixed line that
 * follows the `fcwd` marker. We take the last `n` line to be safe.
 */
export async function getCwd(pid: number): Promise<string> {
  try {
    const out = await run('lsof', ['-a', '-p', String(pid), '-d', 'cwd', '-Fn']);
    const nLines = out
      .split('\n')
      .filter((l) => l.startsWith('n'))
      .map((l) => l.slice(1).trim())
      .filter(Boolean);
    return nLines.length > 0 ? (nLines[nLines.length - 1] as string) : '';
  } catch {
    return '';
  }
}

/** CPU% (of one core) and RSS in MB for a PID. */
export async function getMetrics(pid: number): Promise<ProcessMetrics> {
  try {
    const out = await run('ps', ['-p', String(pid), '-o', '%cpu=,rss=']);
    const [cpuStr, rssStr] = out.trim().split(/\s+/);
    return {
      pid,
      cpuPercent: Number.parseFloat(cpuStr ?? '0') || 0,
      // Darwin `rss` is in KiB.
      memoryMB: Math.round(((Number.parseInt(rssStr ?? '0', 10) || 0) / 1024) * 10) / 10,
    };
  } catch {
    return { pid, cpuPercent: 0, memoryMB: 0 };
  }
}

// ---------------------------------------------------------------------------
// Git context
// ---------------------------------------------------------------------------

export async function gitBranchOf(dir: string): Promise<string | null> {
  if (!dir || !safeIsDir(dir)) return null;
  try {
    const out = await run('git', ['-C', dir, 'rev-parse', '--abbrev-ref', 'HEAD']);
    const branch = out.trim();
    return branch && branch !== 'HEAD' ? branch : branch === 'HEAD' ? 'HEAD (detached)' : null;
  } catch {
    return null;
  }
}

export async function gitRootOf(dir: string): Promise<string | null> {
  if (!dir || !safeIsDir(dir)) return null;
  try {
    const out = await run('git', ['-C', dir, 'rev-parse', '--show-toplevel']);
    return out.trim() || null;
  } catch {
    return null;
  }
}

function safeIsDir(p: string): boolean {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Process-context assembly + tree walking
// ---------------------------------------------------------------------------

export async function getProcessContext(pid: number): Promise<ProcessContext> {
  const [ppid, binaryName, cwd] = await Promise.all([
    getParentPid(pid),
    getBinaryName(pid),
    getCwd(pid),
  ]);
  const [gitBranch, gitRoot] = await Promise.all([gitBranchOf(cwd), gitRootOf(cwd)]);
  return { pid, ppid, binaryName, cwd, gitBranch, gitRoot };
}

/**
 * Walk PPIDs upward from `startPid`. Stops at pid<=1, at `launchd`, at `cmux`
 * (the terminal host), or after `maxDepth` hops — whichever comes first — so we
 * never loop and never march past the workspace boundary.
 */
export async function resolveProcessChain(
  startPid: number,
  maxDepth = 24,
): Promise<ProcessContext[]> {
  const chain: ProcessContext[] = [];
  let current = startPid;
  const seen = new Set<number>();

  while (current > 1 && !seen.has(current) && chain.length < maxDepth) {
    seen.add(current);
    let ctx: ProcessContext;
    try {
      ctx = await getProcessContext(current);
    } catch {
      break;
    }
    chain.push(ctx);
    if (ctx.binaryName === 'cmux' || ctx.binaryName === 'launchd' || ctx.ppid <= 1) break;
    current = ctx.ppid;
  }
  return chain;
}

// ---------------------------------------------------------------------------
// Port <-> PID association
// ---------------------------------------------------------------------------

/**
 * Map a single listening port to the owning process. `-nP` disables DNS/port
 * name resolution so parsing is deterministic and fast.
 */
export async function mapPortToPid(port: number): Promise<PortMapping | null> {
  try {
    const out = await run('lsof', [
      '-nP',
      `-iTCP:${port}`,
      '-sTCP:LISTEN',
    ]);
    const rows = parseLsofTable(out);
    const first = rows.find((r) => r.port === port);
    if (!first) return null;
    const cwd = await getCwd(first.pid);
    return { port, pid: first.pid, command: first.command, cwd };
  } catch {
    return null; // nothing listening, or lsof failed
  }
}

/** Every LISTENing TCP socket on the machine with its owning PID. */
export async function listListeningPorts(): Promise<PortListener[]> {
  try {
    const out = await run('lsof', ['-nP', '-iTCP', '-sTCP:LISTEN']);
    return parseLsofTable(out);
  } catch (err) {
    log.warn('listListeningPorts: lsof failed', err instanceof Error ? err.message : err);
    return [];
  }
}

/**
 * Parse default (table) `lsof` output. Columns:
 *   COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
 * NAME is like `*:5173`, `127.0.0.1:3000`, `[::1]:8080`. We take the port as the
 * integer after the final `:`.
 */
function parseLsofTable(raw: string): PortListener[] {
  const listeners: PortListener[] = [];
  for (const line of raw.split('\n')) {
    if (!line || line.startsWith('COMMAND')) continue;
    const cols = line.trim().split(/\s+/);
    if (cols.length < 9) continue;
    const command = cols[0] as string;
    const pid = Number.parseInt(cols[1] as string, 10);
    const name = cols[cols.length - 1] as string; // last column = NAME
    const lastColon = name.lastIndexOf(':');
    if (lastColon === -1) continue;
    const port = Number.parseInt(name.slice(lastColon + 1), 10);
    if (!Number.isFinite(pid) || !Number.isFinite(port)) continue;
    listeners.push({
      port,
      pid,
      command,
      address: name.slice(0, lastColon) || '*',
    });
  }
  return listeners;
}
