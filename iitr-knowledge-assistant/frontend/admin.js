document.addEventListener('DOMContentLoaded', () => {

  /* ── DOM refs ── */
  const navItems = document.querySelectorAll('.nav-item');
  const viewContainers = document.querySelectorAll('.view-container');
  const currentViewTitle = document.getElementById('current-view-title');
  const breadcrumbCurrent = document.getElementById('breadcrumb-current');
  const sessionsListEl = document.getElementById('sessions-list');
  const messagesContainer = document.getElementById('messages-container');
  const emptyState = document.getElementById('empty-state');
  const sessionActions = document.getElementById('session-actions');
  const sessionActionsMeta = document.getElementById('session-actions-meta');
  const messagesToolbar = document.getElementById('messages-toolbar');
  const btnDeleteSession = document.getElementById('btn-delete-session');
  const btnDeleteAllSessions = document.getElementById('btn-delete-all-sessions');
  const sessionsBadge = document.getElementById('sessions-badge');
  const topbarModel = document.getElementById('topbar-model');

  let currentSessionId = null;
  let currentMsgCount = 0;

  /* ── Confirm Modal ── */
  const confirmModal = document.getElementById('confirmModal');
  const confirmModalTitle = document.getElementById('confirmModalTitle');
  const confirmModalBody = document.getElementById('confirmModalBody');
  const confirmModalOk = document.getElementById('confirmModalOk');
  const confirmModalCancel = document.getElementById('confirmModalCancel');

  function showConfirm(title, body) {
    return new Promise(resolve => {
      confirmModalTitle.textContent = title;
      confirmModalBody.textContent = body;
      confirmModal.classList.add('open');

      function cleanup(result) {
        confirmModal.classList.remove('open');
        confirmModalOk.removeEventListener('click', onOk);
        confirmModalCancel.removeEventListener('click', onCancel);
        confirmModal.removeEventListener('click', onBackdrop);
        resolve(result);
      }

      function onOk() { cleanup(true); }
      function onCancel() { cleanup(false); }
      function onBackdrop(e) { if (e.target === confirmModal) cleanup(false); }

      confirmModalOk.addEventListener('click', onOk);
      confirmModalCancel.addEventListener('click', onCancel);
      confirmModal.addEventListener('click', onBackdrop);
    });
  }

  const VIEW_TITLES = {
    dashboard: ['Dashboard', 'Overview'],
    sessions: ['Sessions', 'Conversation Log'],
    settings: ['Settings', 'Configuration'],
  };

  /* ── Utilities ── */
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function relativeTime(dateStr) {
    if (!dateStr.endsWith('Z') && !dateStr.includes('+')) dateStr += 'Z';
    const diff = (Date.now() - new Date(dateStr)) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  }

  function formatDate(dateStr) {
    if (!dateStr.endsWith('Z') && !dateStr.includes('+')) dateStr += 'Z';
    return new Date(dateStr).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  }

  /* ── View Switching ── */
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const view = item.dataset.view;
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      const [bc, title] = VIEW_TITLES[view];
      breadcrumbCurrent.textContent = bc;
      currentViewTitle.textContent = title;

      viewContainers.forEach(c => c.classList.remove('active'));
      document.getElementById(`view-${view}`).classList.add('active');

      if (view === 'sessions') {
        sessionsListEl.style.display = 'block';
        if (!sessionsListEl.hasAttribute('data-loaded')) fetchSessions();
      } else {
        sessionsListEl.style.display = 'none';
      }

      if (view === 'dashboard') loadDashboardStats();
      if (view === 'settings') loadSettings();
    });
  });

  /* ══ DASHBOARD ══ */
  async function loadDashboardStats() {
    try {
      const res = await fetch('/api/admin/stats');
      const data = await res.json();

      document.getElementById('stat-sessions').textContent = data.total_sessions ?? '—';
      document.getElementById('stat-messages').textContent = data.total_messages ?? '—';
      document.getElementById('stat-llm').textContent = data.llm_model ?? '—';
      topbarModel.textContent = data.llm_model ? data.llm_model.split(':')[0] : '—';

      renderActivityFeed(data);
      renderSystemInfo(data);
    } catch (err) {
      console.error('Stats error:', err);
    }
  }

  function renderActivityFeed(data) {
    const feed = document.getElementById('activity-feed');
    const items = [
      { dot: 'dot-blue', text: `Chatbot serving <strong>${data.total_sessions ?? 0}</strong> sessions`, time: 'now' },
      { dot: 'dot-green', text: `Retrieval pipeline: BM25 + FAISS + RRF hybrid`, time: 'active' },
      { dot: 'dot-green', text: `Cross-encoder reranking enabled`, time: 'active' },
      { dot: 'dot-blue', text: `SSE streaming active`, time: 'active' },
      { dot: 'dot-amber', text: `Model: ${escapeHtml(data.llm_model ?? 'unknown')}`, time: 'config' },
    ];
    feed.innerHTML = items.map(i => `
      <div class="activity-item">
        <div class="activity-dot ${i.dot}"></div>
        <div class="activity-text">${i.text}</div>
        <div class="activity-time">${i.time}</div>
      </div>
    `).join('');
  }

  function renderSystemInfo(data) {
    const grid = document.getElementById('system-info-grid');
    const entries = Object.entries(data).filter(([k]) =>
      !['total_sessions', 'total_messages', 'llm_model'].includes(k)
    );
    if (!entries.length) {
      grid.innerHTML = '';
      return;
    }
    grid.innerHTML = entries.map(([key, val]) => {
      const label = key.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
      const icon = iconForKey(key);
      return `
        <div class="info-card">
          <div class="info-card-label"><i class="fa-solid ${icon}"></i> ${label}</div>
          <div class="info-card-value">${escapeHtml(String(val))}</div>
        </div>
      `;
    }).join('');
  }

  function iconForKey(key) {
    const map = {
      embed: 'fa-cube', retriever: 'fa-magnifying-glass',
      reranker: 'fa-sort', db: 'fa-database', database: 'fa-database',
      host: 'fa-server', port: 'fa-network-wired', version: 'fa-tag',
      threshold: 'fa-sliders', top_k: 'fa-list-ol', chunks: 'fa-layer-group',
    };
    for (const k of Object.keys(map)) {
      if (key.toLowerCase().includes(k)) return map[k];
    }
    return 'fa-circle-info';
  }

  /* ══ SETTINGS ══ */
  window.loadSettings = async function () {
    const grid = document.getElementById('settings-grid');
    grid.innerHTML = `<div class="loading-spinner" style="grid-column:span 2"><i class="fa-solid fa-circle-notch fa-spin"></i></div>`;
    try {
      const res = await fetch('/api/admin/settings');
      const data = await res.json();

      // Group settings into logical cards
      const groups = {
        'Retrieval': ['top_k', 'threshold', 'chunks', 'reranker', 'retriever'],
        'Model': ['llm_model', 'model', 'embed', 'embedding'],
        'Storage': ['db', 'database', 'host', 'port', 'path'],
        'Server': ['version', 'debug', 'env', 'workers'],
      };

      const assigned = new Set();
      let html = '';

      for (const [groupName, keys] of Object.entries(groups)) {
        const matches = Object.entries(data).filter(([k]) =>
          keys.some(gk => k.toLowerCase().includes(gk))
        );
        if (!matches.length) continue;
        matches.forEach(([k]) => assigned.add(k));

        const icon = {
          'Retrieval': 'fa-magnifying-glass', 'Model': 'fa-microchip',
          'Storage': 'fa-database', 'Server': 'fa-server',
        }[groupName] || 'fa-gear';

        html += `
          <div class="settings-card">
            <div class="settings-card-header">
              <i class="fa-solid ${icon}"></i>
              <h3>${groupName}</h3>
            </div>
            ${matches.map(([k, v]) => {
          const label = k.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
          return `
                <div class="setting-item">
                  <div class="setting-label">${label}</div>
                  <div class="setting-value" title="${escapeHtml(String(v))}">${escapeHtml(String(v))}</div>
                </div>
              `;
        }).join('')}
          </div>
        `;
      }

      // Catch-all for ungrouped
      const remaining = Object.entries(data).filter(([k]) => !assigned.has(k));
      if (remaining.length) {
        html += `
          <div class="settings-card">
            <div class="settings-card-header">
              <i class="fa-solid fa-ellipsis"></i>
              <h3>Other</h3>
            </div>
            ${remaining.map(([k, v]) => {
          const label = k.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
          return `
                <div class="setting-item">
                  <div class="setting-label">${label}</div>
                  <div class="setting-value" title="${escapeHtml(String(v))}">${escapeHtml(String(v))}</div>
                </div>
              `;
        }).join('')}
          </div>
        `;
      }

      grid.innerHTML = html || `<div class="empty-state" style="grid-column:span 2"><p>No settings available.</p></div>`;
    } catch (err) {
      console.error(err);
      grid.innerHTML = `<div class="empty-state" style="grid-column:span 2"><p>Error loading settings.</p></div>`;
    }
  };

  /* ══ SESSIONS ══ */
  async function fetchSessions() {
    sessionsListEl.innerHTML = `<div class="sessions-label">Active Sessions</div><div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i></div>`;
    try {
      const res = await fetch('/api/admin/sessions');
      if (!res.ok) throw new Error('Failed');
      const sessions = await res.json();
      renderSessions(sessions);
      sessionsListEl.setAttribute('data-loaded', 'true');

      // Update badge
      if (sessions.length) {
        sessionsBadge.textContent = sessions.length;
        sessionsBadge.style.display = 'block';
      }
    } catch (err) {
      console.error(err);
      sessionsListEl.innerHTML = `<div class="empty-state" style="padding:16px;"><p>Failed to load sessions.</p></div>`;
    }
  }

  function renderSessions(sessions) {
    sessionsListEl.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
        <div class="sessions-label" style="padding-bottom: 0;">Active Sessions</div>
        <button class="btn btn-danger" id="btn-delete-all-sessions" style="padding: 2px 6px; font-size: 0.65rem; margin-right: 6px;" title="Delete all sessions">
          <i class="fa-solid fa-trash-can"></i> Clear All
        </button>
      </div>
    `;

    // Re-attach listener since we replaced innerHTML
    document.getElementById('btn-delete-all-sessions').addEventListener('click', handleDeleteAllSessions);

    if (!sessions.length) {
      sessionsListEl.innerHTML += `<div class="empty-state" style="padding:16px;"><p>No sessions found.</p></div>`;
      sessionsBadge.style.display = 'none';
      return;
    }
    sessions.forEach(session => {
      const el = document.createElement('div');
      el.className = 'session-item';
      el.innerHTML = `
        <div class="session-id">${session.id}</div>
        <div class="session-meta">
          <div class="session-date">
            <i class="fa-regular fa-clock"></i>
            ${relativeTime(session.created_at)}
          </div>
          ${session.message_count ? `<div class="session-msg-count">${session.message_count} msgs</div>` : ''}
        </div>
      `;
      el.addEventListener('click', () => {
        document.querySelectorAll('.session-item').forEach(i => i.classList.remove('active'));
        el.classList.add('active');
        currentSessionId = session.id;
        loadSessionMessages(session.id, session.created_at);
      });
      sessionsListEl.appendChild(el);
    });
  }

  async function loadSessionMessages(sessionId, createdAt) {
    emptyState.style.display = 'none';
    sessionActions.style.display = 'none';
    messagesToolbar.style.display = 'none';
    messagesContainer.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i></div>`;
    currentViewTitle.textContent = 'Conversation Log';

    document.getElementById('active-session-id-pill').textContent = sessionId;

    try {
      const res = await fetch(`/api/admin/sessions/${sessionId}/messages`);
      if (!res.ok) throw new Error('Failed');
      const msgs = await res.json();
      renderMessages(msgs);
      currentMsgCount = msgs.length;

      // Toolbar
      messagesToolbar.style.display = 'flex';
      document.getElementById('msg-count-label').textContent = `${msgs.length} message${msgs.length !== 1 ? 's' : ''}`;

      // Footer
      sessionActions.style.display = 'flex';
      sessionActionsMeta.innerHTML = `
        <i class="fa-regular fa-calendar" style="color:var(--text-light)"></i>
        Created ${formatDate(createdAt)}
      `;
    } catch (err) {
      console.error(err);
      messagesContainer.innerHTML = `<div class="empty-state"><p>Failed to load messages.</p></div>`;
    }
  }

  function renderMessages(messages) {
    messagesContainer.innerHTML = '';
    if (!messages.length) {
      messagesContainer.innerHTML = `
        <div class="empty-state">
          <i class="fa-solid fa-comment-slash"></i>
          <p>No messages in this session.</p>
        </div>`;
      return;
    }

    messages.forEach(msg => {
      const isUser = msg.role === 'user';
      const el = document.createElement('div');
      el.className = `message msg-${msg.role}`;

      let sourcesHtml = '';
      if (msg.sources) {
        let sources = msg.sources;
        if (typeof sources === 'string') {
          try { sources = JSON.parse(sources); } catch (_) { }
        }
        if (Array.isArray(sources) && sources.length) {
          const tags = sources.map(s => {
            const t = s.metadata?.title || s.metadata?.source || 'Source';
            return `<span class="source-tag"><i class="fa-solid fa-book-open"></i> ${escapeHtml(t)}</span>`;
          }).join('');
          sourcesHtml = `<div class="msg-sources"><div class="sources-label">Sources</div>${tags}</div>`;
        }
      }

      el.innerHTML = `
        <div class="msg-label">
          <i class="fa-solid ${isUser ? 'fa-user' : 'fa-robot'}"></i>
          ${isUser ? 'User' : 'Assistant'}
        </div>
        <div class="msg-bubble">
          <div style="white-space:pre-wrap">${escapeHtml(msg.content)}</div>
          ${sourcesHtml}
        </div>
      `;
      messagesContainer.appendChild(el);
    });

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  /* Delete session */
  btnDeleteSession.addEventListener('click', async () => {
    if (!currentSessionId) return;
    const ok = await showConfirm(
      'Delete Session',
      `Delete session ${currentSessionId.slice(0, 8)}…? This will permanently remove the session and all its messages.`
    );
    if (!ok) return;
    try {
      const res = await fetch(`/api/admin/sessions/${currentSessionId}`, { method: 'DELETE' });
      if (res.ok) {
        messagesContainer.innerHTML = `
          <div class="empty-state">
            <i class="fa-solid fa-check-circle" style="color:var(--success)"></i>
            <p>Session deleted.</p>
            <span>Select another session from the sidebar.</span>
          </div>`;
        sessionActions.style.display = 'none';
        messagesToolbar.style.display = 'none';
        currentViewTitle.textContent = 'Conversation Log';
        currentSessionId = null;
        sessionsListEl.removeAttribute('data-loaded');
        fetchSessions();
        loadDashboardStats();
      } else {
        alert('Failed to delete session.');
      }
    } catch (err) {
      console.error(err);
      alert('Error deleting session.');
    }
  });

  async function handleDeleteAllSessions() {
    const ok = await showConfirm(
      'Delete All Sessions',
      'This will permanently remove EVERY conversation log in the database. This cannot be undone.'
    );
    if (!ok) return;
    try {
      const res = await fetch(`/api/admin/sessions`, { method: 'DELETE' });
      if (res.ok) {
        messagesContainer.innerHTML = `
          <div class="empty-state">
            <i class="fa-solid fa-check-circle" style="color:var(--success)"></i>
            <p>All sessions deleted.</p>
            <span>The database is now empty.</span>
          </div>`;
        sessionActions.style.display = 'none';
        messagesToolbar.style.display = 'none';
        currentViewTitle.textContent = 'Conversation Log';
        currentSessionId = null;
        sessionsListEl.removeAttribute('data-loaded');
        fetchSessions();
        loadDashboardStats();
      } else {
        alert('Failed to delete all sessions.');
      }
    } catch (err) {
      console.error(err);
      alert('Error deleting all sessions.');
    }
  }

  if (btnDeleteAllSessions) {
    btnDeleteAllSessions.addEventListener('click', handleDeleteAllSessions);
  }

  /* ── Init ── */
  loadDashboardStats();
});