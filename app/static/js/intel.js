// ── Intelligence ───────────────────────────────────────
Nav.init();

async function runIntel(endpoint, title) {
    const resultEl  = document.getElementById('intelResult');
    const titleEl   = document.getElementById('intelResultTitle');
    const contentEl = document.getElementById('intelResultContent');
    const timeEl    = document.getElementById('intelResultTime');

    titleEl.textContent = title;
    timeEl.textContent  = '';
    contentEl.innerHTML = loadingHTML('Running AI analysis...');
    resultEl.classList.remove('hidden');
    resultEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const start = Date.now();
        const res   = await API.get(`/${endpoint}`);
        timeEl.textContent  = `${((Date.now() - start) / 1000).toFixed(1)}s`;
        contentEl.innerHTML = prettyJson(res);
        Toast.success(`${title} complete`);
    } catch (e) {
        contentEl.innerHTML = `<div class="alert alert-error">${Icons.errorCircle} ${escapeHtml(e.message)}</div>`;
        Toast.error(`${title} failed: ${e.message}`);
    }
}

async function scoreClient() {
    const clientId = document.getElementById('scoreClientId').value.trim();
    if (!clientId) { Toast.error('Please enter a Client ID'); document.getElementById('scoreClientId').focus(); return; }

    const resultEl = document.getElementById('scoreResult');
    const btn      = document.getElementById('scoreBtn');
    resultEl.innerHTML = loadingHTML('Scoring client...');
    resultEl.classList.remove('hidden');
    setLoading(btn, true);

    try {
        const res = await API.get(`/clients/${clientId}/score`);
        const s   = res.score;
        resultEl.innerHTML = `
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
                        <span class="badge ${s.churn_risk==='High'?'badge-high':s.churn_risk==='Medium'?'badge-medium':'badge-low'}">${escapeHtml(s.churn_risk)}</span>
                    </div>
                    <div><div class="input-label">Opportunity</div>
                        <span class="badge badge-stage">${escapeHtml(s.opportunity_value)}</span></div>
                    <div><div class="input-label">Sentiment</div>
                        <span class="badge badge-stage">${escapeHtml(s.sentiment)}</span></div>
                    ${s.suggested_stage ? `<div><div class="input-label">Suggested Stage</div>
                        <span class="badge badge-stage">${escapeHtml(s.suggested_stage)}</span></div>` : ''}
                </div>
                <div class="input-label">Best Next Action</div>
                <div class="text-secondary mb-3">${escapeHtml(s.best_next_action)}</div>
                <div class="input-label">Summary</div>
                <div class="text-secondary text-sm mb-3" style="line-height:1.65">${escapeHtml(s.summary)}</div>
                ${(s.recommended_actions||[]).length ? `<div class="input-label">Recommended Actions</div>
                    <ul style="padding-left:18px;color:var(--text-secondary);font-size:13px;line-height:1.8">
                        ${s.recommended_actions.map(a => `<li>${escapeHtml(a)}</li>`).join('')}
                    </ul>` : ''}
                ${(s.talking_points||[]).length ? `<div class="input-label mt-3">Talking Points</div>
                    <ul style="padding-left:18px;color:var(--text-secondary);font-size:13px;line-height:1.8">
                        ${s.talking_points.map(p => `<li>${escapeHtml(p)}</li>`).join('')}
                    </ul>` : ''}
            </div>`;
        Toast.success('Client scored');
    } catch (e) {
        resultEl.innerHTML = `<div class="alert alert-error">${Icons.errorCircle} ${escapeHtml(e.message)}</div>`;
        Toast.error('Scoring failed: ' + e.message);
    } finally { setLoading(btn, false); }
}

// Intel card click delegation
document.getElementById('intelCards').addEventListener('click', e => {
    const card = e.target.closest('[data-endpoint]');
    if (card) runIntel(card.dataset.endpoint, card.dataset.title);
});

document.getElementById('scoreBtn').addEventListener('click', scoreClient);
document.getElementById('closeResultBtn').addEventListener('click', () => {
    document.getElementById('intelResult').classList.add('hidden');
});
document.getElementById('scoreClientId').addEventListener('keydown', e => {
    if (e.key === 'Enter') scoreClient();
});