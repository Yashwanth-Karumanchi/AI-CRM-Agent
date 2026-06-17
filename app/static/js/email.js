// ── Email ──────────────────────────────────────────────
Nav.init();

// Pre-fill client from URL param
const _clientParam = new URLSearchParams(window.location.search).get('client');
if (_clientParam) document.getElementById('aiClientId').value = _clientParam;

async function loadDrafts() {
    const container = document.getElementById('draftsList');
    container.innerHTML = loadingHTML('Loading drafts...');
    try {
        const res    = await API.get('/email/drafts?max_results=20');
        const drafts = res.drafts || [];
        if (!drafts.length) {
            container.innerHTML = emptyStateHTML('No drafts in Gmail',
                'Use AI Draft or Compose to create one', Icons.mail);
            return;
        }
        container.innerHTML = drafts.map(d => `
            <div class="flex items-center justify-between"
                 style="padding:11px 0;border-bottom:1px solid var(--border)">
                <div style="min-width:0;flex:1">
                    <div class="font-semibold text-sm truncate">${escapeHtml(d.subject || 'No subject')}</div>
                    <div class="text-muted text-xs mt-1">To: ${escapeHtml(d.to || '—')}</div>
                </div>
                <button class="btn btn-danger btn-sm ml-3"
                    data-action="delete" data-id="${escapeHtml(d.draft_id)}"
                    aria-label="Delete draft">${Icons.trash}</button>
            </div>`).join('');
    } catch (e) {
        container.innerHTML = `<div class="alert alert-error">${Icons.errorCircle} ${escapeHtml(e.message)}</div>`;
    }
}

// Draft list delegation
document.getElementById('draftsList').addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (btn?.dataset.action === 'delete') deleteDraft(btn.dataset.id);
});

async function deleteDraft(draftId) {
    if (!confirm('Delete this draft?')) return;
    try {
        await API.delete(`/email/draft/${draftId}`);
        Toast.success('Draft deleted');
        loadDrafts();
    } catch (e) { Toast.error('Delete failed: ' + e.message); }
}

async function aiDraftEmail(send) {
    const clientId    = document.getElementById('aiClientId').value.trim();
    const instruction = document.getElementById('aiInstruction').value.trim();
    const resultEl    = document.getElementById('aiResult');

    if (!clientId)    { Toast.error('Client ID is required');    document.getElementById('aiClientId').focus();    return; }
    if (!instruction) { Toast.error('Instructions are required'); document.getElementById('aiInstruction').focus(); return; }

    const draftBtn = document.getElementById('draftBtn');
    const sendBtn  = document.getElementById('aiSendBtn');
    setLoading(draftBtn, true);
    setLoading(sendBtn, true);
    resultEl.classList.add('hidden');

    try {
        const res = await API.post('/agent/draft-email', {
            client_id: clientId, instruction, send
        });
        if (res.ok) {
            resultEl.className = 'mt-3 alert alert-success';
            resultEl.innerHTML = `${Icons.check}
                <div>
                    <div class="font-semibold">${send ? 'Email sent' : 'Draft saved to Gmail'}</div>
                    <div class="text-xs mt-1">
                        <strong>Subject:</strong> ${escapeHtml(res.subject || '')}<br>
                        <div style="margin-top:4px;white-space:pre-wrap;max-height:80px;overflow:auto;font-size:11px;opacity:0.8">
                            ${escapeHtml((res.body || '').slice(0, 200))}${(res.body||'').length > 200 ? '...' : ''}
                        </div>
                    </div>
                </div>`;
            resultEl.classList.remove('hidden');
            if (!send) loadDrafts();
            Toast.success(send ? 'Email sent!' : 'Draft saved to Gmail');
        } else { throw new Error(res.detail || 'Failed'); }
    } catch (e) {
        resultEl.className = 'mt-3 alert alert-error';
        resultEl.innerHTML = `${Icons.errorCircle} <span>${escapeHtml(e.message)}</span>`;
        resultEl.classList.remove('hidden');
        Toast.error(e.message);
    } finally {
        setLoading(draftBtn, false);
        setLoading(sendBtn, false);
    }
}

async function sendCompose(action) {
    const clientId = document.getElementById('compClientId').value.trim();
    const subject  = document.getElementById('compSubject').value.trim();
    const body     = document.getElementById('compBody').value.trim();

    if (!clientId) { Toast.error('Client ID is required'); return; }
    if (!subject)  { Toast.error('Subject is required');   return; }
    if (!body)     { Toast.error('Email body is required'); return; }

    const btn = document.getElementById('compSendBtn');
    setLoading(btn, true);
    try {
        const res = await API.post(
            action === 'send' ? '/email/send' : '/email/draft',
            { client_id: clientId, subject, body,
              to: document.getElementById('compTo').value.trim() || undefined }
        );
        if (res.ok) {
            Toast.success(action === 'send' ? 'Email sent!' : 'Draft saved!');
            closeModal('composeModal');
            ['compClientId','compTo','compSubject','compBody']
                .forEach(id => { document.getElementById(id).value = ''; });
            if (action === 'draft') loadDrafts();
        } else { Toast.error(res.detail || 'Failed'); }
    } catch (e) { Toast.error(e.message); }
    finally { setLoading(btn, false); }
}

// Listeners
document.getElementById('refreshDraftsBtn').addEventListener('click', loadDrafts);
document.getElementById('composeBtn').addEventListener('click', () => openModal('composeModal'));
document.getElementById('draftBtn').addEventListener('click', () => aiDraftEmail(false));
document.getElementById('aiSendBtn').addEventListener('click', () => aiDraftEmail(true));
document.getElementById('compSendBtn').addEventListener('click', () => sendCompose('send'));
document.getElementById('compDraftBtn').addEventListener('click', () => sendCompose('draft'));
document.getElementById('cancelComposeBtn').addEventListener('click', () => closeModal('composeModal'));

loadDrafts();