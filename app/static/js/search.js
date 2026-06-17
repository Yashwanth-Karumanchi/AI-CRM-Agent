// ── Smart Search ───────────────────────────────────────
Nav.init();

function setNL(q)     { document.getElementById('nlInput').value = q;     runNLSearch(); }
function setFilter(q) { document.getElementById('filterInput').value = q; runFilter();   }

function _showLoading(label) {
    document.getElementById('resultsTitle').textContent  = label;
    document.getElementById('resultsCount').textContent  = '';
    document.getElementById('resultsInterpretation').textContent = '';
    document.getElementById('resultsContent').innerHTML  = loadingHTML('AI is searching...');
    document.getElementById('searchResults').classList.remove('hidden');
}

function _showResults(title, clients, count, interpretation) {
    document.getElementById('resultsTitle').textContent = title;
    document.getElementById('resultsCount').textContent = `${count} match${count !== 1 ? 'es' : ''}`;
    document.getElementById('resultsInterpretation').textContent =
        interpretation ? `Interpreted as: ${interpretation}` : '';

    const container = document.getElementById('resultsContent');
    if (!clients.length) {
        container.innerHTML = `<div class="card">${emptyStateHTML('No matches found',
            'Try rephrasing your search or different keywords', Icons.search)}</div>`;
        return;
    }

    container.innerHTML = `
        <div class="table-wrapper">
            <table class="table">
                <thead><tr><th>Client</th><th>Company</th><th>Service</th><th>Priority</th><th>Stage</th><th>Follow-up</th></tr></thead>
                <tbody>${clients.map(c => `
                    <tr data-href="/aria/clients" style="cursor:pointer" title="View in Clients">
                        <td>
                            <div class="font-semibold">${escapeHtml(c.name || '')}</div>
                            <div class="text-muted text-xs mt-1">${escapeHtml(c.client_id || '')}</div>
                        </td>
                        <td class="text-secondary">${escapeHtml(c.company || '—')}</td>
                        <td class="text-xs text-secondary" style="max-width:140px">
                            <div class="truncate">${escapeHtml(c.service || '—')}</div>
                        </td>
                        <td>${priorityBadge(c.priority)}</td>
                        <td>${stageBadge(c.stage)}</td>
                        <td class="text-xs text-muted">${c.next_follow_up || '—'}</td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>`;

    // Row click navigation
    container.querySelectorAll('tr[data-href]').forEach(row => {
        row.addEventListener('click', () => window.location.href = row.dataset.href);
    });

    Toast.success(`Found ${count} client${count !== 1 ? 's' : ''}`);
}

async function runNLSearch() {
    const query = document.getElementById('nlInput').value.trim();
    if (!query) { Toast.error('Please enter a search query'); document.getElementById('nlInput').focus(); return; }

    const btn = document.getElementById('nlSearchBtn');
    setLoading(btn, true);
    _showLoading(`Searching: "${query}"`);
    try {
        const res = await API.post('/search', { query });
        _showResults(`Search: "${query}"`, res.matched_clients || [], res.total_matches || 0,
            res.search_interpretation || '');
    } catch (e) {
        Toast.error('Search failed: ' + e.message);
        document.getElementById('resultsContent').innerHTML =
            `<div class="alert alert-error">${Icons.errorCircle} ${escapeHtml(e.message)}</div>`;
    } finally { setLoading(btn, false); }
}

async function runFilter() {
    const criteria = document.getElementById('filterInput').value.trim();
    if (!criteria) { Toast.error('Please enter filter criteria'); document.getElementById('filterInput').focus(); return; }

    const btn = document.getElementById('filterBtn');
    setLoading(btn, true);
    _showLoading(`Filtering: "${criteria}"`);
    try {
        const res = await API.post('/search/filter', { criteria });
        _showResults(`Filter: "${criteria}"`, res.matched_clients || [], res.total_matches || 0,
            res.criteria_interpretation || '');
    } catch (e) {
        Toast.error('Filter failed: ' + e.message);
        document.getElementById('resultsContent').innerHTML =
            `<div class="alert alert-error">${Icons.errorCircle} ${escapeHtml(e.message)}</div>`;
    } finally { setLoading(btn, false); }
}

// Listeners
document.getElementById('nlSearchBtn').addEventListener('click', runNLSearch);
document.getElementById('filterBtn').addEventListener('click', runFilter);
document.getElementById('nlInput').addEventListener('keydown', e => { if (e.key === 'Enter') runNLSearch(); });
document.getElementById('filterInput').addEventListener('keydown', e => { if (e.key === 'Enter') runFilter(); });

// Quick example chips
document.querySelectorAll('[data-nl]').forEach(el =>
    el.addEventListener('click', () => setNL(el.dataset.nl)));
document.querySelectorAll('[data-filter]').forEach(el =>
    el.addEventListener('click', () => setFilter(el.dataset.filter)));