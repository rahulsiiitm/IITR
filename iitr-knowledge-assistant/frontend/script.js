const appWindow = document.getElementById('appWindow');
const bubbleBtn = document.getElementById('bubbleBtn');
const closeBtn = document.getElementById('closeBtn');
const chatArea = document.getElementById('chatArea');
const inputForm = document.getElementById('inputForm');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const clearBtn = document.getElementById('clearBtn');
const welcomeMessage = document.getElementById('welcomeMessage');

let isProcessing = false;
let currentSessionId = null;
let msgCount = 0;

// ── Toggle ────────────────────────────────────────────
bubbleBtn.addEventListener('click', () => {
  appWindow.classList.remove('hidden');
  bubbleBtn.classList.add('hidden');
  messageInput.focus();
});

closeBtn.addEventListener('click', () => {
  appWindow.classList.add('hidden');
  bubbleBtn.classList.remove('hidden');
});

// ── Submit ────────────────────────────────────────────
inputForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text || isProcessing) return;
  handleMessage(text);
});

// ── Clear ─────────────────────────────────────────────
clearBtn.addEventListener('click', () => {
  chatArea.querySelectorAll('.msg-wrapper, .msg-divider').forEach(el => el.remove());
  welcomeMessage.style.display = 'flex';
  currentSessionId = null;
  msgCount = 0;
});

// ── Suggestions ───────────────────────────────────────
document.addEventListener('click', (e) => {
  const card = e.target.closest('.suggestion-card');
  if (card && !isProcessing) {
    const question = card.getAttribute('data-question');
    if (question) handleMessage(question);
  }
});

// ── Core handler ──────────────────────────────────────
function handleMessage(text) {
  welcomeMessage.style.display = 'none';
  msgCount++;

  if (msgCount > 1) addDivider();

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
        err.message || 'Unable to reach the knowledge assistant. Please try again.',
        'bot'
      );
    })
    .finally(() => {
      isProcessing = false;
      sendBtn.disabled = false;
    });
}

// ── Add message ───────────────────────────────────────
function addMsg(text, type, sources, debug) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg-wrapper ${type}`;

  // Meta row (avatar + author label)
  const meta = document.createElement('div');
  meta.className = 'msg-meta';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.setAttribute('aria-hidden', 'true');

  if (type === 'user') {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`;
  } else {
    avatar.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;
  }

  const author = document.createElement('span');
  author.className = 'msg-author';
  author.textContent = type === 'user' ? 'You' : 'Sutra';

  meta.appendChild(avatar);
  meta.appendChild(author);

  // Bubble
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  if (type === 'user') {
    bubble.textContent = text;
  } else {
    if (typeof marked !== 'undefined') {
      marked.setOptions({ breaks: true, gfm: true });
      bubble.innerHTML = marked.parse(text);
    } else {
      bubble.textContent = text;
    }
  }

  // Sources
  if (type === 'bot' && sources && sources.length) {
    const sourceContainer = document.createElement('div');
    sourceContainer.className = 'source-container';

    const grouped = {};
    sources.forEach((s) => {
      const doc = s.document || 'Document';
      if (!grouped[doc]) grouped[doc] = [];
      grouped[doc].push(s.page);
    });

    for (const [docName, pages] of Object.entries(grouped)) {
      const pill = document.createElement('span');
      pill.className = 'source-pill';
      const unique = [...new Set(pages)].sort((a, b) => a - b);
      const label = unique.length === 1 ? 'p.' : 'pp.';
      pill.textContent = `${docName} — ${label} ${unique.join(', ')}`;
      sourceContainer.appendChild(pill);
    }

    bubble.appendChild(sourceContainer);
  }

  // Debug panel (hidden by CSS in prod, kept for dev)
  if (type === 'bot' && debug && debug.length) {
    const toggle = document.createElement('button');
    toggle.className = 'debug-toggle';
    toggle.textContent = 'Show retrieved chunks';

    const panel = document.createElement('div');
    panel.className = 'debug-panel';
    panel.style.display = 'none';

    debug.forEach((item, i) => {
      const entry = document.createElement('div');
      entry.className = 'debug-entry';
      entry.innerHTML = `<strong>Chunk ${i + 1}</strong> — Score: ${item.rerank_score.toFixed(3)}, Page ${item.page}<br><small>${escapeHtml(item.chunk)}</small>`;
      panel.appendChild(entry);
    });

    toggle.addEventListener('click', () => {
      const isOpen = panel.style.display !== 'none';
      panel.style.display = isOpen ? 'none' : 'block';
      toggle.textContent = isOpen ? 'Show retrieved chunks' : 'Hide retrieved chunks';
    });

    bubble.appendChild(toggle);
    bubble.appendChild(panel);
  }

  wrapper.appendChild(meta);
  wrapper.appendChild(bubble);
  chatArea.appendChild(wrapper);
  chatArea.scrollTop = chatArea.scrollHeight;
}

// ── Loader ────────────────────────────────────────────
function addLoader() {
  const wrapper = document.createElement('div');
  wrapper.className = 'msg-wrapper bot';

  const meta = document.createElement('div');
  meta.className = 'msg-meta';

  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.setAttribute('aria-hidden', 'true');
  avatar.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c0 2 2 3 6 3s6-1 6-3v-5"/></svg>`;

  const author = document.createElement('span');
  author.className = 'msg-author';
  author.textContent = 'Sutra';

  meta.appendChild(avatar);
  meta.appendChild(author);

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

  wrapper.appendChild(meta);
  wrapper.appendChild(bubble);
  chatArea.appendChild(wrapper);
  chatArea.scrollTop = chatArea.scrollHeight;
  return wrapper;
}

// ── Divider ───────────────────────────────────────────
function addDivider() {
  const div = document.createElement('div');
  div.className = 'msg-divider';
  div.innerHTML = '<span>· · ·</span>';
  chatArea.appendChild(div);
}

// ── Escape HTML ───────────────────────────────────────
function escapeHtml(unsafe) {
  return unsafe
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── API ───────────────────────────────────────────────
const API_BASE = window.API_SAME_ORIGIN
  ? window.location.origin
  : `http://${window.location.hostname}:${window.API_PORT || 52000}`;

async function sendToBackend(question) {
  const headers = { 'Content-Type': 'application/json' };
  if (window.API_KEY) headers['X-API-Key'] = window.API_KEY;

  const payload = { question };
  if (currentSessionId) payload.session_id = currentSessionId;

  let res;
  try {
    res = await fetch(`${API_BASE}/ask`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      `Cannot reach the API at ${API_BASE}. Run ./scripts/run_server.sh and open the URL it prints.`
    );
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail;
    const msg = typeof detail === 'string' ? detail : JSON.stringify(detail) || res.statusText;
    throw new Error(msg || 'Backend request failed');
  }

  const data = await res.json();
  if (data.session_id) currentSessionId = data.session_id;
  return data;
}