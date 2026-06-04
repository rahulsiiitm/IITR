const chatArea = document.getElementById('chatArea');
const inputForm = document.getElementById('inputForm');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const clearBtn = document.getElementById('clearBtn');
const welcomeMessage = document.getElementById('welcomeMessage');

let isProcessing = false;

inputForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text || isProcessing) return;
  handleMessage(text);
});

clearBtn.addEventListener('click', () => {
  chatArea.querySelectorAll('.msg').forEach((el) => el.remove());
  welcomeMessage.style.display = 'flex';
});

document.addEventListener('click', (e) => {
  const card = e.target.closest('.suggestion-card');
  if (card && !isProcessing) {
    const question = card.getAttribute('data-question');
    if (question) handleMessage(question);
  }
});

function handleMessage(text) {
  welcomeMessage.style.display = 'none';
  addMsg(text, 'user');
  messageInput.value = '';

  isProcessing = true;
  sendBtn.disabled = true;
  const loader = addLoader();

  sendToBackend(text)
    .then((res) => {
      loader.remove();
      addMsg(res.answer, 'bot', res.sources, res.debug);
    })
    .catch((err) => {
      console.error(err);
      loader.remove();
      addMsg('Something went wrong while reaching the knowledge assistant. Please try again.', 'bot');
    })
    .finally(() => {
      isProcessing = false;
      sendBtn.disabled = false;
    });
}

function addMsg(text, type, sources, debug) {
  const div = document.createElement('div');
  div.className = `msg ${type}`;

  if (type === 'user') {
    div.textContent = text;
  } else if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
    div.innerHTML = marked.parse(text);
  } else {
    div.textContent = text;
  }

  if (type === 'bot' && sources && sources.length) {
    const sourceContainer = document.createElement('div');
    sourceContainer.className = 'source-container';

    sources.forEach((source) => {
      const pill = document.createElement('span');
      pill.className = 'source-pill';
      const docName = source.document || 'Document';
      pill.innerHTML = `📄 ${docName} — Page ${source.page}`;
      sourceContainer.appendChild(pill);
    });

    div.appendChild(sourceContainer);
  }

  if (type === 'bot' && debug && debug.length) {
    const toggle = document.createElement('button');
    toggle.className = 'debug-toggle';
    toggle.innerHTML = `<svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none" style="margin-right:4px;"><polyline points="9 18 15 12 9 6"/></svg> Show retrieved chunks`;

    const panel = document.createElement('div');
    panel.className = 'debug-panel';
    panel.style.display = 'none';

    debug.forEach((item, i) => {
      const entry = document.createElement('div');
      entry.className = 'debug-entry';
      entry.innerHTML = `
        <div class="debug-header">
          <strong>Chunk ${i + 1}</strong>
          <span class="debug-score">Score: ${item.rerank_score.toFixed(3)}</span>
          <span class="debug-page">Page ${item.page}</span>
        </div>
        <div class="debug-text">${escapeHtml(item.chunk)}</div>
      `;
      panel.appendChild(entry);
    });

    toggle.addEventListener('click', () => {
      const isOpen = panel.style.display !== 'none';
      panel.style.display = isOpen ? 'none' : 'flex';
      toggle.innerHTML = isOpen
        ? `<svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none" style="margin-right:4px;"><polyline points="9 18 15 12 9 6"/></svg> Show retrieved chunks`
        : `<svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none" style="margin-right:4px;"><polyline points="6 9 12 15 18 9"/></svg> Hide retrieved chunks`;
    });

    div.appendChild(toggle);
    div.appendChild(panel);
  }

  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function addLoader() {
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.innerHTML = '<div class="dots"><span></span><span></span><span></span></div>';
  chatArea.appendChild(div);
  chatArea.scrollTop = chatArea.scrollHeight;
  return div;
}

function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

const API_BASE = 'http://localhost:8000';

async function sendToBackend(question) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to reach backend API');
  }
  return await res.json();
}
