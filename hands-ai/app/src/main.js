/**
 * Hands AI Electron Main Process
 * Manages the floating panel window, tray, global shortcut, and daemon lifecycle.
 */

const {
  app,
  BrowserWindow,
  globalShortcut,
  Tray,
  Menu,
  ipcMain,
  nativeImage,
  shell,
} = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn, execSync } = require("child_process");
const http = require("http");
const os = require("os");

const DAEMON_URL = "http://127.0.0.1:7721";
let mainWindow = null;
let tray = null;
let daemonProcess = null;
let daemonLogFd = null;
let windowVisible = false;

// ── Daemon helpers ────────────────────────────────────────────────────────────

function daemonRequest(method, endpoint, body = null) {
  return new Promise((resolve, reject) => {
    const url = new URL(DAEMON_URL + endpoint);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method,
      headers: { "Content-Type": "application/json" },
    };

    const req = http.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          resolve({ raw: data });
        }
      });
    });

    req.on("error", reject);
    req.setTimeout(5000, () => {
      req.destroy(new Error("timeout"));
    });

    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

async function isDaemonRunning() {
  try {
    await daemonRequest("GET", "/health");
    return true;
  } catch {
    return false;
  }
}

async function startDaemon() {
  const agentDir = path.join(__dirname, "..", "..", "agent");
  const logPath = path.join(os.homedir(), ".hands", "daemon.log");

  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const logFd = fs.openSync(logPath, "a");
  daemonLogFd = logFd;

  // Use venv python if available, otherwise fall back to python3.12 or python3
  const venvPython = path.join(agentDir, ".venv", "bin", "python3");
  const pythonBin = fs.existsSync(venvPython) ? venvPython : (
    ["/opt/homebrew/bin/python3.12", "/usr/bin/python3", "python3"].find((p) => {
      try { require("fs").accessSync(p); return true; } catch { return false; }
    }) || "python3"
  );

  daemonProcess = spawn(
    pythonBin,
    ["-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "7721"],
    {
      cwd: agentDir,
      detached: false,
      stdio: ["ignore", logFd, logFd],
    }
  );

  daemonProcess.on("error", (err) => {
    console.error("Daemon process error:", err);
    closeDaemonLog();
  });

  daemonProcess.on("exit", () => {
    closeDaemonLog();
  });

  // Wait up to 8 seconds for daemon to start
  for (let i = 0; i < 16; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await isDaemonRunning()) {
      console.log("Hands AI daemon started.");
      return true;
    }
  }

  console.error("Daemon failed to start. Check ~/.hands/daemon.log");
  return false;
}

function closeDaemonLog() {
  if (daemonLogFd !== null) {
    try {
      fs.closeSync(daemonLogFd);
    } catch {
      // best effort cleanup
    }
    daemonLogFd = null;
  }
}

// ── Window ───────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 420,
    height: 620,
    show: false,
    frame: false,
    alwaysOnTop: true,
    resizable: true,
    transparent: false,
    vibrancy: "under-window", // macOS glass effect
    visualEffectState: "active",
    backgroundColor: "#0d0d0d",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: "hidden",
    roundedCorners: true,
  });

  mainWindow.loadFile(path.join(__dirname, "index.html"));

  mainWindow.on("blur", () => {
    // Hide on blur unless devtools are open
    if (!mainWindow.webContents.isDevToolsOpened()) {
      mainWindow.hide();
      windowVisible = false;
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function toggleWindow() {
  if (!mainWindow) return;

  if (windowVisible) {
    mainWindow.hide();
    windowVisible = false;
  } else {
    // Center on screen
    const { screen } = require("electron");
    const display = screen.getPrimaryDisplay();
    const { width, height } = display.workAreaSize;
    const winBounds = mainWindow.getBounds();
    mainWindow.setPosition(
      Math.round(width / 2 - winBounds.width / 2),
      Math.round(height / 2 - winBounds.height / 2)
    );
    mainWindow.show();
    mainWindow.focus();
    windowVisible = true;
  }
}

// ── Tray ─────────────────────────────────────────────────────────────────────

let daemonOnline = false;
let activeModel = "auto";
let activeProvider = "ollama";

function getTrayIcon(online) {
  // Template image: black hand on transparent bg — macOS auto-inverts for dark mode
  const iconPath = path.join(__dirname, "..", "assets", online ? "iconTemplate.png" : "iconOfflineTemplate.png");
  const fs = require("fs");
  if (fs.existsSync(iconPath)) {
    const img = nativeImage.createFromPath(iconPath);
    img.setTemplateImage(true);
    return img;
  }
  // Fallback: draw a minimal hand icon inline
  return buildInlineIcon(online);
}

function buildInlineIcon(online) {
  // 22x22 RGBA hand silhouette as raw buffer
  const { width: W, height: H } = { width: 22, height: 22 };
  const buf = Buffer.alloc(W * H * 4, 0);

  function px(x, y, a = 255) {
    if (x < 0 || x >= W || y < 0 || y >= H) return;
    const i = (y * W + x) * 4;
    buf[i] = 0; buf[i+1] = 0; buf[i+2] = 0; buf[i+3] = a;
  }
  function rect(x1, y1, x2, y2) {
    for (let y = y1; y <= y2; y++) for (let x = x1; x <= x2; x++) px(x, y);
  }

  // Hand shape
  rect(4, 14, 17, 19);  // palm
  rect(2, 10, 5, 16);   // thumb
  px(2, 9); px(3, 9);
  rect(5, 5, 7, 14);    // index
  rect(9, 3, 11, 14);   // middle
  rect(13, 5, 15, 14);  // ring
  rect(16, 7, 18, 14);  // pinky

  // If offline, draw an X over the bottom right corner
  if (!online) {
    for (let i = 0; i < 4; i++) { px(15+i, 17+i, 200); px(18-i+1, 17+i, 200); }
  }

  const img = nativeImage.createFromBuffer(buf, { width: W, height: H });
  img.setTemplateImage(true);
  return img;
}

function rebuildTrayMenu() {
  if (!tray) return;

  const modelLabel = `${activeProvider} · ${activeModel}`;
  const statusLabel = daemonOnline ? `● Online · ${modelLabel}` : "○ Daemon offline";

  const contextMenu = Menu.buildFromTemplate([
    { label: "Hands AI", enabled: false },
    { label: statusLabel, enabled: false },
    { type: "separator" },
    {
      label: "Show / Hide",
      accelerator: process.platform === "darwin" ? "Option+Space" : "Alt+Space",
      click: toggleWindow,
    },
    { type: "separator" },
    {
      label: "Open Config",
      click: () => shell.openPath(path.join(os.homedir(), ".hands")),
    },
    {
      label: "View Daemon Log",
      click: () => shell.openPath(path.join(os.homedir(), ".hands", "daemon.log")),
    },
    { type: "separator" },
    { label: "Quit Hands AI", role: "quit" },
  ]);

  tray.setContextMenu(contextMenu);
  tray.setToolTip(daemonOnline ? `Hands AI · ${modelLabel} · online` : "Hands AI · offline");
}

function createTray() {
  tray = new Tray(getTrayIcon(false));
  tray.on("click", toggleWindow);
  rebuildTrayMenu();

  // Poll daemon every 5s to update online/offline status + icon
  setInterval(async () => {
    try {
      const health = await daemonRequest("GET", "/health");
      const wasOnline = daemonOnline;
      const previousProvider = activeProvider;
      const previousModel = activeModel;
      daemonOnline = health.status === "ok";
      activeProvider = health.active_provider || activeProvider;
      activeModel = health.active_model || activeModel;
      tray.setImage(getTrayIcon(daemonOnline));
      if (
        daemonOnline !== wasOnline ||
        activeProvider !== previousProvider ||
        activeModel !== previousModel
      ) {
        rebuildTrayMenu();
      }
    } catch (_) {
      if (daemonOnline) {
        daemonOnline = false;
        tray.setImage(getTrayIcon(false));
        rebuildTrayMenu();
      }
    }
  }, 5000);
}

// ── IPC handlers ──────────────────────────────────────────────────────────────

ipcMain.handle("get-models", async () => {
  try {
    return await daemonRequest("GET", "/models");
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle("set-model", async (event, { provider, model }) => {
  try {
    return await daemonRequest("POST", "/model/set", { provider, model });
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle("get-config", async () => {
  try {
    return await daemonRequest("GET", "/config");
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle("save-config", async (event, configData) => {
  try {
    return await daemonRequest("POST", "/config", configData);
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle("get-health", async () => {
  try {
    return await daemonRequest("GET", "/health");
  } catch (e) {
    return { error: e.message, status: "unreachable" };
  }
});

ipcMain.handle("hide-window", () => {
  if (mainWindow) {
    mainWindow.hide();
    windowVisible = false;
  }
});

// ── Chat history persistence ──────────────────────────────────────────────────

const HISTORY_PATH = path.join(os.homedir(), ".hands", "history.json");
const MAX_HISTORY = 200; // keep last 200 messages

ipcMain.handle("load-history", () => {
  try {
    if (fs.existsSync(HISTORY_PATH)) {
      const raw = fs.readFileSync(HISTORY_PATH, "utf8");
      return JSON.parse(raw);
    }
  } catch (_) {}
  return [];
});

ipcMain.handle("save-history", (_event, messages) => {
  try {
    fs.mkdirSync(path.dirname(HISTORY_PATH), { recursive: true });
    const trimmed = messages.slice(-MAX_HISTORY);
    fs.writeFileSync(HISTORY_PATH, JSON.stringify(trimmed, null, 2), { mode: 0o600 });
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

ipcMain.handle("clear-history", () => {
  try {
    if (fs.existsSync(HISTORY_PATH)) fs.unlinkSync(HISTORY_PATH);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  createWindow();
  createTray();

  // Register Option+Space (Mac) / Alt+Space (Win/Linux) global shortcut
  const shortcut = process.platform === "darwin" ? "Option+Space" : "Alt+Space";
  const registered = globalShortcut.register(shortcut, toggleWindow);
  if (!registered) {
    console.warn(`Could not register global shortcut: ${shortcut}`);
  }

  // Check/start daemon
  const running = await isDaemonRunning();
  if (!running) {
    console.log("Daemon not running, starting...");
    await startDaemon();
  } else {
    console.log("Daemon already running.");
  }

  // Show window on first launch
  toggleWindow();
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
  if (daemonProcess) {
    daemonProcess.kill();
    closeDaemonLog();
  }
});

app.on("window-all-closed", () => {
  // Keep running in tray on all platforms
  // Don't call app.quit()
});
