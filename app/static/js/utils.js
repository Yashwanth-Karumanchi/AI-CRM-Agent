// ── ARIA Utilities ─────────────────────────────────────

// ── Heroicon SVGs ──────────────────────────────────────
const Icons = {
    check:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"/></svg>`,
    x:           `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`,
    info:        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="8"/><path stroke-linecap="round" d="M10 7v1m0 3v3"/></svg>`,
    warning:     `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10 2l8 14H2L10 2zm0 5v4m0 2v1"/></svg>`,
    user:        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10 10a4 4 0 100-8 4 4 0 000 8zm-7 8a7 7 0 0114 0"/></svg>`,
    bot:         `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="6" width="14" height="10" rx="2"/><path stroke-linecap="round" d="M10 2v4M7 10h.01M13 10h.01M7 14h6"/></svg>`,
    paperclip:   `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 11-2.828-2.828l6.414-6.414a4 4 0 015.656 5.656l-6.414 6.414a6 6 0 01-8.485-8.485l6.414-6.413"/></svg>`,
    document:    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12h2m-2 4h2m4 2H5a2 2 0 01-2-2V4a2 2 0 012-2h6l4 4v10a2 2 0 01-2 2z"/></svg>`,
    table:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="16" height="14" rx="2"/><path d="M2 8h16M2 13h16M7 8v9"/></svg>`,
    refresh:     `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h5M16 16v-5h-5"/><path stroke-linecap="round" stroke-linejoin="round" d="M20.49 9A9 9 0 005.64 5.64L4 8m12 8l-1.64 2.36A9 9 0 013.51 11"/></svg>`,
    send:        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>`,
    arrowRight:  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M5 10h10m-4-4l4 4-4 4"/></svg>`,
    trash:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`,
    pencil:      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>`,
    eye:         `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>`,
    chevronDown: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>`,
    upload:      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"/></svg>`,
    download:    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>`,
    calendar:    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>`,
    mail:        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>`,
    chart:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6m6 0V9a2 2 0 012-2h2a2 2 0 012 2v10m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14"/></svg>`,
    users:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20H7m10 0v-2a4 4 0 00-4-4H7a4 4 0 00-4 4v2m14-10a4 4 0 11-8 0 4 4 0 018 0z"/></svg>`,
    search:      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>`,
    brain:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 3a5 5 0 015 5 5 5 0 01-5 5H4a2 2 0 01-2-2V7a4 4 0 014-4h3zm6 8a5 5 0 010 10H9v-5h6z"/></svg>`,
    signOut:     `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/></svg>`,
    star:        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>`,
    plus:        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/></svg>`,
    filter:      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><polygon stroke-linecap="round" stroke-linejoin="round" points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>`,
    undo:        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 10a7 7 0 107-7H3m0 0l3-3M3 3l3 3"/></svg>`,
    video:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><polygon stroke-linecap="round" stroke-linejoin="round" points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>`,
    notes:       `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/></svg>`,
    location:    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/></svg>`,
    archive:     `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><polyline stroke-linecap="round" stroke-linejoin="round" points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line stroke-linecap="round" x1="10" y1="12" x2="14" y2="12"/></svg>`,
    import:      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>`,
    restore:     `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h5M16 16v-5h-5"/><path stroke-linecap="round" stroke-linejoin="round" d="M20.49 9A9 9 0 005.64 5.64L4 8m12 8l-1.64 2.36A9 9 0 013.51 11"/></svg>`,
    errorCircle: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="10" cy="10" r="8"/><path stroke-linecap="round" d="M10 7v4m0 2v1"/></svg>`,
};
window.Icons = Icons;


// ── Toast Notifications ────────────────────────────────
const Toast = (() => {
    let _container = null;

    function _getContainer() {
        if (!_container || !document.body.contains(_container)) {
            _container = document.createElement('div');
            _container.className = 'toast-container';
            _container.id = 'toastContainer';
            document.body.appendChild(_container);
        }
        return _container;
    }

    const _iconMap = {
        success: Icons.check,
        error:   Icons.x,
        warning: Icons.warning,
        info:    Icons.info
    };

    function show(message, type = 'info', duration = 4500) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            ${_iconMap[type] || _iconMap.info}
            <span class="toast-message">${escapeHtml(String(message))}</span>
            <button class="toast-close" aria-label="Dismiss">${Icons.x}</button>
        `;
        toast.querySelector('.toast-close')
             .addEventListener('click', () => _dismiss(toast));
        _getContainer().appendChild(toast);
        const timer = setTimeout(() => _dismiss(toast), duration);
        toast._timer = timer;
        return toast;
    }

    function _dismiss(toast) {
        if (!toast || !toast.parentNode) return;
        clearTimeout(toast._timer);
        toast.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
        toast.style.opacity    = '0';
        toast.style.transform  = 'translateX(8px)';
        setTimeout(() => toast.remove(), 260);
    }

    return {
        success: (msg, dur) => show(msg, 'success', dur),
        error:   (msg, dur) => show(msg, 'error',   dur || 6000),
        warning: (msg, dur) => show(msg, 'warning', dur),
        info:    (msg, dur) => show(msg, 'info',    dur)
    };
})();


// ── HTML helpers ───────────────────────────────────────

function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(text ?? '')));
    return div.innerHTML;
}

/** Renders a standard loading overlay */
function loadingHTML(msg = 'Loading...') {
    return `<div class="loading-overlay">
        <div class="loading-spinner"></div>
        ${escapeHtml(msg)}
    </div>`;
}

/** Renders a standard empty / error state */
function emptyStateHTML(title, desc = '', iconSvg = '') {
    return `<div class="empty-state">
        ${iconSvg
            ? `<div class="empty-state-icon">${iconSvg}</div>`
            : ''}
        <div class="empty-state-title">${escapeHtml(title)}</div>
        ${desc
            ? `<div class="empty-state-desc">${escapeHtml(desc)}</div>`
            : ''}
    </div>`;
}


// ── Date helpers ───────────────────────────────────────

function formatDate(dt) {
    if (!dt) return '—';
    try {
        const d = new Date(dt);
        if (isNaN(d.getTime())) return String(dt).slice(0, 10);
        return d.toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric'
        });
    } catch { return String(dt).slice(0, 10); }
}

function formatDateTime(dt) {
    if (!dt) return '—';
    try {
        const d = new Date(dt);
        if (isNaN(d.getTime())) return String(dt).slice(0, 16);
        return d.toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return String(dt).slice(0, 16); }
}

function formatRelative(dt) {
    if (!dt) return '—';
    try {
        const diff  = Date.now() - new Date(dt).getTime();
        const mins  = Math.floor(diff / 60000);
        const hours = Math.floor(mins / 60);
        const days  = Math.floor(hours / 24);
        if (mins  < 1)  return 'Just now';
        if (mins  < 60) return `${mins}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days  < 7)  return `${days}d ago`;
        return formatDate(dt);
    } catch { return formatDate(dt); }
}


// ── Badge helpers ──────────────────────────────────────

function priorityBadge(priority) {
    if (!priority) return '<span class="badge badge-neutral">—</span>';
    const cls = priority.toLowerCase();
    return `<span class="badge badge-${cls}">
        <span class="priority-dot ${cls}"></span>
        ${escapeHtml(priority)}
    </span>`;
}

function stageBadge(stage) {
    if (!stage) return '';
    return `<span class="badge badge-stage">${escapeHtml(stage)}</span>`;
}


// ── JSON viewer ────────────────────────────────────────

function prettyJson(data) {
    try {
        const str = JSON.stringify(data, null, 2);
        return str
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"([^"]+)":/g,    '<span class="json-key">"$1"</span>:')
            .replace(/: "([^"]*)"/g,   ': <span class="json-string">"$1"</span>')
            .replace(/: (-?\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
            .replace(/: (true|false)/g,  ': <span class="json-bool">$1</span>')
            .replace(/: (null)/g,        ': <span class="json-null">$1</span>');
    } catch { return escapeHtml(String(data)); }
}


// ── Modal helpers ──────────────────────────────────────

function openModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.add('open');
    setTimeout(() => {
        const first = el.querySelector(
            'input:not([type=hidden]), textarea, select'
        );
        if (first) first.focus();
    }, 100);
}

function closeModal(id) {
    document.getElementById(id)?.classList.remove('open');
}

// Close on overlay click
document.addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('open');
    }
});

// Close on Escape
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.open')
                .forEach(m => m.classList.remove('open'));
    }
});


// ── Button loading state ───────────────────────────────

function setLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
        btn.disabled       = true;
        btn._originalHTML  = btn.innerHTML;
        btn.innerHTML      = '<div class="loading-spinner sm"></div>';
    } else {
        btn.disabled = false;
        if (btn._originalHTML) btn.innerHTML = btn._originalHTML;
    }
}


// ── Misc ───────────────────────────────────────────────

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a   = Object.assign(document.createElement('a'),
                              { href: url, download: filename });
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function debounce(fn, delay = 300) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
}

function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const k = 1024, sizes = ['B','KB','MB','GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function fileTypeIcon(filename) {
    const ext = (filename || '').split('.').pop().toLowerCase();
    if (ext === 'pdf')                return Icons.document;
    if (['xlsx','xls'].includes(ext)) return Icons.table;
    if (ext === 'csv')                return Icons.table;
    if (['doc','docx'].includes(ext)) return Icons.document;
    return Icons.document;
}

// ── Exports ────────────────────────────────────────────
Object.assign(window, {
    Icons, Toast,
    escapeHtml, loadingHTML, emptyStateHTML,
    formatDate, formatDateTime, formatRelative,
    priorityBadge, stageBadge,
    prettyJson,
    openModal, closeModal,
    setLoading,
    sleep, downloadBlob, debounce,
    formatBytes, fileTypeIcon
});