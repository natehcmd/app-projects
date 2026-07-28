/**
 * Hands AI Renderer — all UI logic for chat, model switching, settings.
 */

const DAEMON_URL = "http://127.0.0.1:7721";

// ── State ─────────────────────────────────────────────────────────────────────
let conversation = [];
let activeProvider = null;
let activeModel = null;
let daemonOnline = false;
let allModels = [];
let modelPanelOpen = false;
let settingsPanelOpen = false;
let streaming = false;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $chatArea = document.getElementById("chat-area");
const $chatInput = document.getElementById("chat-input");
const $sendBtn = document.getElementById("send-btn");
const $statusDot = document.getElementById("status-dot");
const $modelBadge = document.getElementById("model-badge");
const $modelPanel = document.getElementById("model-panel");
const $modelListContainer = document.getElementById("model-list-container");
const $connectingMsg = document.getElementById("connecting-msg");
const $settingsPanel = document.getElementById("settings-panel");
const $anthropicKey = document.getElementById("s-anthropic-key");
const $openaiKey = document.getElementById("s-openai-key");
const $ollamaHost = document.getElementById("s-ollama-host");
const $saveStatus = document.getElementById("save-status");

// ── Health polling ────────────────────────────────────────────────────────────
async function pollHealth() {
  try {
    const health = await window.hands.getHealth();
    if (health && health.status === "ok") {
      setOnline(health.active_provider, health.active_model);
    } else {
      setOffline();
    }
  } catch {
    setOffline();
  }
}

async function loadPersistedHistory() {
  try {
    const messages = await window.hands.loadHistory();
    if (!messages || messages.length === 0) return;
    conversation = messages;
    // Render each saved message into the chat area
    for (const msg of messages) {
      appendMessage(msg.role, msg.content);
    }
    scrollToBottom();
    // Add a subtle divider so user knows where the old session ended
    const divider = document.createElement("div");
    divider.className = "history-divider";
    divider.textContent = "── previous session ──";
    $chatArea.appendChild(divider);
    scrollToBottom();
  } catch (_) {}
}

function setOnline(provider, model) {
  const wasOffline = !daemonOnline;
  daemonOnline = true;
  activeProvider = provider;
  activeModel = model;
  $statusDot.className = "online";
  $statusDot.title = "Daemon status: online";
  $modelBadge.textContent = `${provider || "—"} / ${model || "—"}`;
  $sendBtn.disabled = streaming;
  if (wasOffline) {
    $connectingMsg && $connectingMsg.remove();
    loadPersistedHistory();
  }
}

function setOffline() {
  daemonOnline = false;
  $statusDot.className = "offline";
  $statusDot.title = "Daemon status: offline";
  $modelBadge.textContent = "— disconnected —";
  $sendBtn.disabled = true;
  if (!document.getElementById("connecting-msg")) {
    const msg = document.createElement("div");
    msg.id = "connecting-msg";
    msg.textContent = "Connecting to Hands AI daemon...";
    $chatArea.prepend(msg);
  }
}

// Poll every 5 seconds
pollHealth();
setInterval(pollHealth, 5000);

// ── Models ────────────────────────────────────────────────────────────────────
async function loadModels() {
  const data = await window.hands.getModels();
  if (data && data.models) {
    allModels = data.models;
    renderModelList();
  }
}

function renderModelList() {
  const groups = {
    ollama: { label: "Local (Ollama)", models: [] },
    claude: { label: "Anthropic Claude", models: [] },
    openai: { label: "OpenAI / Codex", models: [] },
  };

  for (const m of allModels) {
    const g = groups[m.provider];
    if (g) g.models.push(m);
  }

  let html = "";
  for (const [key, group] of Object.entries(groups)) {
    if (!group.models.length) continue;
    html += `<div class="model-group-label">${group.label}</div>`;
    for (const m of group.models) {
      const isActive = m.provider === activeProvider && m.id === activeModel;
      const dotClass = m.available ? "avail" : "unavail";
      html += `
        <div class="model-item ${isActive ? "active" : ""}" data-provider="${m.provider}" data-model="${m.id}">
          <div class="model-dot ${dotClass}"></div>
          <span class="model-name">${m.name || m.id}</span>
          <span class="model-provider">${m.id}</span>
        </div>`;
    }
  }

  $modelListContainer.innerHTML = html || "<div style='color:var(--text-muted);font-size:12px;padding:4px;'>No models found</div>";

  // Attach click handlers
  $modelListContainer.querySelectorAll(".model-item").forEach((el) => {
    el.addEventListener("click", async () => {
      const provider = el.dataset.provider;
      const model = el.dataset.model;
      await selectModel(provider, model);
    });
  });
}

async function selectModel(provider, model) {
  const result = await window.hands.setModel(provider, model);
  if (result && result.ok) {
    activeProvider = provider;
    activeModel = model;
    $modelBadge.textContent = `${provider} / ${model}`;
    renderModelList();
    // Close the panel
    modelPanelOpen = false;
    $modelPanel.classList.remove("open");
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────
function appendMessage(role, content, streaming = false) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = role === "user" ? "You" : "Hands AI";

  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  if (streaming) {
    contentDiv.id = "streaming-msg";
  }
  contentDiv.textContent = content;

  div.appendChild(roleLabel);
  div.appendChild(contentDiv);
  $chatArea.appendChild(div);
  scrollToBottom();
  return contentDiv;
}

function appendTypingIndicator() {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.id = "typing-indicator-msg";

  const roleLabel = document.createElement("div");
  roleLabel.className = "message-role";
  roleLabel.textContent = "Hands AI";

  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.innerHTML = "<span></span><span></span><span></span>";

  div.appendChild(roleLabel);
  div.appendChild(indicator);
  $chatArea.appendChild(div);
  scrollToBottom();
  return div;
}

function removeTypingIndicator() {
  const el = document.getElementById("typing-indicator-msg");
  if (el) el.remove();
}

function scrollToBottom() {
  $chatArea.scrollTop = $chatArea.scrollHeight;
}

async function sendMessage() {
  const text = $chatInput.value.trim();
  if (!text || !daemonOnline || streaming) return;

  $chatInput.value = "";
  autoResizeInput();

  conversation.push({ role: "user", content: text });
  appendMessage("user", text);

  streaming = true;
  $sendBtn.disabled = true;

  const typingEl = appendTypingIndicator();
  let responseText = "";

  try {
    const response = await fetch(`${DAEMON_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        stream: true,
        history: conversation.slice(0, -1),
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    removeTypingIndicator();
    const contentDiv = appendMessage("assistant", "", true);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6);
        if (payload === "[DONE]") break;
        try {
          const chunk = JSON.parse(payload);
          const token = chunk.token || "";
          if (token) {
            responseText += token;
            contentDiv.textContent = responseText;
            scrollToBottom();
          }
        } catch {
          // skip malformed
        }
      }
    }

    conversation.push({ role: "assistant", content: responseText });
    window.hands.saveHistory(conversation); // persist after every exchange
  } catch (err) {
    removeTypingIndicator();
    appendMessage("assistant", `[Error: ${err.message}]`);
  } finally {
    streaming = false;
    $sendBtn.disabled = !daemonOnline;
  }
}

// ── Input auto-resize ─────────────────────────────────────────────────────────
function autoResizeInput() {
  $chatInput.style.height = "auto";
  $chatInput.style.height = Math.min($chatInput.scrollHeight, 120) + "px";
}

$chatInput.addEventListener("input", autoResizeInput);

$chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

$sendBtn.addEventListener("click", sendMessage);

// ── Model panel toggle ────────────────────────────────────────────────────────
document.getElementById("model-badge").addEventListener("click", async () => {
  modelPanelOpen = !modelPanelOpen;
  if (modelPanelOpen) {
    $modelPanel.classList.add("open");
    if (daemonOnline) await loadModels();
  } else {
    $modelPanel.classList.remove("open");
  }
});

// ── Clear chat ────────────────────────────────────────────────────────────────
document.getElementById("clear-btn").addEventListener("click", () => {
  conversation = [];
  $chatArea.innerHTML = "";
  window.hands.clearHistory();
});

// ── Settings panel ────────────────────────────────────────────────────────────
document.getElementById("settings-btn").addEventListener("click", async () => {
  settingsPanelOpen = true;
  $settingsPanel.classList.add("open");

  // Load current config
  const cfg = await window.hands.getConfig();
  if (cfg) {
    // API keys come back masked — don't pre-fill with masked value
    $anthropicKey.placeholder = cfg.anthropic_api_key
      ? `Current: ****${cfg.anthropic_api_key.slice(-4)}`
      : "sk-ant-...";
    $openaiKey.placeholder = cfg.openai_api_key
      ? `Current: ****${cfg.openai_api_key.slice(-4)}`
      : "sk-...";
    $ollamaHost.value = cfg.ollama_host || "http://localhost:11434";
  }
});

document.getElementById("close-settings-btn").addEventListener("click", () => {
  $settingsPanel.classList.remove("open");
  settingsPanelOpen = false;
});

document.getElementById("save-settings-btn").addEventListener("click", async () => {
  const data = {};
  if ($anthropicKey.value) data.anthropic_api_key = $anthropicKey.value;
  if ($openaiKey.value) data.openai_api_key = $openaiKey.value;
  if ($ollamaHost.value) data.ollama_host = $ollamaHost.value;

  const result = await window.hands.saveConfig(data);
  if (result && result.ok) {
    $saveStatus.textContent = "Saved!";
    $saveStatus.className = "save-status ok";
    $anthropicKey.value = "";
    $openaiKey.value = "";
    // Refresh model list after saving keys
    await loadModels();
  } else {
    $saveStatus.textContent = "Save failed.";
    $saveStatus.className = "save-status err";
  }
  setTimeout(() => ($saveStatus.textContent = ""), 3000);
});

// ── Escape key closes panels ──────────────────────────────────────────────────
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (settingsPanelOpen) {
      $settingsPanel.classList.remove("open");
      settingsPanelOpen = false;
    } else if (modelPanelOpen) {
      $modelPanel.classList.remove("open");
      modelPanelOpen = false;
    }
  }
});

// ── Tray model-switch sync ────────────────────────────────────────────────────
// When the user switches model from the menu bar tray, update the UI here too
if (window.hands.onModelChanged) {
  window.hands.onModelChanged(({ provider, model }) => {
    activeProvider = provider;
    activeModel = model;
    $modelBadge.textContent = `${provider} / ${model}`;
    loadModels(); // refresh checkmarks in model panel
  });
}
