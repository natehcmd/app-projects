/**
 * TerminalModal  (spec §6.4)
 * ---------------------------------------------------------------------------
 * Wraps an xterm.js instance and streams a surface's live ANSI output. The
 * live feed comes from `subscribeTerminal` (see `useConductorSocket`), which
 * multiplexes TERMINAL_DATA frames from the daemon.
 */

import React, { useEffect, useRef } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';

interface TerminalModalProps {
  isOpen: boolean;
  onClose: () => void;
  surfaceId: string;
  /** Pre-loaded ANSI buffer tail written before the live stream attaches. */
  initialLogs: string;
  /** From useConductorSocket — returns an unsubscribe fn. */
  subscribeTerminal: (surfaceId: string, listener: (chunk: string) => void) => () => void;
}

export const TerminalModal: React.FC<TerminalModalProps> = ({
  isOpen,
  onClose,
  surfaceId,
  initialLogs,
  subscribeTerminal,
}) => {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen || !hostRef.current) return;

    const term = new Terminal({
      theme: { background: '#0b0f19', foreground: '#f8fafc', cursor: '#6366f1' },
      fontFamily: 'JetBrains Mono, Fira Code, monospace',
      fontSize: 12,
      cursorBlink: true,
      scrollback: 5000,
      convertEol: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(hostRef.current);
    fit.fit();

    if (initialLogs) term.write(initialLogs);

    const unsubscribe = subscribeTerminal(surfaceId, (chunk) => term.write(chunk));

    const onResize = (): void => fit.fit();
    window.addEventListener('resize', onResize);

    return () => {
      window.removeEventListener('resize', onResize);
      unsubscribe();
      term.dispose();
    };
  }, [isOpen, surfaceId, initialLogs, subscribeTerminal]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6 backdrop-blur-sm">
      <div className="flex h-[70vh] w-full max-w-4xl flex-col rounded-2xl border border-conductor-border bg-conductor-bg shadow-2xl">
        <header className="flex items-center justify-between border-b border-conductor-border bg-conductor-panel p-4">
          <span className="flex items-center gap-2 text-sm font-bold text-white">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-500" />
            Live console:{' '}
            <code className="font-mono text-xs text-indigo-400">{surfaceId}</code>
          </span>
          <button
            onClick={onClose}
            className="text-2xl leading-none text-slate-400 hover:text-white"
            aria-label="Close"
          >
            &times;
          </button>
        </header>
        <div className="flex-1 overflow-hidden p-4" ref={hostRef} />
      </div>
    </div>
  );
};
