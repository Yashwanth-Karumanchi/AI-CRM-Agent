// ── Utilities ──────────────────────────────────────────

// Toast notifications
const Toast = (() => {
    let container;

    function getContainer() {
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function show(message, type = 'info', duration = 4000) {
        const icons = {
            success: '✅',
            error: '❌',
            info: 'ℹ️',
            warning: '⚠️'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span>${icons[type] || 'ℹ️'}</span>
            <span style="flex:1">${escapeHtml(message)}</span>
            <button onclick="this.parentElement.remove()"
                style="background:none;border:none;cursor:pointer;
                color:inherit;font-size:14px;padding:0;opacity:0.6">✕</button>
        `;

        getContainer().appendChild(toast);

        setTimeout(() => {
            toast.style.transition = 'opacity 0.3s ease';
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    return {
        success: (msg) => show(msg, 'success'),
        error: (msg) => show(msg, 'error'),
        info: (msg) => show(msg, 'info'),
        warning: (msg) => show(msg, 'warning')
    };
})();

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(String(text || '')));
    return div.innerHTML;
}

// Format date
function formatDate(dt) {
    if (!dt) return '—';
    try {
        return new Date(dt).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric'
        });
    } catch { return dt; }
}

// Format datetime
function formatDateTime(dt) {
    if (!dt) return '—';
    try {
        return new Date(dt).toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return dt; }
}

// Priority badge
function priorityBadge(priority) {
    if (!priority) return '';
    const cls = priority.toLowerCase();
    return `<span class="badge badge-${cls}">
        <span class="priority-dot ${cls}"></span>
        ${escapeHtml(priority)}
    </span>`;
}

// Stage badge
function stageBadge(stage) {
    if (!stage) return '';
    return `<span class="badge badge-stage">${escapeHtml(stage)}</span>`;
}

// Pretty JSON viewer
function prettyJson(data) {
    const str = JSON.stringify(data, null, 2);
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"([^"]+)":/g, '<span class="json-key">"$1"</span>:')
        .replace(/: "([^"]*)"/g, ': <span class="json-string">"$1"</span>')
        .replace(/: (\d+\.?\d*)/g, ': <span class="json-number">$1</span>')
        .replace(/: (true|false)/g, ': <span class="json-bool">$1</span>')
        .replace(/: null/g, ': <span class="json-null">null</span>');
}

// Open/close modal
function openModal(id) {
    document.getElementById(id)?.classList.add('open');
}

function closeModal(id) {
    document.getElementById(id)?.classList.remove('open');
}

// Sleep
function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

// Download blob
function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// Set loading state on button
function setLoading(btn, loading, originalText) {
    if (loading) {
        btn.disabled = true;
        btn.dataset.original = btn.textContent;
        btn.innerHTML = '<div class="loading-spinner" style="width:14px;height:14px;border-width:2px"></div>';
    } else {
        btn.disabled = false;
        btn.textContent = originalText || btn.dataset.original || btn.textContent;
    }
}

window.Toast = Toast;
window.escapeHtml = escapeHtml;
window.formatDate = formatDate;
window.formatDateTime = formatDateTime;
window.priorityBadge = priorityBadge;
window.stageBadge = stageBadge;
window.prettyJson = prettyJson;
window.openModal = openModal;
window.closeModal = closeModal;
window.sleep = sleep;
window.downloadBlob = downloadBlob;
window.setLoading = setLoading;