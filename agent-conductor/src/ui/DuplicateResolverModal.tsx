/**
 * DuplicateResolverModal  (spec §6.3)
 * ---------------------------------------------------------------------------
 * Side-by-side comparison of the surfaces in one EXACT_DUPLICATE group. The
 * operator picks which surface to keep; the rest are pruned.
 */

import React from 'react';

export interface ResolverSurface {
  id: string;
  pid: number;
  gitBranch: string | null;
  cpuPercent: number;
  memoryMB: number;
  logs: string[];
}

interface DuplicateResolverModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** e.g. "/Users/dev/code/api::npm run dev" */
  conflictingGroupName: string;
  surfaces: ResolverSurface[];
  onKeep: (keepId: string, pruneIds: string[]) => void;
}

export const DuplicateResolverModal: React.FC<DuplicateResolverModalProps> = ({
  isOpen,
  onClose,
  conflictingGroupName,
  surfaces,
  onKeep,
}) => {
  if (!isOpen) return null;

  const keepAndPruneRest = (keepId: string): void => {
    onKeep(
      keepId,
      surfaces.filter((s) => s.id !== keepId).map((s) => s.id),
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6 backdrop-blur-sm">
      <div className="flex max-h-[85vh] w-full max-w-6xl flex-col rounded-2xl border border-conductor-border bg-conductor-panel shadow-2xl">
        <header className="flex items-center justify-between border-b border-conductor-border p-6">
          <div>
            <h2 className="text-xl font-bold text-white">Resolve Redundant Sessions</h2>
            <p className="mt-1 text-xs text-slate-400">
              Conflict group: <code className="text-indigo-400">{conflictingGroupName}</code>
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-2xl leading-none text-slate-400 hover:text-white"
            aria-label="Close"
          >
            &times;
          </button>
        </header>

        <div className="grid flex-1 grid-cols-1 gap-6 overflow-y-auto bg-black/20 p-6 md:grid-cols-2">
          {surfaces.map((s) => (
            <div
              key={s.id}
              className="flex h-[50vh] flex-col overflow-hidden rounded-xl border border-conductor-border bg-conductor-bg"
            >
              <div className="flex items-center justify-between border-b border-conductor-border bg-conductor-panel p-4">
                <div>
                  <span className="font-mono text-xs text-slate-400">{s.id}</span>
                  <div className="flex items-center gap-2 text-sm font-bold text-white">
                    PID {s.pid}
                    {s.gitBranch && (
                      <span className="text-xs font-medium text-indigo-400">({s.gitBranch})</span>
                    )}
                    <span className="font-mono text-[11px] font-normal text-slate-500">
                      {s.cpuPercent.toFixed(1)}% · {s.memoryMB.toFixed(0)} MB
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => keepAndPruneRest(s.id)}
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white transition-colors hover:bg-emerald-500"
                >
                  Keep this &amp; terminate the rest
                </button>
              </div>
              <div className="flex-1 overflow-y-auto bg-black/40 p-4 font-mono text-xs leading-relaxed text-slate-300">
                {s.logs.length === 0 ? (
                  <span className="italic text-slate-600">No output logged…</span>
                ) : (
                  s.logs.map((line, i) => (
                    <div key={i} className="whitespace-pre-wrap">
                      {line}
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>

        <footer className="flex justify-end gap-3 border-t border-conductor-border p-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-bold text-slate-400 transition-colors hover:text-white"
          >
            Cancel
          </button>
        </footer>
      </div>
    </div>
  );
};
