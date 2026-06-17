// ── Dashboard ──────────────────────────────────────────

document.getElementById('dashboardDate').textContent =
    new Date().toLocaleDateString('en-US', {
        weekday: 'long', year: 'numeric',
        month: 'long',   day:  'numeric'
    });

function _showError(msg) {
    const el = document.getElementById('errorBanner');
    document.getElementById('errorMsg').textContent = msg || '';
    el.classList.toggle('hidden', !msg);
}

async function loadDashboard() {
    if (!Nav.init()) return;
    _showError(null);

    try {
        const [pipeline, followups, activities] = await Promise.all([
            API.get('/pipeline'),
            API.get('/followups/due'),
            API.get('/activities?limit=None')
        ]);

        // Stats
        document.getElementById('statTotal').textContent     = pipeline.total_clients                  || 0;
        document.getElementById('statHigh').textContent      = pipeline.high_priority_pending_count    || 0;
        document.getElementById('statWon').textContent       = pipeline.won_count                      || 0;
        document.getElementById('statFollowups').textContent = followups.count                         || 0;

        Nav.loadSidebarStats();

        // Pipeline stages
        const counts   = pipeline.stage_counts || {};
        const total    = Math.max(pipeline.total_clients || 1, 1);
        const stagesEl = document.getElementById('pipelineStages');

        stagesEl.innerHTML = Object.keys(counts).length
            ? Object.entries(counts).map(([stage, count]) => {
                const pct = Math.round(count / total * 100);
                return `<div class="flex items-center gap-3 mb-3">
                    <div class="text-secondary text-sm truncate" style="width:170px;flex-shrink:0">
                        ${escapeHtml(stage)}
                    </div>
                    <div class="progress-bar flex-1">
                        <div class="progress-fill" style="width:${pct}%"></div>
                    </div>
                    <div class="font-semibold text-sm text-accent"
                         style="width:28px;text-align:right;flex-shrink:0">
                        ${count}
                    </div>
                </div>`;
            }).join('')
            : emptyStateHTML('No clients yet', 'Add your first client to see pipeline data');

        // High priority
        const hpClients = pipeline.high_priority_pending_clients || [];
        document.getElementById('highPriorityList').innerHTML = hpClients.length
            ? hpClients.map(c => `
                <div class="flex items-center justify-between"
                     style="padding:9px 0;border-bottom:1px solid var(--border);cursor:pointer"
                     data-href="/aria/clients" role="button" tabindex="0">
                    <div style="min-width:0">
                        <div class="font-semibold text-sm truncate">${escapeHtml(c.name)}</div>
                        <div class="text-muted text-xs">
                            ${escapeHtml(c.company || '')}${c.company && c.stage ? ' · ' : ''}${escapeHtml(c.stage)}
                        </div>
                    </div>
                    ${c.next_follow_up
                        ? `<span class="text-xs text-error flex-shrink-0 ml-2">${escapeHtml(c.next_follow_up)}</span>`
                        : ''}
                </div>`).join('')
            : emptyStateHTML('No high priority clients pending', '', `<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`);

        // Follow-ups
        const fuClients = followups.clients || [];
        document.getElementById('followupsList').innerHTML = fuClients.length
            ? fuClients.map(c => `
                <div class="flex items-center justify-between"
                     style="padding:9px 0;border-bottom:1px solid var(--border)">
                    <div style="min-width:0">
                        <div class="font-semibold text-sm truncate">${escapeHtml(c.name)}</div>
                        <div class="text-muted text-xs">${escapeHtml(c.company || '')}</div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0 ml-2">
                        <span class="text-xs text-error font-semibold">
                            ${escapeHtml(c.next_follow_up || '')}
                        </span>
                        ${priorityBadge(c.priority)}
                    </div>
                </div>`).join('')
            : emptyStateHTML("No follow-ups due — you're all caught up!");

        // Recent activity
        const acts = activities.activities || [];
        document.getElementById('recentActivity').innerHTML = acts.length
            ? `<div class="table-wrapper" style="border:none;border-radius:0">
                <table class="table">
                    <thead><tr>
                        <th>Time</th><th>Client</th><th>Type</th>
                        <th>Description</th><th>Result</th>
                    </tr></thead>
                    <tbody>${acts.map(a => `
                        <tr>
                            <td class="text-muted text-xs">${formatDateTime(a.timestamp)}</td>
                            <td class="text-xs">${escapeHtml(a.client_id || '')}</td>
                            <td><span class="badge badge-stage">${escapeHtml(a.type || '')}</span></td>
                            <td class="text-secondary text-xs" style="max-width:280px">
                                <div class="truncate">${escapeHtml(a.description || '')}</div>
                            </td>
                            <td><span class="badge ${a.result === 'SUCCESS' ? 'badge-success' : 'badge-error'}">
                                ${escapeHtml(a.result || '')}
                            </span></td>
                        </tr>`).join('')}
                    </tbody>
                </table>
               </div>`
            : emptyStateHTML('No recent activity');

    } catch (e) {
        _showError('Failed to load dashboard: ' + e.message);
        Toast.error(e.message);
    }
}

// Navigate on clicking high priority rows
document.getElementById('highPriorityList')
        .addEventListener('click', e => {
    const row = e.target.closest('[data-href]');
    if (row) window.location.href = row.dataset.href;
});

document.getElementById('refreshBtn')
        .addEventListener('click', loadDashboard);

loadDashboard();