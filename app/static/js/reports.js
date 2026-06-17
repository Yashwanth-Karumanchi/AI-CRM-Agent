// ── Reports ────────────────────────────────────────────
Nav.init();

const REPORT_PATHS = {
    weekly:           '/reports/weekly',
    monthly:          '/reports/monthly',
    acquisition:      '/reports/acquisition',
    pipeline:         '/pipeline/report',
    'agent-activity': '/reports/agent-activity'
};

async function downloadReport(type, label) {
    Toast.info(`Generating ${label}...`);
    try {
        const blob = await API.blob('GET', REPORT_PATHS[type]);
        downloadBlob(blob, `${type}_report.docx`);
        Toast.success(`${label} downloaded`);
    } catch (e) { Toast.error(`${label} failed: ${e.message}`); }
}

async function downloadClientReport() {
    const clientId = document.getElementById('reportClientId').value.trim();
    if (!clientId) {
        Toast.error('Please enter a Client ID');
        document.getElementById('reportClientId').focus();
        return;
    }
    const btn = document.getElementById('clientReportBtn');
    setLoading(btn, true);
    Toast.info('Generating client report...');
    try {
        const blob = await API.blob('POST', `/clients/${clientId}/report`);
        downloadBlob(blob, `report_${clientId}.docx`);
        Toast.success('Client report downloaded');
    } catch (e) { Toast.error('Report failed: ' + e.message); }
    finally { setLoading(btn, false); }
}

// Report card click delegation
document.getElementById('reportCards').addEventListener('click', e => {
    const card = e.target.closest('[data-report]');
    if (card) downloadReport(card.dataset.report, card.dataset.label);
});

document.getElementById('clientReportBtn')
        .addEventListener('click', downloadClientReport);
document.getElementById('reportClientId')
        .addEventListener('keydown', e => { if (e.key === 'Enter') downloadClientReport(); });