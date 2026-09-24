/* Quick notes (backlog P1) — drafted by Gemini Flash via the pipeline, reviewed by Claude. */
(function () {
  function init() {
    function formatTs(ts) {
      if (!ts) return '';
      let d = typeof ts === 'number' ? new Date(ts < 1e11 ? ts * 1000 : ts) : new Date(ts);
      if (isNaN(d.getTime())) return String(ts);
      const pad = (n) => String(n).padStart(2, '0');
      return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }

    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.textContent = '✎';
    toggleBtn.setAttribute('aria-label', 'Quick note');
    toggleBtn.title = 'Quick note (N)';
    toggleBtn.style.cssText = [
      'position: fixed',
      'top: 14px',
      'left: 14px',
      'z-index: 60',
      'width: 40px',
      'height: 40px',
      'border-radius: 50%',
      'background: var(--glass)',
      'border: 1px solid var(--glass-brd)',
      'color: var(--ink)',
      'font-size: 18px',
      'cursor: pointer',
      'display: flex',
      'align-items: center',
      'justify-content: center',
      'backdrop-filter: blur(10px)',
      '-webkit-backdrop-filter: blur(10px)',
      'box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15)',
      'transition: transform 0.15s ease'
    ].join(';');

    const panel = document.createElement('div');
    panel.style.cssText = [
      'position: fixed',
      'top: 62px',
      'left: 14px',
      'width: min(380px, calc(100vw - 28px))',
      'z-index: 60',
      'background: var(--glass)',
      'border: 1px solid var(--glass-brd)',
      'color: var(--ink)',
      'border-radius: 12px',
      'padding: 12px',
      'box-sizing: border-box',
      'backdrop-filter: blur(16px)',
      '-webkit-backdrop-filter: blur(16px)',
      'box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25)',
      'display: none',
      'flex-direction: column',
      'gap: 10px',
      'font-family: inherit',
      'font-size: 13px',
      'line-height: 1.4'
    ].join(';');

    const heading = document.createElement('h3');
    heading.textContent = 'Quick note — Claude and Hammond can read these';
    heading.style.cssText = 'margin: 0; font-size: 13px; font-weight: 600; color: var(--ink); opacity: 0.95;';

    const textarea = document.createElement('textarea');
    textarea.rows = 4;
    textarea.placeholder = 'Type a note... (Cmd/Ctrl+Enter to save)';
    textarea.style.cssText = [
      'width: 100%',
      'box-sizing: border-box',
      'resize: vertical',
      'border-radius: 8px',
      'background: rgba(0, 0, 0, 0.05)',
      'border: 1px solid var(--glass-brd)',
      'color: var(--ink)',
      'padding: 8px',
      'font-family: inherit',
      'font-size: 13px',
      'outline: none'
    ].join(';');

    const actionsRow = document.createElement('div');
    actionsRow.style.cssText = 'display: flex; justify-content: space-between; align-items: center; gap: 8px;';

    const micBtn = document.createElement('button');
    micBtn.type = 'button';
    micBtn.textContent = '🎤 Speak';
    micBtn.style.cssText = [
      'background: var(--glass)',
      'border: 1px solid var(--glass-brd)',
      'color: var(--ink)',
      'border-radius: 6px',
      'padding: 6px 12px',
      'font-size: 12px',
      'cursor: pointer'
    ].join(';');

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.textContent = 'Save';
    saveBtn.style.cssText = [
      'background: var(--accent, var(--sky))',
      'color: #fff',
      'border: none',
      'border-radius: 6px',
      'padding: 6px 16px',
      'font-size: 12px',
      'font-weight: 600',
      'cursor: pointer'
    ].join(';');

    actionsRow.appendChild(micBtn);
    actionsRow.appendChild(saveBtn);

    const statusEl = document.createElement('div');
    statusEl.style.cssText = 'font-size: 12px; min-height: 16px; display: none;';

    const recentSection = document.createElement('div');
    recentSection.style.cssText = 'border-top: 1px solid var(--glass-brd); padding-top: 8px; display: flex; flex-direction: column; gap: 6px;';

    const recentHeading = document.createElement('div');
    recentHeading.textContent = 'Recent notes';
    recentHeading.style.cssText = 'font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.75;';

    const notesList = document.createElement('div');
    notesList.style.cssText = 'display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto;';

    recentSection.appendChild(recentHeading);
    recentSection.appendChild(notesList);

    panel.appendChild(heading);
    panel.appendChild(textarea);
    panel.appendChild(actionsRow);
    panel.appendChild(statusEl);
    panel.appendChild(recentSection);

    document.body.appendChild(toggleBtn);
    document.body.appendChild(panel);

    let statusTimer = null;
    function showStatus(text, isError) {
      clearTimeout(statusTimer);
      statusEl.textContent = text;
      statusEl.style.display = 'block';
      statusEl.style.color = isError ? '#ff4d4f' : 'var(--accent, var(--sky))';
      if (!isError) {
        statusTimer = setTimeout(() => {
          statusEl.style.display = 'none';
          statusEl.textContent = '';
        }, 1500);
      }
    }

    async function loadRecentNotes() {
      try {
        const data = await api('activity?limit=60');
        const notes = (Array.isArray(data) ? data : [])
          .filter((item) => item && item.kind === 'note')
          .slice(0, 5);

        if (notes.length === 0) {
          notesList.innerHTML = '<div style="font-size:12px;opacity:0.6;font-style:italic;">No notes yet</div>';
          return;
        }

        notesList.innerHTML = notes
          .map((n) => `
            <div style="background:rgba(0,0,0,0.04);border:1px solid var(--glass-brd);border-radius:6px;padding:6px 8px;font-size:12px;word-break:break-word;">
              <div style="font-size:10px;opacity:0.6;margin-bottom:2px;">${esc(formatTs(n.ts))}</div>
              <div>${esc(n.detail || '')}</div>
            </div>
          `)
          .join('');
      } catch (err) {
        notesList.innerHTML = '<div style="font-size:12px;opacity:0.6;">Unable to load recent notes</div>';
      }
    }

    async function saveNote() {
      const text = textarea.value.trim();
      if (!text || saveBtn.disabled) return;

      saveBtn.disabled = true;
      try {
        await api('activity/log', { kind: 'note', detail: text });
        textarea.value = '';
        showStatus('Saved ✓', false);
        await loadRecentNotes();
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        showStatus("Couldn't save — " + msg, true);
      } finally {
        saveBtn.disabled = false;
      }
    }

    let isListening = false;
    let recognition = null;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      micBtn.disabled = true;
      micBtn.title = 'Voice not supported in this browser — use Safari/Chrome';
      micBtn.style.opacity = '0.5';
      micBtn.style.cursor = 'not-allowed';
    } else {
      recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        isListening = true;
        micBtn.textContent = '■ Stop';
      };

      recognition.onresult = (event) => {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            const transcript = event.results[i][0].transcript.trim();
            if (transcript) {
              const current = textarea.value;
              textarea.value = current
                ? current + (current.endsWith(' ') || current.endsWith('\n') ? '' : ' ') + transcript
                : transcript;
            }
          }
        }
      };

      recognition.onerror = () => {
        isListening = false;
        micBtn.textContent = '🎤 Speak';
      };

      recognition.onend = () => {
        isListening = false;
        micBtn.textContent = '🎤 Speak';
      };

      micBtn.addEventListener('click', () => {
        if (isListening) {
          recognition.stop();
        } else {
          try {
            recognition.start();
          } catch (e) {}
        }
      });
    }

    function openPanel() {
      panel.style.display = 'flex';
      loadRecentNotes();
      setTimeout(() => textarea.focus(), 50);
    }

    function closePanel() {
      panel.style.display = 'none';
      if (isListening && recognition) {
        recognition.stop();
      }
    }

    function togglePanel() {
      if (panel.style.display === 'none' || !panel.style.display) {
        openPanel();
      } else {
        closePanel();
      }
    }

    toggleBtn.addEventListener('click', togglePanel);
    saveBtn.addEventListener('click', saveNote);

    textarea.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        saveNote();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (panel.style.display !== 'none') {
          closePanel();
        }
        return;
      }

      if ((e.key === 'n' || e.key === 'N') && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const el = document.activeElement;
        const isEditing = el && (
          el.tagName === 'INPUT' ||
          el.tagName === 'TEXTAREA' ||
          el.tagName === 'SELECT' ||
          el.isContentEditable
        );
        if (!isEditing) {
          e.preventDefault();
          togglePanel();
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
