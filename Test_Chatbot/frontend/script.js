const chatArea = document.getElementById('chatArea');
const inputForm = document.getElementById('inputForm');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const clearBtn = document.getElementById('clearBtn');
const welcomeMessage = document.getElementById('welcomeMessage');

let isProcessing = false;

// Send message
inputForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = messageInput.value.trim();
  if (!text || isProcessing) return;
  handleMessage(text);
});

// Clear chat
clearBtn.addEventListener('click', () => {
  chatArea.querySelectorAll('.msg').forEach((el) => el.remove());
  welcomeMessage.style.display = 'block';
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
    .catch(() => {
      loader.remove();
      addMsg('Something went wrong. Please try again.', 'bot');
    })
    .finally(() => {
      isProcessing = false;
      sendBtn.disabled = false;
    });
}

function addMsg(text, type, sources, debug) {
  const div = document.createElement('div');
  div.className = `msg ${type}`;
  div.textContent = text;

  if (type === 'bot' && sources && sources.length) {
    const src = document.createElement('div');
    src.className = 'source';
    src.textContent = '📄 Sources: Pages ' + sources.join(', ');
    div.appendChild(src);
  }

  // Debug panel (collapsible)
  if (type === 'bot' && debug && debug.length) {
    const toggle = document.createElement('button');
    toggle.className = 'debug-toggle';
    toggle.textContent = '▶ Show retrieved chunks';
    
    const panel = document.createElement('div');
    panel.className = 'debug-panel';
    panel.style.display = 'none';

    debug.forEach((item, i) => {
      const entry = document.createElement('div');
      entry.className = 'debug-entry';
      entry.innerHTML = `
        <div class="debug-header">
          <strong>Chunk ${i + 1}</strong>
          <span class="debug-score">Score: ${item.rerank_score}</span>
          <span class="debug-page">Page ${item.page}</span>
        </div>
        <div class="debug-text">${item.chunk}</div>
      `;
      panel.appendChild(entry);
    });

    toggle.addEventListener('click', () => {
      const open = panel.style.display !== 'none';
      panel.style.display = open ? 'none' : 'block';
      toggle.textContent = open ? '▶ Show retrieved chunks' : '▼ Hide retrieved chunks';
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

// Backend call
const API_BASE = 'http://localhost:5000';

async function sendToBackend(question) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error('Failed');
  return await res.json();
}
