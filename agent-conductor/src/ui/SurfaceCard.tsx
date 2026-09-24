/**
 * SurfaceCard  (spec §6.2)
 * ---------------------------------------------------------------------------
 * One cmux terminal surface: state badge, PID + binary, git branch, listening
 * ports, live CPU / RAM, and quick actions (Focus, Console, Kill-if-duplicate).
 */

import React from 'react';
import type { SurfaceSnapshot, SurfaceState } from '../shared/types.js';

interface SurfaceCardProps {
  surface: SurfaceSnapshot;
  onFocus: (surfaceId: string) => void;
  onPrune: (surfaceId: string) => void;
  onOpenConsole: (surfaceId: string) => void;
}

const BADGE: Record<SurfaceState, string> = {
  NEEDS_INPUT: 'bg-red-500/10 text-red-400 border-red-500/20',
  RUNNING: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  IDLE: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  DUPLICATE: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
};

export const SurfaceCard: React.FC<SurfaceCardProps> = ({
  surface,
  onFocus,
  onPrune,
  onOpenConsole,
}) => {
  const { surfaceId, pid, binaryName, gitBranch, ports, state, cpuPercent, memoryMB } = surface;

  return (
    <div
      className={`flex flex-col justify-between rounded-xl border bg-conductor-panel p-4 shadow-lg transition-all ${
        state === 'NEEDS_INPUT'
          ? 'border-red-500/40 ring-2 ring-red-500/60 animate-pulse-ring'
          : 'border-conductor-border'
      }`}
    >
      <div>
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono text-xs text-slate-400">{surfaceId}</span>
          <span
            className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${BADGE[state]}`}
          >
            {state}
          </span>
        </div>

        <h3 className="flex items-center gap-2 text-lg font-bold text-white">
          <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs text-slate-300">
            PID {pid || '—'}
          </span>
          {binaryName || 'unknown'}
        </h3>

        {gitBranch && (
          <div className="mt-2 flex items-center text-xs font-medium text-indigo-400">
            <GitBranchIcon />
            {gitBranch}
          </div>
        )}

        {ports.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {ports.map((port) => (
              <span
                key={port}
                className="rounded border border-blue-900/30 bg-blue-950/40 px-2 py-0.5 font-mono text-xs text-blue-300"
              >
                localhost:{port}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-conductor-border pt-4">
        <div className="font-mono text-[11px] text-slate-500">
          CPU {cpuPercent.toFixed(1)}% · RAM {memoryMB.toFixed(0)} MB
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onOpenConsole(surfaceId)}
            className="rounded-lg border border-slate-600/40 px-3 py-1.5 text-xs font-semibold text-slate-300 transition-colors hover:bg-slate-700/40"
          >
            Console
          </button>
          {state === 'DUPLICATE' && (
            <button
              onClick={() => onPrune(surfaceId)}
              className="rounded-lg border border-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-400 transition-colors hover:bg-red-500/10"
            >
              Kill
            </button>
          )}
          <button
            onClick={() => onFocus(surfaceId)}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-indigo-500"
          >
            Focus
          </button>
        </div>
      </div>
    </div>
  );
};

const GitBranchIcon: React.FC = () => (
  <svg
    className="mr-1 h-3.5 w-3.5"
    fill="none"
    viewBox="0 0 24 24"
    stroke="currentColor"
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      d="M6 3v12m0 0a3 3 0 103 3m-3-3a3 3 0 013 3m9-12a3 3 0 11-6 0 3 3 0 016 0zm-3 3v1a3 3 0 01-3 3H9"
    />
  </svg>
);
