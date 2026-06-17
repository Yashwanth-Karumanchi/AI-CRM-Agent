// ── Chat ───────────────────────────────────────────────
Nav.init();

let chatHistory    = [];
let sessionContext = {
    lastClientId: null, lastClientName: null, lastAction: null,
    pendingAction: null, lastCompletedAction: null, deletedClients: []
};
let attachedFile   = null;
let _isProcessing  = false;

// Prevent navigation mid-request
window.addEventListener('beforeunload', e => {
    if (_isProcessing) { e.preventDefault(); e.returnValue = ''; }
});

// ── Session persistence ────────────────────────────────
function loadSession() {
    try {
        const saved = sessionStorage.getItem('aria_session');
        if (!saved) return;
        const parsed = JSON.parse(saved);
        chatHistory    = parsed.chatHistory    || [];
        sessionContext = parsed.sessionContext || sessionContext;
        if (chatHistory.length) restoreChatUI();
    } catch {}
}

function saveSession() {
    try {
        sessionStorage.setItem('aria_session',
            JSON.stringify({ chatHistory, sessionContext }));
    } catch {}
}

function restoreChatUI() {
    const container = document.getElementById('chatMessages');
    chatHistory.forEach(msg => container.appendChild(_makeMsgEl(msg.role, msg.content)));
    container.scrollTop = container.scrollHeight;
}

loadSession();

// ── File attachment ────────────────────────────────────
function handleFileAttach(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
        Toast.error('File too large. Max 10 MB.');
        return;
    }
    const allowed = [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel', 'text/csv',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword'
    ];
    const ext = file.name.split('.').pop().toLowerCase();
    const validExt = ['pdf','xlsx','xls','csv','docx','doc'].includes(ext);
    if (!validExt && !allowed.includes(file.type)) {
        Toast.error('Unsupported file type. Use PDF, Excel, CSV, or Word.');
        return;
    }
    attachedFile = file;
    document.getElementById('filePreviewIcon').innerHTML = fileTypeIcon(file.name);
    document.getElementById('filePreviewName').textContent = file.name;
    document.getElementById('filePreviewSize').textContent = formatBytes(file.size);
    document.getElementById('filePreviewArea').classList.remove('hidden');
    Toast.info(`${file.name} attached`);
}

function removeAttachment() {
    attachedFile = null;
    document.getElementById('filePreviewArea').classList.add('hidden');
    document.getElementById('chatFileInput').value = '';
}

// ── Quick actions ──────────────────────────────────────
function quick(text) {
    document.getElementById('chatInput').value = text;
    send();
}

function confirm_action(btn) {
    btn.closest('.chat-confirm-buttons').querySelectorAll('button')
       .forEach(b => b.disabled = true);
    document.getElementById('chatInput').value = 'yes';
    send();
}

function cancel_action(btn) {
    btn.closest('.chat-confirm-buttons').querySelectorAll('button')
       .forEach(b => b.disabled = true);
    document.getElementById('chatInput').value = 'no';
    send();
}

// ── Send ───────────────────────────────────────────────
async function send() {
    const inputEl = document.getElementById('chatInput');
    const text    = inputEl.value.trim();
    const file    = attachedFile;

    if (!text && !file) return;
    if (_isProcessing) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';
    _isProcessing = true;
    document.getElementById('sendBtn').disabled = true;

    addUserMessage(text, file);
    if (file) removeAttachment();
    chatHistory.push({ role: 'user', content: text || `[file: ${file?.name}]` });

    const thinkId = addThinking();

    try {
        let res;
        if (file) {
            updateThinking(thinkId, 'Processing file...');
            const form = new FormData();
            form.append('file', file);
            form.append('message', text);
            form.append('history', JSON.stringify(
                chatHistory.slice(-10).map(m => ({ role: m.role, content: m.content }))
            ));
            form.append('session_context', JSON.stringify(sessionContext));
            const rawRes = await API.upload('POST', '/aria/chat/upload', form);
            res = await rawRes.json();
        } else {
            updateThinking(thinkId, 'Thinking...');
            res = await API.post('/aria/chat', {
                message:         text,
                history:         chatHistory.slice(-10).map(m => ({ role: m.role, content: m.content })),
                session_context: sessionContext
            });
        }

        removeThinking(thinkId);

        if (res.needs_confirmation) {
            addConfirmMessage(res.response);
        } else {
            addAriaMessage(res.response);
        }

        chatHistory.push({ role: 'assistant', content: res.response });
        if (res.context) Object.assign(sessionContext, res.context);
        saveSession();

    } catch (e) {
        removeThinking(thinkId);
        addAriaMessage(`Sorry, something went wrong: ${e.message}`);
        Toast.error(e.message);
    } finally {
        _isProcessing = false;
        document.getElementById('sendBtn').disabled = false;
    }
}

// ── Message rendering ──────────────────────────────────
function _makeMsgEl(role, text) {
    const isUser = role === 'user';
    const div    = document.createElement('div');
    div.className = `chat-message${isUser ? ' user' : ''}`;
    div.innerHTML = `<div class="chat-avatar ${isUser ? 'user' : 'aria'}">${
        isUser
        ? Icons.user
        : `<svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="3"/><path stroke-linecap="round" d="M10 2v2m0 12v2M2 10h2m12 0h2M4.93 4.93l1.41 1.41m7.32 7.32l1.41 1.41M4.93 15.07l1.41-1.41m7.32-7.32l1.41-1.41"/></svg>`
    }</div><div class="chat-bubble ${isUser ? 'user' : 'aria'}" style="white-space:pre-wrap;line-height:1.65;width:fit-content">${escapeHtml(text)}</div>`;
    return div;
}

function addUserMessage(text, file) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'chat-message user';
    div.innerHTML = `<div class="chat-avatar user">${Icons.user}</div>
    <div style="max-width:560px">
        ${file ? `<div class="chat-file-preview mb-2" style="background:rgba(255,255,255,0.15);border-color:rgba(255,255,255,0.3)">
            <div class="chat-file-icon" style="background:rgba(255,255,255,0.2);color:white">${fileTypeIcon(file.name)}</div>
            <div style="flex:1;min-width:0">
                <div class="chat-file-name" style="color:white">${escapeHtml(file.name)}</div>
                <div class="chat-file-size" style="color:rgba(255,255,255,0.7)">${formatBytes(file.size)}</div>
            </div>
        </div>` : ''}
        ${text ? `<div class="chat-bubble user" style="white-space:pre-wrap;line-height:1.65;width:fit-content">${escapeHtml(text)}</div>` : ''}
    </div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addAriaMessage(text) {
    const container = document.getElementById('chatMessages');
    container.appendChild(_makeMsgEl('aria', text));
    container.scrollTop = container.scrollHeight;
}

function addConfirmMessage(text) {
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.className = 'chat-message';
    div.innerHTML = `<div class="chat-avatar aria"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="3"/><path stroke-linecap="round" d="M10 2v2m0 12v2M2 10h2m12 0h2M4.93 4.93l1.41 1.41m7.32 7.32l1.41 1.41M4.93 15.07l1.41-1.41m7.32-7.32l1.41-1.41"/></svg></div>
    <div>
        <div class="chat-bubble aria" style="white-space:pre-wrap;line-height:1.65;width:fit-content">${escapeHtml(text)}</div>
        <div class="chat-confirm-buttons">
            <button class="btn btn-success btn-sm" id="confirmYesBtn">${Icons.check} Yes, go ahead</button>
            <button class="btn btn-danger btn-sm" id="confirmNoBtn">${Icons.x} Cancel</button>
        </div>
    </div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    div.querySelector('#confirmYesBtn').addEventListener('click', function() { confirm_action(this); });
    div.querySelector('#confirmNoBtn').addEventListener('click',  function() { cancel_action(this);  });
}

function addThinking() {
    const id  = 'think-' + Date.now();
    const container = document.getElementById('chatMessages');
    const div = document.createElement('div');
    div.id = id;
    div.className = 'chat-message';
    div.innerHTML = `<div class="chat-avatar aria"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="3"/><path stroke-linecap="round" d="M10 2v2m0 12v2M2 10h2m12 0h2M4.93 4.93l1.41 1.41m7.32 7.32l1.41 1.41M4.93 15.07l1.41-1.41m7.32-7.32l1.41-1.41"/></svg></div>
    <div class="chat-bubble aria"><div class="flex items-center gap-3">
        <div class="thinking-dots"><div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div></div>
        <span id="${id}-text" class="text-muted text-xs" style="transition:opacity 0.2s">Thinking...</span>
    </div></div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function updateThinking(id, msg) {
    const el = document.getElementById(id + '-text');
    if (!el) return;
    el.style.opacity = '0';
    setTimeout(() => { el.textContent = msg; el.style.opacity = '1'; }, 120);
}

function removeThinking(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.transition = 'opacity 0.2s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 200);
}

// ── Clear chat ─────────────────────────────────────────
function clearChat() {
    chatHistory    = [];
    sessionContext = { lastClientId: null, lastClientName: null, lastAction: null,
                       pendingAction: null, lastCompletedAction: null, deletedClients: [] };
    sessionStorage.removeItem('aria_session');
    removeAttachment();
    document.getElementById('chatMessages').innerHTML = `
        <div class="chat-message">
            <div class="chat-avatar aria"><svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="3"/><path stroke-linecap="round" d="M10 2v2m0 12v2M2 10h2m12 0h2M4.93 4.93l1.41 1.41m7.32 7.32l1.41 1.41M4.93 15.07l1.41-1.41m7.32-7.32l1.41-1.41"/></svg></div>
            <div class="chat-bubble aria">Chat cleared. How can I help?</div>
        </div>`;
}

// ── Event listeners ────────────────────────────────────
document.getElementById('sendBtn')
        .addEventListener('click', send);
document.getElementById('clearChatBtn')
        .addEventListener('click', clearChat);
document.getElementById('chatFileInput')
        .addEventListener('change', handleFileAttach);
document.getElementById('removeAttachBtn')
        .addEventListener('click', removeAttachment);
document.getElementById('attachBtn')
        .addEventListener('click', () => document.getElementById('chatFileInput').click());
document.getElementById('chatInput')
        .addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
document.getElementById('chatInput')
        .addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 140) + 'px';
});

// Quick action buttons
document.querySelectorAll('.quick-action-btn[data-prompt]')
        .forEach(btn => btn.addEventListener('click', () => quick(btn.dataset.prompt)));