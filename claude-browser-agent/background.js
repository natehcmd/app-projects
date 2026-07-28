const CLAUDE_API_URL = 'https://api.anthropic.com/v1/messages';
const MODEL = 'claude-sonnet-4-6';
const MAX_TOKENS = 8096;

const SYSTEM_PROMPT = `You are a helpful browser automation assistant. You can control the user's browser to accomplish tasks.

When asked to do something, use the available tools to actually do it — don't just explain how. Be proactive and complete tasks end-to-end. After finishing, briefly summarize what you did.

Tips:
- Use get_page_content or get_interactive_elements to understand the current page before acting
- Use take_screenshot when you need to visually verify something
- Use wait after navigating or clicking to let pages load
- Chain multiple tool calls to complete multi-step tasks`;

const BROWSER_TOOLS = [
  {
    name: "navigate",
    description: "Navigate the browser to a URL",
    input_schema: {
      type: "object",
      properties: {
        url: { type: "string", description: "Full URL to navigate to (include https://)" }
      },
      required: ["url"]
    }
  },
  {
    name: "get_page_content",
    description: "Get the current page title, URL, and text content",
    input_schema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "get_interactive_elements",
    description: "Get a list of clickable elements, inputs, and links on the current page with their selectors",
    input_schema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "click_element",
    description: "Click an element on the page by CSS selector",
    input_schema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector for the element" }
      },
      required: ["selector"]
    }
  },
  {
    name: "type_text",
    description: "Type text into an input field",
    input_schema: {
      type: "object",
      properties: {
        selector: { type: "string", description: "CSS selector for the input" },
        text: { type: "string", description: "Text to type" },
        clear_first: { type: "boolean", description: "Clear the field before typing (default true)" },
        press_enter: { type: "boolean", description: "Press Enter after typing" }
      },
      required: ["selector", "text"]
    }
  },
  {
    name: "scroll",
    description: "Scroll the page",
    input_schema: {
      type: "object",
      properties: {
        direction: { type: "string", enum: ["up", "down", "top", "bottom"], description: "Scroll direction" },
        amount: { type: "number", description: "Pixels to scroll (optional, default 400)" }
      },
      required: ["direction"]
    }
  },
  {
    name: "take_screenshot",
    description: "Take a screenshot to see what the page currently looks like",
    input_schema: {
      type: "object",
      properties: {}
    }
  },
  {
    name: "wait",
    description: "Wait for the page to load or an animation to complete",
    input_schema: {
      type: "object",
      properties: {
        ms: { type: "number", description: "Milliseconds to wait (max 5000)" }
      },
      required: ["ms"]
    }
  },
  {
    name: "run_script",
    description: "Run JavaScript on the current page and return the result. Use for complex interactions.",
    input_schema: {
      type: "object",
      properties: {
        script: { type: "string", description: "JavaScript code to execute. Must be a valid JS expression or block that returns a value." }
      },
      required: ["script"]
    }
  }
];

// In-memory chat history (persisted to storage)
let chatHistory = [];
let isRunning = false;

// Load history on startup
chrome.storage.local.get('chatHistory', (result) => {
  if (result.chatHistory) chatHistory = result.chatHistory;
});

function saveHistory() {
  // Keep last 200 messages to avoid storage limits
  const trimmed = chatHistory.slice(-200);
  chrome.storage.local.set({ chatHistory: trimmed });
}

// Open side panel when icon clicked
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'USER_MESSAGE') {
    if (isRunning) {
      sendResponse({ error: 'Already processing a message' });
      return true;
    }
    getCurrentTabId().then(tabId => {
      handleUserMessage(message.text, tabId)
        .catch(err => notifySidePanel({ type: 'ERROR', error: err.message }))
        .finally(() => { isRunning = false; notifySidePanel({ type: 'DONE' }); });
    });
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'CLEAR_HISTORY') {
    chatHistory = [];
    chrome.storage.local.remove('chatHistory');
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === 'GET_HISTORY') {
    sendResponse({ history: chatHistory });
    return true;
  }

  if (message.type === 'STOP') {
    isRunning = false;
    sendResponse({ ok: true });
    return true;
  }
});

async function handleUserMessage(text, tabId) {
  isRunning = true;
  chatHistory.push({ role: 'user', content: text });
  saveHistory();
  await runAgentLoop(tabId);
}

async function runAgentLoop(tabId) {
  const apiKey = await getApiKey();
  if (!apiKey) {
    notifySidePanel({ type: 'ERROR', error: 'No API key set. Click the gear icon to add your Anthropic API key.' });
    return;
  }

  while (isRunning) {
    let response;
    try {
      response = await callClaude(apiKey, chatHistory);
    } catch (err) {
      notifySidePanel({ type: 'ERROR', error: `API error: ${err.message}` });
      break;
    }

    const assistantMessage = { role: 'assistant', content: response.content };
    chatHistory.push(assistantMessage);
    saveHistory();

    const toolUses = response.content.filter(b => b.type === 'tool_use');
    const textBlocks = response.content.filter(b => b.type === 'text');

    // Send text to side panel
    const text = textBlocks.map(b => b.text).join('');
    if (text) {
      notifySidePanel({ type: 'ASSISTANT_TEXT', text });
    }

    if (toolUses.length === 0) break;

    // Execute tools sequentially
    const toolResults = [];
    for (const toolUse of toolUses) {
      if (!isRunning) break;

      notifySidePanel({ type: 'TOOL_START', name: toolUse.name, input: toolUse.input });

      let result;
      try {
        result = await executeTool(toolUse.name, toolUse.input, tabId);
      } catch (err) {
        result = `Error: ${err.message}`;
      }

      notifySidePanel({ type: 'TOOL_DONE', name: toolUse.name });

      // Handle image results (screenshots) specially
      if (result && result._type === 'image') {
        toolResults.push({
          type: 'tool_result',
          tool_use_id: toolUse.id,
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: 'image/jpeg',
                data: result.data
              }
            }
          ]
        });
      } else {
        toolResults.push({
          type: 'tool_result',
          tool_use_id: toolUse.id,
          content: typeof result === 'string' ? result : JSON.stringify(result, null, 2)
        });
      }
    }

    if (toolResults.length > 0) {
      chatHistory.push({ role: 'user', content: toolResults });
      saveHistory();
    }
  }
}

async function callClaude(apiKey, messages) {
  const response = await fetch(CLAUDE_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: MAX_TOKENS,
      system: SYSTEM_PROMPT,
      messages,
      tools: BROWSER_TOOLS
    })
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status}: ${body}`);
  }

  return response.json();
}

async function executeTool(name, input, tabId) {
  switch (name) {
    case 'navigate': {
      let url = input.url;
      if (!url.startsWith('http://') && !url.startsWith('https://')) url = 'https://' + url;
      await chrome.tabs.update(tabId, { url });
      await waitForTabLoad(tabId);
      const tab = await chrome.tabs.get(tabId);
      return `Navigated to ${tab.url}`;
    }

    case 'get_page_content': {
      const result = await injectScript(tabId, function() {
        return {
          title: document.title,
          url: window.location.href,
          content: document.body ? document.body.innerText.substring(0, 8000) : ''
        };
      });
      return result;
    }

    case 'get_interactive_elements': {
      const result = await injectScript(tabId, function() {
        const seen = new Set();
        const elements = [];
        const nodes = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [role="link"], [role="tab"], [role="menuitem"], [onclick]');

        nodes.forEach((el) => {
          const rect = el.getBoundingClientRect();
          if (rect.width === 0 && rect.height === 0) return;

          // Build a unique-ish selector
          let selector = el.tagName.toLowerCase();
          if (el.id) {
            selector = '#' + CSS.escape(el.id);
          } else if (el.name) {
            selector = el.tagName.toLowerCase() + '[name="' + el.name + '"]';
          } else if (el.getAttribute('data-testid')) {
            selector = '[data-testid="' + el.getAttribute('data-testid') + '"]';
          } else if (el.getAttribute('aria-label')) {
            selector = el.tagName.toLowerCase() + '[aria-label="' + el.getAttribute('aria-label') + '"]';
          }

          if (seen.has(selector)) return;
          seen.add(selector);

          const text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.getAttribute('title') || '').trim().substring(0, 60);

          elements.push({
            tag: el.tagName.toLowerCase(),
            type: el.type || el.getAttribute('role') || null,
            text,
            selector,
            href: el.href || null
          });
        });

        return elements.slice(0, 60);
      });
      return result;
    }

    case 'click_element': {
      const result = await injectScript(tabId, function(selector) {
        const el = document.querySelector(selector);
        if (!el) return { ok: false, error: 'Element not found: ' + selector };
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.focus();
        el.click();
        return { ok: true, message: 'Clicked ' + selector };
      }, [input.selector]);
      if (result && !result.ok) throw new Error(result.error);
      await new Promise(r => setTimeout(r, 500));
      return result?.message || 'Clicked';
    }

    case 'type_text': {
      const clearFirst = input.clear_first !== false;
      const pressEnter = input.press_enter === true;
      const result = await injectScript(tabId, function({ selector, text, clearFirst, pressEnter }) {
        const el = document.querySelector(selector);
        if (!el) return { ok: false, error: 'Element not found: ' + selector };
        el.focus();
        if (clearFirst) {
          el.value = '';
          el.dispatchEvent(new Event('input', { bubbles: true }));
        }
        // Type character by character for React/Vue inputs
        for (const char of text) {
          el.value += char;
          el.dispatchEvent(new InputEvent('input', { bubbles: true, data: char }));
        }
        el.dispatchEvent(new Event('change', { bubbles: true }));
        if (pressEnter) {
          el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));
          el.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', keyCode: 13, bubbles: true }));
        }
        return { ok: true, message: `Typed "${text}" into ${selector}` };
      }, [{ selector: input.selector, text: input.text, clearFirst, pressEnter }]);
      if (result && !result.ok) throw new Error(result.error);
      return result?.message || 'Typed text';
    }

    case 'scroll': {
      const amount = input.amount || 400;
      await injectScript(tabId, function({ direction, amount }) {
        if (direction === 'top') window.scrollTo({ top: 0, behavior: 'smooth' });
        else if (direction === 'bottom') window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        else if (direction === 'up') window.scrollBy({ top: -amount, behavior: 'smooth' });
        else window.scrollBy({ top: amount, behavior: 'smooth' });
      }, [{ direction: input.direction, amount }]);
      await new Promise(r => setTimeout(r, 400));
      return `Scrolled ${input.direction}`;
    }

    case 'take_screenshot': {
      const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: 'jpeg', quality: 75 });
      // Strip the data URL prefix to get raw base64
      const data = dataUrl.replace(/^data:image\/jpeg;base64,/, '');
      return { _type: 'image', data };
    }

    case 'wait': {
      const ms = Math.min(input.ms, 5000);
      await new Promise(r => setTimeout(r, ms));
      return `Waited ${ms}ms`;
    }

    case 'run_script': {
      const result = await injectScript(tabId, function(script) {
        try {
          // eslint-disable-next-line no-eval
          const val = eval(script);
          return { ok: true, result: val !== undefined ? String(val) : 'undefined' };
        } catch (e) {
          return { ok: false, error: e.message };
        }
      }, [input.script]);
      if (result && !result.ok) throw new Error(result.error);
      return result?.result || 'Script executed';
    }

    default:
      return `Unknown tool: ${name}`;
  }
}

function injectScript(tabId, fn, args = []) {
  return new Promise((resolve, reject) => {
    chrome.scripting.executeScript(
      { target: { tabId }, func: fn, args },
      (results) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(results && results[0] ? results[0].result : null);
        }
      }
    );
  });
}

function waitForTabLoad(tabId) {
  return new Promise(resolve => {
    const timeout = setTimeout(resolve, 8000);
    function listener(id, changeInfo) {
      if (id === tabId && changeInfo.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        clearTimeout(timeout);
        setTimeout(resolve, 600);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

function notifySidePanel(data) {
  chrome.runtime.sendMessage({ ...data, _source: 'background' }).catch(() => {});
}

async function getApiKey() {
  return new Promise(resolve => {
    chrome.storage.local.get('apiKey', r => resolve(r.apiKey || null));
  });
}

async function getCurrentTabId() {
  return new Promise(resolve => {
    chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
      resolve(tabs[0]?.id);
    });
  });
}
