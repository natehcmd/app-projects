/**
 * Dashboard  (spec §6.1 — Project Folder Matrix Layout)
 * ---------------------------------------------------------------------------
 * Everything is grouped under its Git repository so parallel agent work stays
 * legible. Surfaces render as SurfaceCards; associated Chrome tabs render as a
 * compact rail beside them. Conflicts and Sentinel halts are surfaced as
 * banners with one-click resolution.
 */

import React, { useMemo, useState } from 'react';
import { useConductorSocket } from './useConductorSocket.js';
import { SurfaceCard } from './SurfaceCard.js';
import { DuplicateResolverModal, type ResolverSurface } from './DuplicateResolverModal.js';
import { TerminalModal } from './TerminalModal.js';
import type {
  BrowserTabSnapshot,
  ConflictSnapshot,
  SurfaceSnapshot,
} from '../shared/types.js';

const NO_REPO = '__no_repo__';

export const Dashboard: React.FC = () => {
  const conductor = useConductorSocket();
  const { snapshot, connected, lastUpdate } = conductor;

  const [consoleSurfaceId, setConsoleSurfaceId] = useState<string | null>(null);
  const [activeConflict, setActiveConflict] = useState<ConflictSnapshot | null>(null);

  // --- group surfaces + tabs by repo --------------------------------
  const groups = useMemo(() => {
    const map = new Map<
      string,
      { repoName: string; branch: string | null; rootPath: string; surfaces: SurfaceSnapshot[]; tabs: BrowserTabSnapshot[] }
    >();
    if (!snapshot) return [];

    for (const repo of snapshot.repositories) {
      map.set(repo.rootPath, {
        repoName: repo.repoName,
        branch: repo.currentBranch,
        rootPath: repo.rootPath,
        surfaces: [],
        tabs: [],
      });
    }
    const byName = new Map([...map.values()].map((g) => [g.repoName, g] as const));

    for (const s of snapshot.surfaces) {
      const repo = snapshot.repositories.find((r) => r.activeSurfaces.includes(s.surfaceId));
      const bucket = repo ? map.get(repo.rootPath) : undefined;
      if (bucket) bucket.surfaces.push(s);
      else {
        if (!map.has(NO_REPO))
          map.set(NO_REPO, {
            repoName: 'No repository',
            branch: null,
            rootPath: NO_REPO,
            surfaces: [],
            tabs: [],
          });
        map.get(NO_REPO)!.surfaces.push(s);
      }
    }

    for (const t of snapshot.browserTabs) {
      if (t.associatedRepo && byName.has(t.associatedRepo)) {
        byName.get(t.associatedRepo)!.tabs.push(t);
      }
    }

    return [...map.values()].filter((g) => g.surfaces.length > 0 || g.tabs.length > 0);
  }, [snapshot]);

  const conflictSurfaces: ResolverSurface[] = useMemo(() => {
    if (!activeConflict || !snapshot) return [];
    return activeConflict.surfaceIds
      .map((id) => snapshot.surfaces.find((s) => s.surfaceId === id))
      .filter((s): s is SurfaceSnapshot => Boolean(s))
      .map((s) => ({
        id: s.surfaceId,
        pid: s.pid,
        gitBranch: s.gitBranch,
        cpuPercent: s.cpuPercent,
        memoryMB: s.memoryMB,
        logs: [],
      }));
  }, [activeConflict, snapshot]);

  const sys = snapshot?.system;
  const swarm = snapshot?.swarm;

  return (
    <div className="min-h-full bg-conductor-bg text-slate-200">
      {/* ---- top bar ---- */}
      <header className="sticky top-0 z-30 border-b border-conductor-border bg-conductor-bg/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold tracking-tight text-white">
              Agent Conductor
            </span>
            <span className="font-mono text-[11px] text-slate-500">Cmux Control Tower</span>
          </div>
          <div className="flex items-center gap-4 font-mono text-[11px] text-slate-400">
            {sys && (
              <>
                <span>CPU {sys.cpuLoad.toFixed(1)}%</span>
                <span>
                  RAM {sys.memoryUsageGB.toFixed(1)} / {sys.totalMemoryGB.toFixed(0)} GB
                </span>
              </>
            )}
            <span
              className={`flex items-center gap-1.5 ${connected ? 'text-emerald-400' : 'text-red-400'}`}
            >
              <span
                className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-red-400 animate-pulse'}`}
              />
              {connected ? 'daemon connected' : 'daemon offline'}
            </span>
            {lastUpdate && <span className="text-slate-600">{formatClock(lastUpdate)}</span>}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {/* ---- sentinel halt banner ---- */}
        {swarm?.halted && (
          <div className="mb-5 flex items-center justify-between rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3">
            <div>
              <div className="text-sm font-bold text-red-300">Sentinel halt — pipeline paused</div>
              <div className="mt-0.5 font-mono text-xs text-red-400/80">
                {swarm.haltReason ?? 'unknown reason'}
              </div>
            </div>
            <button
              onClick={() => void conductor.resetSentinel().catch(() => undefined)}
              className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-500"
            >
              Reset Sentinel
            </button>
          </div>
        )}

        {/* ---- conflict banners ---- */}
        {snapshot?.unresolvedConflicts.map((c) => (
          <div
            key={c.groupId}
            className="mb-3 flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-2.5"
          >
            <div className="text-xs text-amber-300">
              <span className="font-semibold">
                {c.type === 'EXACT_DUPLICATE' ? 'Duplicate sessions' : 'Port conflict'}
              </span>{' '}
              <code className="text-amber-400/80">{c.groupId}</code> — {c.surfaceIds.length} surfaces
            </div>
            {c.type === 'EXACT_DUPLICATE' && (
              <button
                onClick={() => setActiveConflict(c)}
                className="rounded-lg border border-amber-500/30 px-3 py-1 text-xs font-semibold text-amber-300 hover:bg-amber-500/10"
              >
                Resolve
              </button>
            )}
          </div>
        ))}

        {/* ---- empty / loading ---- */}
        {!snapshot && (
          <div className="py-24 text-center text-sm text-slate-500">
            Waiting for the first snapshot from the daemon…
          </div>
        )}
        {snapshot && groups.length === 0 && (
          <div className="py-24 text-center text-sm text-slate-500">
            No active surfaces or browser tabs. Start a cmux workspace to populate the matrix.
          </div>
        )}

        {/* ---- project folder matrix ---- */}
        <div className="space-y-8">
          {groups.map((g) => (
            <section key={g.rootPath}>
              <div className="mb-3 flex items-baseline gap-3">
                <h2 className="font-mono text-sm font-semibold text-slate-200">{g.repoName}</h2>
                {g.branch && (
                  <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-indigo-300">
                    {g.branch}
                  </span>
                )}
                {g.rootPath !== NO_REPO && (
                  <span className="font-mono text-[11px] text-slate-600">{g.rootPath}</span>
                )}
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {g.surfaces.map((s) => (
                  <SurfaceCard
                    key={s.surfaceId}
                    surface={s}
                    onFocus={(id) => void conductor.focusSurface(id).catch(() => undefined)}
                    onPrune={(id) => void conductor.pruneSurface(id).catch(() => undefined)}
                    onOpenConsole={setConsoleSurfaceId}
                  />
                ))}
                {g.tabs.map((t) => (
                  <ChromeTabCard key={t.tabId} tab={t} />
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* ---- swarm pipeline strip ---- */}
        {swarm && swarm.activeTasks.length > 0 && (
          <section className="mt-10">
            <h2 className="mb-3 font-mono text-sm font-semibold text-slate-200">Swarm pipeline</h2>
            <div className="overflow-x-auto rounded-xl border border-conductor-border bg-conductor-panel">
              <table className="w-full text-left text-xs">
                <thead className="text-slate-500">
                  <tr className="border-b border-conductor-border">
                    <th className="px-4 py-2 font-medium">Task</th>
                    <th className="px-4 py-2 font-medium">Tier</th>
                    <th className="px-4 py-2 font-medium">Phase</th>
                    <th className="px-4 py-2 font-medium">Worker</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  {swarm.activeTasks.map((t) => (
                    <tr key={t.id} className="border-b border-conductor-border/50 last:border-0">
                      <td className="px-4 py-2 text-slate-300">{t.title}</td>
                      <td className="px-4 py-2 text-slate-400">{t.targetTier}</td>
                      <td className="px-4 py-2 text-indigo-300">{t.phase}</td>
                      <td className="px-4 py-2 text-slate-500">{t.workerId ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>

      {/* ---- modals ---- */}
      <TerminalModal
        isOpen={consoleSurfaceId !== null}
        surfaceId={consoleSurfaceId ?? ''}
        initialLogs=""
        subscribeTerminal={conductor.subscribeTerminal}
        onClose={() => setConsoleSurfaceId(null)}
      />
      <DuplicateResolverModal
        isOpen={activeConflict !== null}
        conflictingGroupName={activeConflict?.groupId ?? ''}
        surfaces={conflictSurfaces}
        onClose={() => setActiveConflict(null)}
        onKeep={(keepId, pruneIds) => {
          void conductor.resolveConflict(keepId, pruneIds).catch(() => undefined);
          setActiveConflict(null);
        }}
      />
    </div>
  );
};

const ChromeTabCard: React.FC<{ tab: BrowserTabSnapshot }> = ({ tab }) => (
  <div className="flex flex-col justify-between rounded-xl border border-conductor-border bg-conductor-panel/60 p-4">
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-xs text-slate-400">chrome</span>
        {tab.isActive && (
          <span className="rounded-full border border-blue-500/20 bg-blue-500/10 px-2 py-0.5 text-[11px] font-semibold text-blue-300">
            active
          </span>
        )}
      </div>
      <div className="line-clamp-2 text-sm font-semibold text-white">{tab.title || 'Untitled'}</div>
      <div className="mt-1 truncate font-mono text-[11px] text-slate-500">{tab.url}</div>
    </div>
  </div>
);

function formatClock(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString();
}
