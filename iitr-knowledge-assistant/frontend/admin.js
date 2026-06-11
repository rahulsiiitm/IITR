document.addEventListener('DOMContentLoaded', () => {
    // Nav elements
    const navItems = document.querySelectorAll('.nav-item');
    const viewContainers = document.querySelectorAll('.view-container');
    const currentViewTitle = document.getElementById('current-view-title');
    
    // Sessions elements
    const sessionsListContainer = document.getElementById('sessions-list');
    const messagesContainer = document.getElementById('messages-container');
    const emptyState = document.getElementById('empty-state');
    const sessionActions = document.getElementById('session-actions');
    const btnDeleteSession = document.getElementById('btn-delete-session');
    
    let currentSessionId = null;

    // View Switching Logic
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;
            
            // Update active nav
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // Update title
            currentViewTitle.textContent = item.textContent.trim() + (view === 'dashboard' ? ' Overview' : '');
            
            // Show relevant view container
            viewContainers.forEach(container => container.classList.remove('active'));
            document.getElementById(`view-${view}`).classList.add('active');
            
            // Contextual Sidebar logic
            if (view === 'sessions') {
                sessionsListContainer.style.display = 'block';
                if (!sessionsListContainer.hasAttribute('data-loaded')) {
                    fetchSessions();
                }
            } else {
                sessionsListContainer.style.display = 'none';
            }
            
            // Load specific data based on view
            if (view === 'dashboard') loadDashboardStats();
            if (view === 'settings') loadSettings();
        });
    });

    /* =================================================================
     * DASHBOARD LOGIC
     * ================================================================= */
    async function loadDashboardStats() {
        try {
            const res = await fetch('/api/admin/stats');
            const data = await res.json();
            document.getElementById('stat-sessions').textContent = data.total_sessions;
            document.getElementById('stat-messages').textContent = data.total_messages;
            document.getElementById('stat-llm').textContent = data.llm_model;
            document.getElementById('stat-llm').title = data.llm_model; // tooltip if too long
        } catch (error) {
            console.error('Error fetching stats', error);
        }
    }

    /* =================================================================
     * SETTINGS LOGIC
     * ================================================================= */
    async function loadSettings() {
        const settingsList = document.getElementById('settings-list');
        try {
            const res = await fetch('/api/admin/settings');
            const data = await res.json();
            
            settingsList.innerHTML = '';
            for (const [key, value] of Object.entries(data)) {
                // Formatting key to be readable
                const readableKey = key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
                
                settingsList.innerHTML += `
                    <div class="setting-item">
                        <div class="setting-label">${readableKey}</div>
                        <div class="setting-value">${escapeHtml(value)}</div>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Error fetching settings', error);
            settingsList.innerHTML = `<div class="empty-state"><p>Error loading settings.</p></div>`;
        }
    }

    /* =================================================================
     * SESSIONS LOGIC
     * ================================================================= */
    async function fetchSessions() {
        try {
            const response = await fetch('/api/admin/sessions');
            if (!response.ok) throw new Error('Failed to fetch sessions');
            const sessions = await response.json();
            renderSessions(sessions);
            sessionsListContainer.setAttribute('data-loaded', 'true');
        } catch (error) {
            console.error(error);
            sessionsListContainer.innerHTML = `<div class="empty-state"><p>Error loading sessions.</p></div>`;
        }
    }

    function renderSessions(sessions) {
        sessionsListContainer.innerHTML = '';
        if (sessions.length === 0) {
            sessionsListContainer.innerHTML = `<div class="empty-state"><p>No sessions found.</p></div>`;
            return;
        }

        sessions.forEach(session => {
            const date = new Date(session.created_at).toLocaleString();
            const el = document.createElement('div');
            el.className = 'session-item';
            el.innerHTML = `
                <div class="session-id">${session.id}</div>
                <div class="session-date"><i class="fa-regular fa-clock"></i> ${date}</div>
            `;
            el.addEventListener('click', () => {
                document.querySelectorAll('.session-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                currentSessionId = session.id;
                loadSessionMessages(session.id, date);
            });
            sessionsListContainer.appendChild(el);
        });
    }

    async function loadSessionMessages(sessionId, dateStr) {
        emptyState.style.display = 'none';
        sessionActions.style.display = 'none';
        messagesContainer.innerHTML = `<div class="loading-spinner"><i class="fa-solid fa-circle-notch fa-spin"></i></div>`;
        currentViewTitle.textContent = `Session: ${sessionId}`;

        try {
            const response = await fetch(`/api/admin/sessions/${sessionId}/messages`);
            if (!response.ok) throw new Error('Failed to fetch messages');
            const messages = await response.json();
            renderMessages(messages);
            sessionActions.style.display = 'flex';
        } catch (error) {
            console.error(error);
            messagesContainer.innerHTML = `<div class="empty-state"><p>Error loading messages.</p></div>`;
        }
    }

    function renderMessages(messages) {
        messagesContainer.innerHTML = '';
        if (messages.length === 0) {
            messagesContainer.innerHTML = `<div class="empty-state"><p>No messages in this session.</p></div>`;
            return;
        }

        messages.forEach(msg => {
            const msgEl = document.createElement('div');
            msgEl.className = `message msg-${msg.role}`;
            
            const icon = msg.role === 'user' ? 'fa-user' : 'fa-robot';
            const title = msg.role === 'user' ? 'User' : 'Assistant';

            let sourcesHtml = '';
            if (msg.sources && msg.sources.length > 0) {
                let parsedSources = msg.sources;
                if (typeof msg.sources === 'string') {
                    try {
                        parsedSources = JSON.parse(msg.sources);
                    } catch(e) {}
                }
                if (Array.isArray(parsedSources)) {
                    const sourceTags = parsedSources.map(s => {
                        const title = s.metadata?.title || s.metadata?.source || 'Source';
                        return `<span class="source-tag"><i class="fa-solid fa-book"></i> ${escapeHtml(title)}</span>`;
                    }).join('');
                    sourcesHtml = `<div class="msg-sources"><strong>Sources:</strong><br>${sourceTags}</div>`;
                }
            }

            msgEl.innerHTML = `
                <div class="msg-header">
                    <i class="fa-solid ${icon}"></i> ${title}
                </div>
                <div class="msg-content">${escapeHtml(msg.content)}</div>
                ${sourcesHtml}
            `;
            messagesContainer.appendChild(msgEl);
        });

        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Delete Session Action
    btnDeleteSession.addEventListener('click', async () => {
        if (!currentSessionId) return;
        
        if (confirm('Are you sure you want to delete this session and all its messages? This action cannot be undone.')) {
            try {
                const res = await fetch(`/api/admin/sessions/${currentSessionId}`, { method: 'DELETE' });
                if (res.ok) {
                    alert('Session deleted successfully.');
                    messagesContainer.innerHTML = `<div class="empty-state"><i class="fa-solid fa-database"></i><p>Select a session from the sidebar to view its messages.</p></div>`;
                    sessionActions.style.display = 'none';
                    currentViewTitle.textContent = 'Sessions';
                    currentSessionId = null;
                    fetchSessions(); // Refresh list
                    loadDashboardStats(); // Refresh stats if someone goes back to dashboard
                } else {
                    alert('Failed to delete session.');
                }
            } catch (err) {
                console.error(err);
                alert('An error occurred while deleting the session.');
            }
        }
    });

    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return String(unsafe)
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    // Initialize Dashboard as default view
    loadDashboardStats();
});
