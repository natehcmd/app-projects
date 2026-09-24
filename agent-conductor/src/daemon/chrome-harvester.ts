/**
 * Chrome Tab & DevTools Harvester  (spec §2)
 * ---------------------------------------------------------------------------
 * Two independent strategies, used together:
 *
 *   1. JXA (JavaScript for Automation) via `osascript -l JavaScript`.
 *      Native, memory-safe, no debug flag required. Gives us window/tab
 *      structure, titles, URLs and which tab is active. This is the primary
 *      source for the snapshot's `browserTabs`.
 *
 *   2. Chrome DevTools Protocol over HTTP/WebSocket (`localhost:9222`).
 *      Only available when Chrome was launched with
 *      `--remote-debugging-port=9222`. Used for deeper automation such as
 *      streaming console errors from a page. Optional; absence is not an error.
 *
 * macOS notes:
 *   - `osascript` will prompt the user for Automation permission the first time
 *     the daemon talks to "Google Chrome". That prompt is a one-time TCC grant.
 *   - If Chrome is not running, JXA returns `[]` rather than throwing.
 */

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import axios from 'axios';
import WebSocket from 'ws';
import { createLogger } from './logger.js';

const execFileAsync = promisify(execFile);
const log = createLogger('chrome');

export interface ChromeTab {
  windowId: number;
  tabIndex: number; // 1-indexed, matches AppleScript semantics
  title: string;
  url: string;
  isActive: boolean;
  /** Parsed loopback port if the URL points at localhost / 127.0.0.1 / [::1]. */
  localPort: number | null;
}

// ---------------------------------------------------------------------------
// 1. JXA tab harvest
// ---------------------------------------------------------------------------

/**
 * Self-contained JXA program. Kept as a single string so it can be handed to
 * `osascript -l JavaScript -e`. Returns a JSON array on stdout.
 */
const JXA_HARVEST_TABS = `
function run() {
  const chrome = Application('Google Chrome');
  if (!chrome.running()) return JSON.stringify([]);
  const out = [];
  const windows = chrome.windows();
  for (let w = 0; w < windows.length; w++) {
    const win = windows[w];
    let winId, activeIdx, tabs;
    try { winId = win.id(); activeIdx = win.activeTabIndex(); tabs = win.tabs(); }
    catch (e) { continue; }
    for (let t = 0; t < tabs.length; t++) {
      const tab = tabs[t];
      let title = '', url = '';
      try { title = tab.title(); } catch (e) {}
      try { url = tab.url(); } catch (e) {}
      out.push({
        windowId: winId,
        tabIndex: t + 1,
        title: title,
        url: url,
        isActive: (t + 1) === activeIdx
      });
    }
  }
  return JSON.stringify(out);
}
`;

interface RawJxaTab {
  windowId: number;
  tabIndex: number;
  title: string;
  url: string;
  isActive: boolean;
}

export async function harvestChromeTabs(): Promise<ChromeTab[]> {
  try {
    const { stdout } = await execFileAsync(
      'osascript',
      ['-l', 'JavaScript', '-e', JXA_HARVEST_TABS],
      { timeout: 5_000, maxBuffer: 4 * 1024 * 1024 },
    );
    const raw = JSON.parse(stdout.trim() || '[]') as RawJxaTab[];
    return raw.map((t) => ({
      ...t,
      localPort: parseLoopbackPort(t.url),
    }));
  } catch (err) {
    // Automation permission denied, Chrome mid-relaunch, script error, etc.
    log.warn('JXA tab harvest failed; treating Chrome as having no tabs', errText(err));
    return [];
  }
}

/**
 * Extract the port from a loopback URL. Returns `null` for non-local URLs.
 * Handles: http://localhost:5173, http://127.0.0.1:3000, http://[::1]:8080,
 * and the implicit 80/443 when the port is omitted.
 */
export function parseLoopbackPort(rawUrl: string): number | null {
  let u: URL;
  try {
    u = new URL(rawUrl);
  } catch {
    return null;
  }
  const host = u.hostname.toLowerCase();
  const isLoopback =
    host === 'localhost' ||
    host === '127.0.0.1' ||
    host === '[::1]' ||
    host === '::1' ||
    host.endsWith('.localhost');
  if (!isLoopback) return null;
  if (u.port) return Number.parseInt(u.port, 10);
  if (u.protocol === 'https:') return 443;
  if (u.protocol === 'http:') return 80;
  return null;
}

// ---------------------------------------------------------------------------
// 2. Chrome DevTools Protocol explorer
// ---------------------------------------------------------------------------

export interface CDPTarget {
  id: string;
  title: string;
  type: string;
  url: string;
  webSocketDebuggerUrl: string;
}

export class CDPHarvester {
  private readonly port: number;

  constructor(port: number = Number.parseInt(process.env.CDP_PORT || '9222', 10)) {
    this.port = port;
  }

  /** List page targets from the CDP HTTP endpoint. Throws with actionable text. */
  async listTabs(): Promise<CDPTarget[]> {
    try {
      const res = await axios.get<CDPTarget[]>(
        `http://localhost:${this.port}/json/list`,
        { timeout: 3_000 },
      );
      return res.data.filter((t) => t.type === 'page');
    } catch {
      throw new Error(
        `Chrome DevTools not reachable on port ${this.port}. ` +
          `Launch Chrome with --remote-debugging-port=${this.port} to enable CDP features.`,
      );
    }
  }

  /**
   * Attach to a page target and stream console output. Enables the Console and
   * Runtime domains, then forwards `Runtime.consoleAPICalled` /
   * `Console.messageAdded` params to `onEntry`. Returns the open socket so the
   * caller owns its lifecycle.
   */
  listenToTabConsole(
    webSocketDebuggerUrl: string,
    onEntry: (params: unknown) => void,
  ): Promise<WebSocket> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(webSocketDebuggerUrl);
      ws.on('open', () => {
        ws.send(JSON.stringify({ id: 1, method: 'Console.enable' }));
        ws.send(JSON.stringify({ id: 2, method: 'Runtime.enable' }));
        resolve(ws);
      });
      ws.on('message', (data: WebSocket.RawData) => {
        try {
          const payload = JSON.parse(data.toString()) as {
            method?: string;
            params?: unknown;
          };
          if (
            payload.method === 'Runtime.consoleAPICalled' ||
            payload.method === 'Console.messageAdded'
          ) {
            onEntry(payload.params);
          }
        } catch {
          /* ignore malformed CDP frame */
        }
      });
      ws.on('error', reject);
    });
  }
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
