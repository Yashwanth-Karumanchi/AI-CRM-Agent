// ── Clients ────────────────────────────────────────────
Nav.init();

let allClients      = [];
let filteredClients = [];
let showArchived    = false;
let currentPage     = 1;
const PAGE_SIZE     = 25;

// ── Load ───────────────────────────────────────────────
async function loadClients() {
    _showError(null);
    document.getElementById('clientsTableBody').innerHTML =
        `<tr><td colspan="7">${loadingHTML('Loading clients...')}</td></tr>`;

    try {
        const url = showArchived
            ? '/clients?include_archived=true&limit=500'
            : '/clients?limit=500';
        const res = await API.get(url);
        allClients = res.clients || [];
        document.getElementById('clientCount').textContent =
            `${allClients.length} client${allClients.length !== 1 ? 's' : ''}`;
        currentPage = 1;
        filterClients();
        Nav.loadSidebarStats();
    } catch (e) {
        _showError('Failed to load: ' + e.message);
        document.getElementById('clientsTableBody').innerHTML =
            `<tr><td colspan="7">${emptyStateHTML('Could not load clients', e.message)}</td></tr>`;
    }
}

async function hardRefresh() {
    try { await API.post('/cache/clear', {}); } catch { /* ignore */ }
    await loadClients();
    Toast.info('Refreshed');
}

function _showError(msg) {
    const el = document.getElementById('errorBanner');
    if (msg) {
        document.getElementById('errorBannerMsg').textContent = msg;
        el.classList.remove('hidden');
    } else {
        el.classList.add('hidden');
    }
}

function toggleArchived() {
    showArchived = !showArchived;
    document.getElementById('archivedBtn').textContent =
        showArchived ? 'Hide Archived' : 'Show Archived';
    loadClients();
}

// ── Filter & Pagination ────────────────────────────────
function filterClients() {
    const q = document.getElementById('searchInput').value.toLowerCase();
    const p = document.getElementById('priorityFilter').value;
    const s = document.getElementById('stageFilter').value;

    filteredClients = allClients.filter(c => {
        const text = [c.name, c.company, c.email, c.service, c.client_id, c.notes]
            .join(' ').toLowerCase();
        return (!q || text.includes(q)) && (!p || c.priority === p) && (!s || c.stage === s);
    });
    currentPage = 1;
    renderTable();
}

function changePage(dir) {
    const total = Math.ceil(filteredClients.length / PAGE_SIZE);
    currentPage = Math.max(1, Math.min(total, currentPage + dir));
    renderTable();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ── Render ─────────────────────────────────────────────
function renderTable() {
    const tbody      = document.getElementById('clientsTableBody');
    const pagination = document.getElementById('pagination');

    if (!filteredClients.length) {
        tbody.innerHTML =
            `<tr><td colspan="7">${emptyStateHTML('No clients found', 'Adjust filters or add a new client')}</td></tr>`;
        pagination.classList.add('hidden');
        return;
    }

    const totalPages = Math.ceil(filteredClients.length / PAGE_SIZE);
    const start      = (currentPage - 1) * PAGE_SIZE;
    const page       = filteredClients.slice(start, start + PAGE_SIZE);
    const today      = new Date().toISOString().split('T')[0];

    tbody.innerHTML = page.map(c => {
        const isOverdue  = c.next_follow_up && c.next_follow_up < today;
        const isArchived = String(c.archived).toLowerCase() === 'yes';
        return `
        <tr data-client-id="${escapeHtml(c.client_id)}"
            style="${isArchived ? 'opacity:0.55' : ''}">
            <td>
                <div class="font-semibold">
                    ${escapeHtml(c.name)}
                    ${isArchived ? '<span class="badge badge-neutral ml-1">Archived</span>' : ''}
                </div>
                <div class="text-muted text-xs mt-1">${escapeHtml(c.client_id)}</div>
            </td>
            <td class="text-secondary">${escapeHtml(c.company || '—')}</td>
            <td class="text-secondary text-xs">
                <div class="truncate" style="max-width:160px">${escapeHtml(c.service || '—')}</div>
            </td>
            <td>${priorityBadge(c.priority)}</td>
            <td>${stageBadge(c.stage)}</td>
            <td class="text-xs ${isOverdue ? 'text-error font-semibold' : 'text-muted'}">
                ${c.next_follow_up || '—'}
                ${isOverdue ? Icons.warning : ''}
            </td>
            <td>
                <div class="flex gap-1" data-actions>
                    <button class="btn btn-ghost btn-icon btn-sm"
                        title="Score" data-action="score" data-id="${escapeHtml(c.client_id)}">
                        ${Icons.star}
                    </button>
                    <button class="btn btn-ghost btn-icon btn-sm"
                        title="Report" data-action="report" data-id="${escapeHtml(c.client_id)}">
                        ${Icons.download}
                    </button>
                    <button class="btn btn-ghost btn-icon btn-sm"
                        title="Email" data-action="email"
                        data-id="${escapeHtml(c.client_id)}">
                        ${Icons.mail}
                    </button>
                    ${isArchived
                        ? `<button class="btn btn-ghost btn-icon btn-sm"
                                title="Restore" data-action="restore"
                                data-id="${escapeHtml(c.client_id)}">${Icons.restore}</button>`
                        : `<button class="btn btn-ghost btn-icon btn-sm"
                                title="Delete" data-action="delete"
                                data-id="${escapeHtml(c.client_id)}"
                                data-name="${escapeHtml(c.name)}"
                                style="color:var(--error)">${Icons.trash}</button>`
                    }
                </div>
            </td>
        </tr>`;
    }).join('');

    if (totalPages > 1) {
        pagination.classList.remove('hidden');
        document.getElementById('paginationInfo').textContent =
            `Showing ${start + 1}–${Math.min(start + PAGE_SIZE, filteredClients.length)} of ${filteredClients.length}`;
        document.getElementById('prevBtn').disabled = currentPage === 1;
        document.getElementById('nextBtn').disabled = currentPage === totalPages;
    } else {
        pagination.classList.add('hidden');
    }
}

// ── Table click delegation ─────────────────────────────
document.getElementById('clientsTableBody').addEventListener('click', e => {
    // Row click → view detail
    const actionBtn = e.target.closest('[data-action]');
    if (actionBtn) {
        e.stopPropagation();
        const id     = actionBtn.dataset.id;
        const action = actionBtn.dataset.action;
        if (action === 'score')   quickScore(id);
        if (action === 'report')  quickReport(id);
        if (action === 'email')   window.location = `/aria/email?client=${id}`;
        if (action === 'restore') restoreClient(id);
        if (action === 'delete')  deleteClient(id, actionBtn.dataset.name);
        return;
    }
    const row = e.target.closest('tr[data-client-id]');
    if (row) viewClient(row.dataset.clientId);
});

// ── Client Detail ──────────────────────────────────────
async function viewClient(clientId) {
    try {
        const res = await API.get(`/clients/${clientId}`);
        const c   = res.client;
        document.getElementById('detailTitle').textContent = c.name;

        document.getElementById('detailBody').innerHTML = `
            <div class="grid-2 mb-4" style="gap:16px">
                <div><div class="input-label">Company</div><div>${escapeHtml(c.company || '—')}</div></div>
                <div><div class="input-label">Email</div>
                    <div>${c.email ? `<a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a>` : '—'}</div>
                </div>
                <div><div class="input-label">Phone</div><div>${escapeHtml(c.phone || '—')}</div></div>
                <div><div class="input-label">Service</div><div>${escapeHtml(c.service || '—')}</div></div>
                <div><div class="input-label">Priority</div><div>${priorityBadge(c.priority)}</div></div>
                <div>
                    <div class="input-label">Stage</div>
                    <select id="detailStageSelect" class="input select" data-client-id="${escapeHtml(c.client_id)}">
                        ${['New','Contacted','Consultation Scheduled','Proposal Sent','Won','Lost']
                            .map(s => `<option ${s === c.stage ? 'selected' : ''} value="${s}">${s}</option>`)
                            .join('')}
                    </select>
                </div>
                <div><div class="input-label">Next Follow-up</div>
                    <div class="${c.next_follow_up && c.next_follow_up < new Date().toISOString().split('T')[0] ? 'text-error font-semibold' : ''}">
                        ${c.next_follow_up || '—'}
                    </div>
                </div>
                <div><div class="input-label">Created</div><div class="text-muted">${formatDate(c.created_at)}</div></div>
                <div style="grid-column:1/-1">
                    <div class="input-label">Notes</div>
                    <div class="text-secondary" style="white-space:pre-wrap;line-height:1.6">
                        ${escapeHtml(c.notes || '—')}
                    </div>
                </div>
            </div>
            <div class="divider"></div>
            <div class="flex gap-2 flex-wrap">
                <button class="btn btn-secondary btn-sm" data-detail-action="score" data-id="${escapeHtml(c.client_id)}">${Icons.star} Score</button>
                <button class="btn btn-secondary btn-sm" data-detail-action="report" data-id="${escapeHtml(c.client_id)}">${Icons.download} Report</button>
                <button class="btn btn-secondary btn-sm" data-detail-action="activity" data-id="${escapeHtml(c.client_id)}">${Icons.notes} Activity</button>
                <button class="btn btn-secondary btn-sm" data-detail-action="audit" data-id="${escapeHtml(c.client_id)}">${Icons.restore} Audit Trail</button>
                <button class="btn btn-secondary btn-sm" data-detail-action="rollback" data-id="${escapeHtml(c.client_id)}">${Icons.undo} Rollback</button>
                <button class="btn btn-danger btn-sm" data-detail-action="delete" data-id="${escapeHtml(c.client_id)}" data-name="${escapeHtml(c.name)}">${Icons.trash} Delete</button>
            </div>
            <div id="detailResult" class="mt-4"></div>`;

        // Stage change
        document.getElementById('detailStageSelect')
                .addEventListener('change', function() {
            updateStage(this.dataset.clientId, this.value);
        });

        openModal('clientDetailModal');
    } catch (e) {
        Toast.error('Failed to load client: ' + e.message);
    }
}

// Detail modal action delegation
document.getElementById('clientDetailModal')
        .addEventListener('click', e => {
    const btn = e.target.closest('[data-detail-action]');
    if (!btn) return;
    const id     = btn.dataset.id;
    const action = btn.dataset.detailAction;
    if (action === 'score')    quickScore(id);
    if (action === 'report')   quickReport(id);
    if (action === 'activity') viewActivity(id);
    if (action === 'audit')    viewAudit(id);
    if (action === 'rollback') rollbackClient(id);
    if (action === 'delete')   deleteClient(id, btn.dataset.name);
});

// ── Actions ────────────────────────────────────────────
async function updateStage(clientId, stage) {
    try {
        await API.put(`/clients/${clientId}/stage`, { stage });
        Toast.success('Stage updated to ' + stage);
        await loadClients();
    } catch (e) { Toast.error('Update failed: ' + e.message); }
}

async function deleteClient(clientId, name) {
    if (!confirm(`Permanently delete "${name}"?\n\nSay "undo delete" in ARIA chat to restore within 1 hour.`)) return;
    try {
        await API.delete(`/clients/${clientId}/permanent`);
        Toast.success(`${name} deleted`);
        closeModal('clientDetailModal');
        await loadClients();
    } catch (e) { Toast.error('Delete failed: ' + e.message); }
}

async function restoreClient(clientId) {
    try {
        await API.post(`/clients/${clientId}/restore`);
        Toast.success('Client restored');
        closeModal('clientDetailModal');
        await loadClients();
    } catch (e) { Toast.error('Restore failed: ' + e.message); }
}

async function quickScore(clientId) {
    const el = document.getElementById('detailResult');
    if (el) el.innerHTML = loadingHTML('Scoring...');
    try {
        Toast.info('Scoring client...');
        const res = await API.get(`/clients/${clientId}/score`);
        const s   = res.score;
        const html = `
            <div class="divider"></div>
            <div class="grid-2 mb-3" style="gap:12px">
                <div class="stat-card" style="padding:16px">
                    <div class="stat-value">${s.lead_score}<span class="text-muted" style="font-size:16px">/10</span></div>
                    <div class="stat-label">Lead Score</div>
                </div>
                <div class="stat-card" style="padding:16px">
                    <div class="stat-value">${s.estimated_close_probability}<span class="text-muted" style="font-size:16px">%</span></div>
                    <div class="stat-label">Close Probability</div>
                </div>
            </div>
            <div class="card card-p">
                <div class="flex gap-4 mb-3 flex-wrap">
                    <div><div class="input-label">Churn Risk</div>
                        <span class="badge ${s.churn_risk==='High'?'badge-high':s.churn_risk==='Medium'?'badge-medium':'badge-low'}">
                            ${escapeHtml(s.churn_risk)}</span></div>
                    <div><div class="input-label">Sentiment</div>
                        <span class="badge badge-stage">${escapeHtml(s.sentiment)}</span></div>
                    <div><div class="input-label">Opportunity</div>
                        <span class="badge badge-stage">${escapeHtml(s.opportunity_value)}</span></div>
                </div>
                <div class="input-label">Best Next Action</div>
                <div class="text-secondary mb-3">${escapeHtml(s.best_next_action)}</div>
                <div class="input-label">Summary</div>
                <div class="text-secondary text-sm">${escapeHtml(s.summary)}</div>
            </div>`;
        if (el) el.innerHTML = html;
        Toast.success('Client scored');
    } catch (e) { Toast.error('Scoring failed: ' + e.message); }
}

async function quickReport(clientId) {
    try {
        Toast.info('Generating report...');
        const blob = await API.blob('POST', `/clients/${clientId}/report`);
        downloadBlob(blob, `report_${clientId}.docx`);
        Toast.success('Report downloaded');
    } catch (e) { Toast.error('Report failed: ' + e.message); }
}

async function viewActivity(clientId) {
    const el = document.getElementById('detailResult');
    if (!el) return;
    try {
        const res  = await API.get(`/clients/${clientId}/activity`);
        const acts = res.activities || [];
        el.innerHTML = `
            <div class="divider"></div>
            <div class="font-semibold mb-2">Activity (${acts.length})</div>
            <div style="max-height:220px;overflow-y:auto">
                ${acts.length
                    ? acts.map(a => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:12px;display:flex;gap:8px">
                        <span class="text-muted" style="flex-shrink:0;width:110px">${formatDateTime(a.timestamp)}</span>
                        <span class="badge badge-stage">${escapeHtml(a.type)}</span>
                        <span class="text-secondary">${escapeHtml(a.description)}</span>
                      </div>`).join('')
                    : '<div class="text-muted text-sm">No activity yet</div>'}
            </div>`;
    } catch (e) { Toast.error('Failed to load activity'); }
}

async function viewAudit(clientId) {
    const el = document.getElementById('detailResult');
    if (!el) return;
    try {
        const res     = await API.get(`/clients/${clientId}/audit`);
        const history = res.history || [];
        el.innerHTML = `
            <div class="divider"></div>
            <div class="font-semibold mb-2">Audit Trail (${history.length})</div>
            <div style="max-height:220px;overflow-y:auto">
                ${history.length
                    ? history.map(h => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:12px;display:flex;gap:8px">
                        <span class="text-muted" style="flex-shrink:0;width:110px">${formatDateTime(h.timestamp)}</span>
                        <span class="text-accent font-semibold">${escapeHtml(h.field)}</span>
                        <span class="text-muted">${escapeHtml(String(h.old_value||'—'))} → ${escapeHtml(String(h.new_value||'—'))}</span>
                      </div>`).join('')
                    : '<div class="text-muted text-sm">No changes recorded</div>'}
            </div>`;
    } catch (e) { Toast.error('Failed to load audit trail'); }
}

async function rollbackClient(clientId) {
    if (!confirm('Rollback the last change to this client?')) return;
    try {
        const res = await API.post(`/clients/${clientId}/rollback`);
        Toast.success(`Rolled back: ${res.field} ← ${res.rolled_back_to}`);
        closeModal('clientDetailModal');
        await loadClients();
    } catch (e) { Toast.error('Rollback failed: ' + e.message); }
}

async function createClient() {
    const nameEl = document.getElementById('newName');
    const name   = nameEl.value.trim();
    if (!name) { Toast.error('Name is required'); nameEl.focus(); return; }

    const btn = document.getElementById('createClientBtn');
    setLoading(btn, true);
    try {
        const data = {
            name,
            email:    document.getElementById('newEmail').value.trim()    || null,
            company:  document.getElementById('newCompany').value.trim()  || null,
            phone:    document.getElementById('newPhone').value.trim()    || null,
            service:  document.getElementById('newService').value.trim()  || null,
            priority: document.getElementById('newPriority').value,
            stage:    document.getElementById('newStage').value,
            notes:    document.getElementById('newNotes').value.trim()    || null
        };
        const res = await API.post('/clients', data);
        if (res.ok) {
            Toast.success(`Client created: ${res.client.client_id}`);
            closeModal('addClientModal');
            ['newName','newEmail','newCompany','newPhone','newService','newNotes']
                .forEach(id => { document.getElementById(id).value = ''; });
            await loadClients();
        } else {
            Toast.error(res.detail || 'Failed to create client');
        }
    } catch (e) { Toast.error(e.message); }
    finally { setLoading(btn, false); }
}

// ── Event listeners ────────────────────────────────────
document.getElementById('searchInput')
        .addEventListener('input', debounce(filterClients, 250));
document.getElementById('priorityFilter')
        .addEventListener('change', filterClients);
document.getElementById('stageFilter')
        .addEventListener('change', filterClients);
document.getElementById('archivedBtn')
        .addEventListener('click', toggleArchived);
document.getElementById('refreshBtn')
        .addEventListener('click', hardRefresh);
document.getElementById('newClientBtn')
        .addEventListener('click', () => openModal('addClientModal'));
document.getElementById('createClientBtn')
        .addEventListener('click', createClient);
document.getElementById('prevBtn')
        .addEventListener('click', () => changePage(-1));
document.getElementById('nextBtn')
        .addEventListener('click', () => changePage(1));

loadClients();