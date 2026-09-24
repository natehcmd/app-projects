const messagesEl = document.getElementById('messages');
const inputEl = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const stopBtn = document.getElementById('stopBtn');
const clearBtn = document.getElementById('clearBtn');
const settingsBtn = document.getElementById('settingsBtn');
const emptyState = document.getElementById('emptyState');

let isRunning = false;
let currentAssistantBubble = null;
let currentAssistantText = '';
let typingEl = null;

// ── Helpers ────────────────────────────────────────────────────────────────

function setRunning(val) {
  isRunning = val;
  sendBtn.disabled = val;
  stopBtn.classList.toggle('visible', val);
}

function hideEmpty() {
  if (emptyState) emptyState.style.display = 'none';
}

function scrollBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function removeTyping() {
  if (typingEl) { typingEl.remove(); typingEl = null; }
}

function showTyping() {
  removeTyping();
  typingEl = document.createElement('div');
  typingEl.className = 'msg assistant';
  typingEl.innerHTML = `
    <div class="msg-label">Claude</div>
    <div class="typing">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  messagesEl.appendChild(typingEl);
  scrollBottom();
}

function renderMarkdown(text) {
  // Basic markdown rendering
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code.trim()}</code></pre>`)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<strong>$1</strong>')
    .replace(/^## (.+)$/gm, '<strong>$1</strong>')
    .replace(/^# (.+)$/gm, '<strong>$1</strong>')
    .replace(/^[-*] (.+)$/gm, '• $1')
    .replace(/\n/g, '<br/>');
}

function appendUserMessage(text) {
  hideEmpty();
  const el = document.createElement('div');
  el.className = 'msg user';
  el.innerHTML = `
    <div class="msg-label">You</div>
    <div class="msg-bubble msg-text">${renderMarkdown(text)}</div>`;
  messagesEl.appendChild(el);
  scrollBottom();
}

// Escapes text for use inside an HTML element. renderMarkdown() is not usable
// here: it emits markup by design, and this content originates from the model,
// which a hostile page can influence via get_page_content.
function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Shows exactly what the model wants to do and waits for a human decision.
// The gate lives in background.js; this only renders it and reports the answer.
function appendApprovalRequest(id, name, input) {
  hideEmpty();
  const detail = name === 'run_script'
    ? (input && input.script) || ''
    : (input && input.url) || JSON.stringify(input || {});

  const el = document.createElement('div');
  el.className = 'msg assistant';
  el.innerHTML = `
    <div class="msg-label">Approval needed</div>
    <div class="msg-bubble msg-text">
      <div><strong>${escapeHtml(formatToolName(name))}</strong> wants to run:</div>
      <pre style="white-space:pre-wrap;word-break:break-word;background:#111;color:#ddd;padding:8px;border-radius:6px;margin:8px 0;max-height:200px;overflow:auto;font-size:11px">${escapeHtml(detail)}</pre>
      <div style="display:flex;gap:8px">
        <button data-approve="1" style="flex:1;padding:6px 10px;cursor:pointer">Allow</button>
        <button data-approve="0" style="flex:1;padding:6px 10px;cursor:pointer">Deny</button>
      </div>
    </div>`;

  const answer = (approved) => {
    el.querySelectorAll('button').forEach(b => { b.disabled = true; });
    const note = document.createElement('div');
    note.style.cssText = 'font-size:11px;color:#888;margin-top:6px';
    note.textContent = approved ? 'Allowed' : 'Denied';
    el.querySelector('.msg-bubble').appendChild(note);
    chrome.runtime.sendMessage({ type: 'APPROVAL_RESPONSE', id, approved });
  };
  el.querySelector('[data-approve="1"]').addEventListener('click', () => answer(true));
  el.querySelector('[data-approve="0"]').addEventListener('click', () => answer(false));

  messagesEl.appendChild(el);
  scrollBottom();
}

function appendToolCall(name, input) {
  hideEmpty();
  const label = formatToolName(name);
  const detail = formatToolInput(name, input);
  const el = document.createElement('div');
  el.className = 'tool-call';
  el.dataset.tool = name;
  el.innerHTML = `
    <div class="tool-spinner"></div>
    <svg class="tool-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
    <span class="tool-name">${label}</span>
    ${detail ? `<span style="color:#666;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:160px">${detail}</span>` : ''}`;
  messagesEl.appendChild(el);
  scrollBottom();
  return el;
}

function markToolDone(el) {
  if (el) el.classList.add('done');
}

function startAssistantMessage() {
  removeTyping();
  hideEmpty();
  currentAssistantText = '';
  const el = document.createElement('div');
  el.className = 'msg assistant';
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble msg-text';
  el.innerHTML = '<div class="msg-label">Claude</div>';
  el.appendChild(bubble);
  messagesEl.appendChild(el);
  currentAssistantBubble = bubble;
  scrollBottom();
}

function appendAssistantChunk(text) {
  if (!currentAssistantBubble) startAssistantMessage();
  currentAssistantText += text;
  currentAssistantBubble.innerHTML = renderMarkdown(currentAssistantText);
  scrollBottom();
}

function appendErrorMessage(text) {
  removeTyping();
  const el = document.createElement('div');
  el.className = 'msg error';
  el.innerHTML = `
    <div class="msg-label">Error</div>
    <div class="msg-bubble"></div>`;
  el.querySelector('.msg-bubble').textContent = text;
  messagesEl.appendChild(el);
  scrollBottom();
}

function formatToolName(name) {
  const names = {
    navigate: '🌐 Navigate',
    get_page_content: '📄 Read page',
    get_interactive_elements: '🔍 Scan elements',
    click_element: '👆 Click',
    type_text: '⌨️ Type',
    scroll: '↕️ Scroll',
    take_screenshot: '📸 Screenshot',
    wait: '⏳ Wait',
    run_script: '⚡ Run script'
  };
  return names[name] || name;
}

function formatToolInput(name, input) {
  if (!input) return '';
  if (name === 'navigate') return input.url;
  if (name === 'click_element') return input.selector;
  if (name === 'type_text') return `"${input.text}"`;
  if (name === 'scroll') return input.direction;
  if (name === 'wait') return `${input.ms}ms`;
  return '';
}

// ── Load history ────────────────────────────────────────────────────────────

function loadHistory() {
  chrome.runtime.sendMessage({ type: 'GET_HISTORY' }, (response) => {
    if (!response || !response.history) return;
    const history = response.history;
    if (!history.length) return;

    hideEmpty();
    for (const msg of history) {
      if (msg.role === 'user') {
        // May be a string or array (tool results)
        if (typeof msg.content === 'string') {
          appendUserMessage(msg.content);
        }
      } else if (msg.role === 'assistant') {
        if (Array.isArray(msg.content)) {
          const text = msg.content.filter(b => b.type === 'text').map(b => b.text).join('');
          if (text) {
            const el = document.createElement('div');
            el.className = 'msg assistant';
            el.innerHTML = `
              <div class="msg-label">Claude</div>
              <div class="msg-bubble msg-text">${renderMarkdown(text)}</div>`;
            messagesEl.appendChild(el);
          }
        }
      }
    }
    scrollBottom();
  });
}

// ── Send message ────────────────────────────────────────────────────────────

function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || isRunning) return;

  inputEl.value = '';
  inputEl.style.height = 'auto';
  appendUserMessage(text);
  setRunning(true);
  currentAssistantBubble = null;

  showTyping();

  chrome.runtime.sendMessage({ type: 'USER_MESSAGE', text }, (response) => {
    if (response?.error) {
      removeTyping();
      appendErrorMessage(response.error);
      setRunning(false);
    }
  });
}

// ── Background messages ─────────────────────────────────────────────────────

const pendingToolEls = new Map();

chrome.runtime.onMessage.addListener((message) => {
  if (message._source !== 'background') return;

  switch (message.type) {
    case 'ASSISTANT_TEXT':
      removeTyping();
      appendAssistantChunk(message.text);
      break;

    case 'APPROVAL_REQUEST':
      removeTyping();
      appendApprovalRequest(message.id, message.name, message.input);
      break;

    case 'TOOL_START': {
      removeTyping();
      const el = appendToolCall(message.name, message.input);
      pendingToolEls.set(message.name + Date.now(), el);
      // Store last el per tool name for simplicity
      pendingToolEls.set(message.name, el);
      break;
    }

    case 'TOOL_DONE':
      markToolDone(pendingToolEls.get(message.name));
      pendingToolEls.delete(message.name);
      break;

    case 'ERROR':
      removeTyping();
      appendErrorMessage(message.error);
      setRunning(false);
      break;

    case 'DONE':
      removeTyping();
      currentAssistantBubble = null;
      setRunning(false);
      break;
  }
});

// ── Event listeners ─────────────────────────────────────────────────────────

sendBtn.addEventListener('click', sendMessage);

inputEl.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

inputEl.addEventListener('input', () => {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
});

stopBtn.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'STOP' });
  removeTyping();
  setRunning(false);
});

clearBtn.addEventListener('click', () => {
  if (!confirm('Clear chat history?')) return;
  chrome.runtime.sendMessage({ type: 'CLEAR_HISTORY' });
  // Remove all messages except empty state
  while (messagesEl.lastChild && messagesEl.lastChild !== emptyState) {
    messagesEl.removeChild(messagesEl.lastChild);
  }
  if (emptyState) emptyState.style.display = '';
  currentAssistantBubble = null;
  setRunning(false);
});

settingsBtn.addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

// ── Init ────────────────────────────────────────────────────────────────────

loadHistory();
inputEl.focus();
