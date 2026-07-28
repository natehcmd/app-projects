/**
 * Hands AI Preload — bridges IPC between main process and renderer.
 * All IPC calls are exposed through contextBridge for security.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("hands", {
  getModels: () => ipcRenderer.invoke("get-models"),
  setModel: (provider, model) => ipcRenderer.invoke("set-model", { provider, model }),
  getConfig: () => ipcRenderer.invoke("get-config"),
  saveConfig: (data) => ipcRenderer.invoke("save-config", data),
  getHealth: () => ipcRenderer.invoke("get-health"),
  hideWindow: () => ipcRenderer.invoke("hide-window"),
  onModelChanged: (cb) => ipcRenderer.on("model-changed", (_event, data) => cb(data)),
  // Chat history persistence
  loadHistory: () => ipcRenderer.invoke("load-history"),
  saveHistory: (messages) => ipcRenderer.invoke("save-history", messages),
  clearHistory: () => ipcRenderer.invoke("clear-history"),
});
