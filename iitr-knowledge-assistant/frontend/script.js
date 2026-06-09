const chatArea = document.getElementById('chatArea');
const inputForm = document.getElementById('inputForm');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const clearBtn = document.getElementById('clearBtn');
const welcomeMessage = document.getElementById('welcomeMessage');

let isProcessing = false;
let currentSessionId = null;

inputForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text || isProcessing) return;
  handleMessage(text);
});

clearBtn.addEventListener('click', () => {
  chatArea.querySelectorAll('.msg').forEach((el) => el.remove());
  welcomeMessage.style.display = 'flex';
  currentSessionId = null;
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
      addMsg(
        err.message ||
          'Something went wrong while reaching the knowledge assistant. Please try again.',
        'bot'
      );
    })
    .finally(() => {
      isProcessing = false;
      sendBtn.disabled = false;
    });
}

function addMsg(text, type, sources, debug) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper ${type}`;

  const div = document.createElement('div');
  div.className = `msg`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  if (type === 'user') {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
  } else {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;
  }

  const contentDiv = document.createElement('div');
  contentDiv.className = 'msg-content';

  const textDiv = document.createElement('div');
  textDiv.className = 'msg-text';

  if (type === 'user') {
    textDiv.textContent = text;
  } else if (typeof marked !== 'undefined') {
    marked.setOptions({ breaks: true, gfm: true });
    textDiv.innerHTML = marked.parse(text);
  } else {
    textDiv.textContent = text;
  }
  
  contentDiv.appendChild(textDiv);

  if (type === 'bot' && sources && sources.length) {
    const sourceContainer = document.createElement('div');
    sourceContainer.className = 'source-container';

    const grouped = {};
    sources.forEach((source) => {
      const docName = source.document || 'Document';
      if (!grouped[docName]) grouped[docName] = [];
      grouped[docName].push(source.page);
    });

    for (const [docName, pages] of Object.entries(grouped)) {
      const pill = document.createElement('span');
      pill.className = 'source-pill';
      const uniquePages = [...new Set(pages)].sort((a, b) => a - b);
      const pageText = uniquePages.length === 1 ? 'Page' : 'Pages';
      pill.innerHTML = `📄 ${docName} — ${pageText} ${uniquePages.join(', ')}`;
      sourceContainer.appendChild(pill);
    }

    contentDiv.appendChild(sourceContainer);
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

    contentDiv.appendChild(toggle);
    contentDiv.appendChild(panel);
  }

  div.appendChild(avatar);
  div.appendChild(contentDiv);
  wrapper.appendChild(div);
  chatArea.appendChild(wrapper);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function addLoader() {
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper bot loader-msg';
  
  const div = document.createElement('div');
  div.className = 'msg';
  
  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'msg-content';
  contentDiv.innerHTML = '<div class="dots"><span></span><span></span><span></span></div>';
  
  div.appendChild(avatar);
  div.appendChild(contentDiv);
  wrapper.appendChild(div);
  
  chatArea.appendChild(wrapper);
  chatArea.scrollTop = chatArea.scrollHeight;
  return wrapper;
}

function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Same-origin when UI is served by FastAPI (recommended, especially over SSH remote)
const API_BASE = window.API_SAME_ORIGIN
  ? window.location.origin
  : `http://${window.location.hostname}:${window.API_PORT || 52000}`;

async function sendToBackend(question) {
  let res;
  const headers = {
    'Content-Type': 'application/json'
  };
  
  if (window.API_KEY) {
    headers['X-API-Key'] = window.API_KEY;
  }

  const payload = { question };
  if (currentSessionId) {
    payload.session_id = currentSessionId;
  }

  try {
    res = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(payload),
    });
  } catch (err) {
    throw new Error(
      `Cannot reach the API at ${API_BASE}. Run ./scripts/run_server.sh and open the URL it prints (not a separate port).`
    );
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const msg = typeof detail === 'string' ? detail : JSON.stringify(detail) || res.statusText;
    throw new Error(msg || 'Failed to reach backend API');
  }
  const data = await res.json();
  if (data.session_id) {
    currentSessionId = data.session_id;
  }
  return data;
}
