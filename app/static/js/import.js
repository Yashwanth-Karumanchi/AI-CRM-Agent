// ── Bulk Import ────────────────────────────────────────
Nav.init();

let selectedFile  = null;
let previewData   = null;
let importedCount = 0;
let totalToImport = 0;

function showPhase(phase) {
    ['phaseUpload','phasePreview','phaseImporting','phaseResults']
        .forEach(id => document.getElementById(id).classList.add('hidden'));
    document.getElementById(phase).classList.remove('hidden');
}

function resetImport() {
    selectedFile  = null;
    previewData   = null;
    importedCount = 0;
    totalToImport = 0;
    const fi = document.getElementById('fileInput');
    if (fi) fi.value = '';
    showPhase('phaseUpload');
}

// ── Drag & Drop ────────────────────────────────────────
const dropZone = document.getElementById('dropZone');
dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop',      e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
});

document.getElementById('fileInput').addEventListener('change', e => {
    if (e.target.files[0]) processFile(e.target.files[0]);
});

document.getElementById('browseBtn').addEventListener('click', () => {
    document.getElementById('fileInput').click();
});

function processFile(file) {
    const ext = file.name.toLowerCase().split('.').pop();
    if (!['xlsx','xls','csv'].includes(ext)) {
        Toast.error('File must be .xlsx, .xls, or .csv'); return;
    }
    if (file.size > 25 * 1024 * 1024) {
        Toast.error('File too large. Maximum 25 MB.'); return;
    }
    selectedFile = file;
    previewFile(file);
}

async function previewFile(file) {
    showPhase('phasePreview');
    document.getElementById('previewFilename').textContent = file.name;
    document.getElementById('previewTotal').textContent    = '...';
    document.getElementById('previewCols').textContent     = '...';
    document.getElementById('previewErrors').textContent   = '...';
    document.getElementById('detectedCols').innerHTML      = '';
    document.getElementById('previewTable').innerHTML      = '';
    document.getElementById('validationErrorsSection').classList.add('hidden');

    try {
        const formData = new FormData();
        formData.append('file', file);
        const rawRes = await API.upload('POST', '/clients/import/preview', formData);
        let data;
        try { data = await rawRes.json(); } catch { throw new Error('Invalid server response'); }
        if (!rawRes.ok) throw new Error(data.detail || 'Preview failed');
        previewData = data;
        renderPreview(data);
    } catch (e) {
        Toast.error('Preview failed: ' + e.message);
        resetImport();
    }
}

function renderPreview(data) {
    document.getElementById('previewTotal').textContent  = data.total_valid_rows ?? 0;
    document.getElementById('previewCols').textContent   = (data.detected_columns || []).length;
    document.getElementById('previewErrors').textContent = (data.validation_errors || []).length;

    document.getElementById('detectedCols').innerHTML =
        (data.detected_columns || []).map(c => `<span class="badge badge-stage">${escapeHtml(c)}</span>`).join('');

    const errSection = document.getElementById('validationErrorsSection');
    if ((data.validation_errors || []).length) {
        errSection.classList.remove('hidden');
        document.getElementById('validationErrors').innerHTML =
            data.validation_errors.map(e => `<div style="padding:2px 0">⚠ ${escapeHtml(e)}</div>`).join('');
    } else {
        errSection.classList.add('hidden');
    }

    const samples = data.sample_rows || [];
    if (samples.length) {
        const cols = Object.keys(samples[0]);
        document.getElementById('previewTable').innerHTML = `
            <thead><tr>${cols.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
            <tbody>${samples.map(row => `<tr>${cols.map(c =>
                `<td class="text-xs">${escapeHtml(String(row[c] ?? '—'))}</td>`
            ).join('')}</tr>`).join('')}</tbody>`;
    }

    const importBtn = document.getElementById('importBtn');
    importBtn.disabled = !data.ready_to_import;
    importBtn.textContent = `Import ${data.total_valid_rows ?? 0} Clients`;
    if (!data.ready_to_import) Toast.error('File has no valid rows. Check validation errors above.');
}

async function startImport() {
    if (!selectedFile) return;
    showPhase('phaseImporting');
    importedCount = 0;
    totalToImport = previewData?.total_valid_rows || 0;

    document.getElementById('importProgress').style.width = '0%';
    document.getElementById('liveCount').textContent      = '0';
    document.getElementById('liveTotal').textContent      = totalToImport;
    document.getElementById('liveStatus').textContent     = 'Starting...';
    document.getElementById('liveLog').innerHTML          = '';

    const checkDups = document.getElementById('checkDuplicates').checked;
    const formData  = new FormData();
    formData.append('file', selectedFile);

    try {
        const res = await API.upload('POST',
            `/clients/import/stream?check_duplicates=${checkDups}`, formData);
        if (!res.ok) {
            let detail = `Import failed: ${res.status}`;
            try { const err = await res.json(); detail = err.detail || detail; } catch {}
            throw new Error(detail);
        }

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer    = '';
        let finalData = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                try {
                    const event = JSON.parse(line.slice(6));
                    handleStreamEvent(event);
                    if (event.type === 'complete') finalData = event;
                } catch {}
            }
        }

        await sleep(400);
        if (finalData) {
            showImportResults(finalData);
        } else {
            Toast.error('Import stream ended unexpectedly');
            showPhase('phasePreview');
        }
    } catch (e) {
        Toast.error('Import failed: ' + e.message);
        showPhase('phasePreview');
    }
}

function handleStreamEvent(event) {
    const statusEl   = document.getElementById('liveStatus');
    const progressEl = document.getElementById('importProgress');
    const countEl    = document.getElementById('liveCount');
    const logEl      = document.getElementById('liveLog');

    switch (event.type) {
        case 'start':
            statusEl.textContent = event.message || 'Starting...';
            logEl.innerHTML += `<div style="color:var(--accent-primary)">▶ ${escapeHtml(event.message || '')}</div>`;
            break;
        case 'progress':
            statusEl.textContent = event.message || '';
            if (event.percent) progressEl.style.width = event.percent + '%';
            logEl.innerHTML += `<div style="color:var(--text-muted)">⟳ ${escapeHtml(event.message || '')}</div>`;
            logEl.scrollTop = logEl.scrollHeight;
            break;
        case 'client_added': {
            importedCount++;
            countEl.textContent = importedCount;
            const pct = Math.min(90, 20 + Math.round((importedCount / Math.max(totalToImport, 1)) * 70));
            progressEl.style.width = pct + '%';
            const c = event.client || {};
            logEl.innerHTML += `<div style="color:var(--success)">✓ ${escapeHtml(c.name || '?')}
                <span style="color:var(--text-muted);margin-left:6px">${escapeHtml(c.client_id || '')}</span>
                ${c.email ? `<span style="color:var(--text-muted);margin-left:6px">${escapeHtml(c.email)}</span>` : ''}
            </div>`;
            logEl.scrollTop = logEl.scrollHeight;
            break;
        }
        case 'client_skipped': {
            const s = event.client || {};
            logEl.innerHTML += `<div style="color:var(--warning)">⊘ ${escapeHtml(s.name || '?')} — skipped
                ${s.reason ? `<span style="opacity:0.7">(${escapeHtml(s.reason)})</span>` : ''}</div>`;
            logEl.scrollTop = logEl.scrollHeight;
            break;
        }
        case 'client_failed': {
            const f = event.client || {};
            logEl.innerHTML += `<div style="color:var(--error)">✗ ${escapeHtml(f.name || '?')} — failed
                ${f.error ? `<span style="opacity:0.7">(${escapeHtml(f.error)})</span>` : ''}</div>`;
            logEl.scrollTop = logEl.scrollHeight;
            break;
        }
        case 'complete':
            progressEl.style.width = '100%';
            statusEl.textContent   = event.message || 'Complete!';
            logEl.innerHTML += `<div style="color:var(--accent-primary);font-weight:600;margin-top:6px">🎉 ${escapeHtml(event.message || 'Import complete!')}</div>`;
            logEl.scrollTop = logEl.scrollHeight;
            break;
        case 'error':
            logEl.innerHTML += `<div style="color:var(--error)">✗ Error: ${escapeHtml(event.message || '')}</div>`;
            logEl.scrollTop = logEl.scrollHeight;
            break;
    }
}

function showImportResults(data) {
    showPhase('phaseResults');
    document.getElementById('resultImported').textContent = data.imported ?? 0;
    document.getElementById('resultSkipped').textContent  = data.skipped  ?? 0;
    document.getElementById('resultFailed').textContent   = data.failed   ?? 0;

    const imported = data.imported_clients || [];
    document.getElementById('importedList').innerHTML = imported.length ? `
        <div class="font-semibold text-success mb-2 mt-2">${Icons.check} Imported (${imported.length})</div>
        <div class="table-wrapper"><table class="table">
            <thead><tr><th>Name</th><th>Client ID</th><th>Email</th></tr></thead>
            <tbody>${imported.map(c => `<tr>
                <td class="font-semibold">${escapeHtml(c.name || '')}</td>
                <td class="text-accent text-xs">${escapeHtml(c.client_id || '')}</td>
                <td class="text-muted text-xs">${escapeHtml(c.email || '—')}</td>
            </tr>`).join('')}</tbody>
        </table></div>` : '';

    const skipped = data.skipped_clients || [];
    document.getElementById('skippedList').innerHTML = skipped.length ? `
        <div class="font-semibold text-warning mb-2 mt-4">⊘ Skipped — Duplicates (${skipped.length})</div>
        <div style="font-size:12px">${skipped.map(c =>
            `<div style="padding:3px 0;border-bottom:1px solid var(--border)">
                <span class="text-secondary">${escapeHtml(c.name || '')}</span>
                <span class="text-muted ml-2">— ${escapeHtml(c.reason || 'duplicate')}</span>
            </div>`).join('')}</div>` : '';

    const failed = data.failed_clients || [];
    document.getElementById('failedList').innerHTML = failed.length ? `
        <div class="font-semibold text-error mb-2 mt-4">✗ Failed (${failed.length})</div>
        <div style="font-size:12px">${failed.map(c =>
            `<div style="padding:3px 0;border-bottom:1px solid var(--border)">
                <span class="text-secondary">${escapeHtml(c.name || '')}</span>
                <span class="text-error ml-2">— ${escapeHtml(c.error || 'unknown error')}</span>
            </div>`).join('')}</div>` : '';

    Toast.success(`Import done! ${data.imported ?? 0} clients added.`);
}

// Buttons
document.getElementById('importBtn').addEventListener('click', startImport);
document.getElementById('cancelPreviewBtn').addEventListener('click', resetImport);
document.getElementById('resetBtn')?.addEventListener('click', resetImport);
document.querySelectorAll('[data-reset]').forEach(el =>
    el.addEventListener('click', resetImport));