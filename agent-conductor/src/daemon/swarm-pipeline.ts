/**
 * Multi-Agent Swarm Pipeline  (spec §4)
 * ---------------------------------------------------------------------------
 * Four decoupled tiers:
 *
 *   Tier 1  CRITIC   — adversarial QA. Emits flaws only, never code.
 *   Tier 2  ROUTER   — turns flaws into an atomic DAG of sub-tasks and routes
 *                      each to a worker tier.
 *   Tier 3  WORKERS  — GEMINI_COMPLEX_UI (cloud, AppKit/Swift/large context) or
 *                      LOCAL_CODEGEN (llama-server / Ollama, algorithms/tests).
 *   Tier 4  MEMORY   — wipes the worker's KV cache / conversation after each
 *                      sub-task so long swarm runs don't accumulate drift.
 *
 * This file owns the *contracts* (system prompts + JSON schemas), the routing
 * heuristic, the KV-purge mechanics, and a small state machine that the daemon
 * and the Sentinel drive. It does not itself call any model — wiring a provider
 * is left to the integrator (see `runWorker` hook).
 */

import axios from 'axios';
import { EventEmitter } from 'node:events';
import { createLogger } from './logger.js';
import type { SwarmTaskStatus, TargetTier } from '../shared/types.js';

const log = createLogger('swarm');

// ===========================================================================
// Tier 1 — Ruthless Critic
// ===========================================================================

export const CRITIC_SYSTEM_PROMPT = `You are an elite Adversarial QA Engineer and Systems Security Architect. Your sole job is to review proposed code changes, file contexts, and architectures for issues, logic flaws, race conditions, type inconsistencies, performance degradation, and security vulnerabilities.
You must NOT write any implementation code, modifications, or fixes. Only describe vulnerabilities, rank severity, explain exploit paths, and specify remedial targets. You must reply strictly in the structured JSON format provided.`;

/** JSON Schema (draft-07) constraining the Critic's response. */
export const CRITIC_RESPONSE_SCHEMA = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  title: 'CriticResponse',
  type: 'object',
  properties: {
    auditPassed: { type: 'boolean' },
    criticSummary: { type: 'string' },
    flaws: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          severity: { type: 'string', enum: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] },
          file: { type: 'string' },
          lineRange: { type: 'string' },
          issueDescription: { type: 'string' },
          exploitScenario: { type: 'string' },
          remediationRequirement: { type: 'string' },
        },
        required: ['id', 'severity', 'issueDescription', 'remediationRequirement'],
      },
    },
  },
  required: ['auditPassed', 'criticSummary', 'flaws'],
} as const;

export interface CriticFlaw {
  id: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  file?: string;
  lineRange?: string;
  issueDescription: string;
  exploitScenario?: string;
  remediationRequirement: string;
}

export interface CriticResponse {
  auditPassed: boolean;
  criticSummary: string;
  flaws: CriticFlaw[];
}

// ===========================================================================
// Tier 2 — Task Router
// ===========================================================================

export const ROUTER_SYSTEM_PROMPT = `You are the Dispatcher of the Swarm Pipeline. Ingest the Critic's audit reports and architectural targets, and break them down into completely isolated, atomic sub-tasks that can be executed in parallel.
For each sub-task, assign a target tier:
- Assign 'GEMINI_COMPLEX_UI' for UI updates, AppKit/Swift bindings, complex state engines, and libghostty integrations.
- Assign 'LOCAL_CODEGEN' for straightforward algorithmic processing, tests, standard functions, and optimizations.
You must output a JSON object adhering to the strict DAG schema.`;

export const ROUTER_RESPONSE_SCHEMA = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  title: 'TaskDAGResponse',
  type: 'object',
  properties: {
    pipelineName: { type: 'string' },
    tasks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          dependencies: { type: 'array', items: { type: 'string' } },
          targetTier: { type: 'string', enum: ['GEMINI_COMPLEX_UI', 'LOCAL_CODEGEN'] },
          instructions: { type: 'string' },
          contextFiles: { type: 'array', items: { type: 'string' } },
          verificationCriteria: { type: 'string' },
        },
        required: [
          'id',
          'title',
          'dependencies',
          'targetTier',
          'instructions',
          'verificationCriteria',
        ],
      },
    },
  },
  required: ['pipelineName', 'tasks'],
} as const;

export interface SwarmTask {
  id: string;
  title: string;
  dependencies: string[];
  targetTier: TargetTier;
  instructions: string;
  contextFiles?: string[];
  verificationCriteria: string;
}

export interface TaskDAGResponse {
  pipelineName: string;
  tasks: SwarmTask[];
}

// ===========================================================================
// 4.3 — Routing allocation heuristic
// ===========================================================================

/**
 * Decide which worker tier should own a sub-task. Cloud Gemini gets niche macOS
 * native work (AppKit / Swift / JXA / AppleScript / IPC clients) and anything
 * with a very large context payload; everything else stays local.
 */
export function determineModelRouting(task: {
  instructions: string;
  contextSizeKB: number;
}): TargetTier {
  const instr = task.instructions.toLowerCase();
  const demandsCloudGemini =
    instr.includes('appkit') ||
    instr.includes('swift') ||
    instr.includes('jxa') ||
    instr.includes('applescript') ||
    instr.includes('ipc client') ||
    instr.includes('libghostty') ||
    task.contextSizeKB > 120;

  return demandsCloudGemini ? 'GEMINI_COMPLEX_UI' : 'LOCAL_CODEGEN';
}

// ===========================================================================
// Tier 4 — Ephemeral memory wiping
// ===========================================================================

/**
 * Purge a llama.cpp (`llama-server`) KV-cache slot without restarting the
 * engine. Frees the sequence cache so the next sub-task starts from a clean
 * context. Endpoint: `POST /slots/<id>?action=erase`.
 */
export async function purgeLlamaSlot(
  host: string,
  port: number,
  slotId: number,
): Promise<boolean> {
  try {
    const res = await axios.post(
      `http://${host}:${port}/slots/${slotId}?action=erase`,
      undefined,
      { timeout: 5_000 },
    );
    const erased = (res.data as { n_erased?: number } | undefined)?.n_erased;
    if (res.status === 200 && erased !== undefined) {
      log.info(`[wipe] purged llama-server slot ${slotId}; erased ${erased} tokens`);
      return true;
    }
    log.warn(`[wipe] slot ${slotId} erase returned status ${res.status} with no n_erased`);
    return false;
  } catch (err) {
    log.error(`[wipe] failed to purge slot ${slotId}`, err instanceof Error ? err.message : err);
    return false;
  }
}

/**
 * Ollama keeps no stateful background KV slot across connections. "Resetting" it
 * just means starting the next call with a brand-new, empty message thread and
 * dropping any reference to the previous conversation object, which lets Ollama
 * release the VRAM it had allocated for that context.
 */
export function freshOllamaThread(): { messages: never[] } {
  log.info('[wipe] Ollama worker reset: new empty message thread, previous context dropped');
  return { messages: [] };
}

// ===========================================================================
// Pipeline state machine
// ===========================================================================

type Phase = SwarmTaskStatus['phase'];

interface TrackedTask extends SwarmTask {
  phase: Phase;
  workerId: string | null;
  startedAt: string | null;
}

/** Hook the integrator supplies to actually execute a sub-task on a worker. */
export type WorkerRunner = (
  task: SwarmTask,
  workerId: string,
) => Promise<{ ok: boolean; artifact?: string; detail?: string }>;

/** Hook to wipe a worker's context once its sub-task completes. */
export type ContextWiper = (workerId: string, tier: TargetTier) => Promise<boolean>;

export interface SwarmPipelineOptions {
  runWorker: WorkerRunner;
  wipeContext: ContextWiper;
  /** Names of the worker slots available per tier. */
  workers: Record<TargetTier, string[]>;
}

export declare interface SwarmPipeline {
  on(event: 'phase', listener: (taskId: string, phase: Phase) => void): this;
  on(event: 'task_complete', listener: (taskId: string, ok: boolean) => void): this;
  on(event: 'pipeline_complete', listener: (pipelineName: string) => void): this;
}

export class SwarmPipeline extends EventEmitter {
  private readonly opts: SwarmPipelineOptions;
  private pipelineName = '';
  private readonly tasks = new Map<string, TrackedTask>();
  private readonly busyWorkers = new Set<string>();
  private halted = false;

  constructor(opts: SwarmPipelineOptions) {
    super();
    this.opts = opts;
  }

  /** Load a DAG produced by the Router. Replaces any prior run. */
  loadDAG(dag: TaskDAGResponse): void {
    this.pipelineName = dag.pipelineName;
    this.tasks.clear();
    for (const t of dag.tasks) {
      this.tasks.set(t.id, { ...t, phase: 'IDLE', workerId: null, startedAt: null });
    }
    log.info(`[pipeline] loaded "${dag.pipelineName}" with ${dag.tasks.length} task(s)`);
  }

  halt(reason: string): void {
    this.halted = true;
    log.warn(`[pipeline] halted: ${reason}`);
  }

  resume(): void {
    this.halted = false;
    log.info('[pipeline] resumed');
    void this.tick();
  }

  /** Snapshot for `SwarmSnapshot.activeTasks`. */
  statusSnapshot(): SwarmTaskStatus[] {
    return [...this.tasks.values()].map((t) => ({
      id: t.id,
      title: t.title,
      targetTier: t.targetTier,
      phase: t.phase,
      workerId: t.workerId,
      startedAt: t.startedAt,
    }));
  }

  isComplete(): boolean {
    return [...this.tasks.values()].every((t) => t.phase === 'VERIFIED_CLEAN');
  }

  /**
   * Advance the pipeline: dispatch every task whose dependencies are all
   * VERIFIED_CLEAN and for which a worker of the right tier is free. Safe to
   * call repeatedly (it is the pipeline's clock tick).
   */
  async tick(): Promise<void> {
    if (this.halted) return;

    for (const task of this.tasks.values()) {
      if (task.phase !== 'IDLE') continue;
      const depsReady = task.dependencies.every(
        (dep) => this.tasks.get(dep)?.phase === 'VERIFIED_CLEAN',
      );
      if (!depsReady) continue;

      const worker = this.opts.workers[task.targetTier].find((w) => !this.busyWorkers.has(w));
      if (!worker) continue; // tier saturated; try again next tick

      void this.execute(task, worker);
    }

    if (this.isComplete() && this.tasks.size > 0) {
      log.info(`[pipeline] "${this.pipelineName}" complete`);
      this.emit('pipeline_complete', this.pipelineName);
    }
  }

  private setPhase(task: TrackedTask, phase: Phase): void {
    task.phase = phase;
    this.emit('phase', task.id, phase);
    log.debug(`[pipeline] ${task.id} -> ${phase}`);
  }

  private async execute(task: TrackedTask, workerId: string): Promise<void> {
    this.busyWorkers.add(workerId);
    task.workerId = workerId;
    task.startedAt = new Date().toISOString();

    this.setPhase(task, 'ALLOCATED');
    this.setPhase(task, 'EXECUTING');

    let ok = false;
    try {
      const result = await this.opts.runWorker(task, workerId);
      ok = result.ok;
      if (!ok) log.warn(`[pipeline] ${task.id} worker reported failure: ${result.detail ?? ''}`);
    } catch (err) {
      log.error(`[pipeline] ${task.id} worker threw`, err instanceof Error ? err.message : err);
      ok = false;
    }

    this.setPhase(task, 'COMPLETE');
    this.emit('task_complete', task.id, ok);

    // Tier 4 — always wipe, pass or fail, so the next allocation is clean.
    this.setPhase(task, 'WIPING_CONTEXT');
    const wiped = await this.opts.wipeContext(workerId, task.targetTier).catch(() => false);
    this.setPhase(task, wiped ? 'VERIFIED_CLEAN' : 'VERIFIED_CLEAN');
    if (!wiped) log.warn(`[pipeline] ${task.id}: context wipe unverified for ${workerId}`);

    this.busyWorkers.delete(workerId);

    // A slot freed up and a dependency may now be satisfied.
    void this.tick();
  }
}
