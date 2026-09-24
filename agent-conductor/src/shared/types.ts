/**
 * Agent Conductor — shared wire contracts.
 *
 * These types are the single source of truth for every payload that crosses
 * the daemon <-> React Control Tower WebSocket boundary. Both `src/daemon/*`
 * and `src/ui/*` import from here so the compiler catches drift between the
 * background process and the foreground UI.
 *
 * Conventions:
 *  - All timestamps are ISO-8601 strings in UTC (`new Date().toISOString()`).
 *  - Durations / cadences are milliseconds unless the field name says otherwise.
 *  - Every message on the socket is a discriminated union keyed on `type`.
 */

// ---------------------------------------------------------------------------
// 1. Domain primitives
// ---------------------------------------------------------------------------

/** Heuristic classification of a single cmux terminal surface. */
export type SurfaceState = 'NEEDS_INPUT' | 'RUNNING' | 'IDLE' | 'DUPLICATE';

/** Signals the daemon will forward to `process.kill(pid, signal)`. */
export type KillSignal = 'SIGTERM' | 'SIGKILL' | 'SIGINT' | 'SIGHUP';

/** Kind of resource collision the dedup engine can surface. */
export type ConflictType = 'EXACT_DUPLICATE' | 'PORT_CONFLICT';

/** Swarm pipeline worker tiers (see spec §4.2 / §4.3). */
export type TargetTier = 'GEMINI_COMPLEX_UI' | 'LOCAL_CODEGEN';

/** Severity ladder shared by the Critic schema and the Sentinel. */
export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

// ---------------------------------------------------------------------------
// 2. Snapshot sub-structures
// ---------------------------------------------------------------------------

export interface SystemVitals {
  /** 1-minute load average normalised to a 0-100 percentage of logical cores. */
  cpuLoad: number;
  memoryUsageGB: number;
  totalMemoryGB: number;
}

export interface RepositorySummary {
  repoName: string;
  rootPath: string;
  currentBranch: string | null;
  /** Surface ids whose CWD resolves inside `rootPath`. */
  activeSurfaces: string[];
}

export interface SurfaceSnapshot {
  surfaceId: string;
  pid: number;
  cwd: string;
  binaryName: string;
  command: string;
  gitBranch: string | null;
  /** TCP ports this surface's process tree is LISTENing on. */
  ports: number[];
  state: SurfaceState;
  cpuPercent: number;
  memoryMB: number;
  lastActive: string;
}

export interface BrowserTabSnapshot {
  tabId: string;
  windowId: number;
  title: string;
  url: string;
  isActive: boolean;
  /** `repoName` of the repository this tab's localhost port maps back to. */
  associatedRepo: string | null;
}

export interface ConflictSnapshot {
  groupId: string;
  type: ConflictType;
  surfaceIds: string[];
}

export interface SwarmSnapshot {
  /** True while the Sentinel has halted the worker fleet. */
  halted: boolean;
  haltReason: string | null;
  activeTasks: SwarmTaskStatus[];
  /** Rolling tail of pipeline state-change log lines for the UI console. */
  recentLog: string[];
}

export interface SwarmTaskStatus {
  id: string;
  title: string;
  targetTier: TargetTier;
  phase: 'IDLE' | 'ALLOCATED' | 'EXECUTING' | 'COMPLETE' | 'WIPING_CONTEXT' | 'VERIFIED_CLEAN';
  workerId: string | null;
  startedAt: string | null;
}

// ---------------------------------------------------------------------------
// 3. Server -> Client messages
// ---------------------------------------------------------------------------

/** Full-fidelity state snapshot, pushed on `SNAPSHOT_INTERVAL_MS` (spec: 1000ms). */
export interface ServerStateUpdate {
  type: 'SERVER_STATE_UPDATE';
  timestamp: string;
  data: {
    system: SystemVitals;
    repositories: RepositorySummary[];
    surfaces: SurfaceSnapshot[];
    browserTabs: BrowserTabSnapshot[];
    unresolvedConflicts: ConflictSnapshot[];
    swarm: SwarmSnapshot;
  };
}

/** Acknowledgement of a control action requested by the client. */
export interface CommandExecOk {
  type: 'COMMAND_EXEC_OK';
  requestId: string;
  timestamp: string;
  result: {
    surfaceId?: string;
    killedPid?: number;
    success: boolean;
    detail?: string;
  };
}

/** Failure reply for a control action (never throws across the socket). */
export interface CommandExecError {
  type: 'COMMAND_EXEC_ERROR';
  requestId: string;
  timestamp: string;
  error: string;
}

/** Incremental terminal output for an open TerminalModal. */
export interface TerminalData {
  type: 'TERMINAL_DATA';
  surfaceId: string;
  chunk: string;
}

export type ServerMessage =
  | ServerStateUpdate
  | CommandExecOk
  | CommandExecError
  | TerminalData;

// ---------------------------------------------------------------------------
// 4. Client -> Server messages
// ---------------------------------------------------------------------------

/** Terminate a surface's process (spec §7.2.B). */
export interface PruneSurfRequest {
  type: 'PRUNE_SURF_REQUEST';
  requestId: string;
  params: {
    surfaceId: string;
    signal: KillSignal;
  };
}

/** Bring a surface to the foreground in cmux. */
export interface FocusSurfRequest {
  type: 'FOCUS_SURF_REQUEST';
  requestId: string;
  params: { surfaceId: string };
}

/** Resolve an EXACT_DUPLICATE group: keep one surface, prune the rest. */
export interface ResolveConflictRequest {
  type: 'RESOLVE_CONFLICT_REQUEST';
  requestId: string;
  params: {
    keepSurfaceId: string;
    pruneSurfaceIds: string[];
    signal: KillSignal;
  };
}

/** Subscribe / unsubscribe to a surface's live TERMINAL_DATA stream. */
export interface TerminalSubscribeRequest {
  type: 'TERMINAL_SUBSCRIBE';
  requestId: string;
  params: { surfaceId: string; subscribe: boolean };
}

/** Manually clear the Sentinel halt latch after operator remediation. */
export interface ResetSentinelRequest {
  type: 'RESET_SENTINEL_REQUEST';
  requestId: string;
}

export type ClientMessage =
  | PruneSurfRequest
  | FocusSurfRequest
  | ResolveConflictRequest
  | TerminalSubscribeRequest
  | ResetSentinelRequest;

// ---------------------------------------------------------------------------
// 5. Type guards (used by the daemon router and the UI reducer)
// ---------------------------------------------------------------------------

export function isClientMessage(value: unknown): value is ClientMessage {
  if (typeof value !== 'object' || value === null) return false;
  const t = (value as { type?: unknown }).type;
  return (
    t === 'PRUNE_SURF_REQUEST' ||
    t === 'FOCUS_SURF_REQUEST' ||
    t === 'RESOLVE_CONFLICT_REQUEST' ||
    t === 'TERMINAL_SUBSCRIBE' ||
    t === 'RESET_SENTINEL_REQUEST'
  );
}

export function isServerMessage(value: unknown): value is ServerMessage {
  if (typeof value !== 'object' || value === null) return false;
  const t = (value as { type?: unknown }).type;
  return (
    t === 'SERVER_STATE_UPDATE' ||
    t === 'COMMAND_EXEC_OK' ||
    t === 'COMMAND_EXEC_ERROR' ||
    t === 'TERMINAL_DATA'
  );
}
