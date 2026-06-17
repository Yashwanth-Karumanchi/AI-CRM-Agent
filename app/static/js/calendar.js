// ── Calendar ───────────────────────────────────────────
Nav.init();

async function loadMeetings() {
    const days      = document.getElementById('daysFilter').value;
    const container = document.getElementById('meetingsList');
    container.innerHTML = loadingHTML('Loading meetings...');
    document.getElementById('errorBanner').classList.add('hidden');

    try {
        const res      = await API.get(`/meetings?days_ahead=${days}&max_results=50`);
        const meetings = res.meetings || [];

        if (!meetings.length) {
            container.innerHTML = `<div class="card">${emptyStateHTML('No upcoming meetings',
                'Schedule a meeting to get started', Icons.calendar)}</div>`;
            return;
        }

        container.innerHTML = meetings.map(m => {
            const start = new Date(m.start_time);
            const end   = new Date(m.end_time || m.start_time);
            const isPast = start < new Date();
            return `
            <div class="card mb-3" style="${isPast ? 'opacity:0.6' : ''}">
                <div class="card-body">
                    <div class="flex items-start justify-between gap-3">
                        <div style="flex:1;min-width:0">
                            <div class="font-semibold text-primary mb-1">${escapeHtml(m.title || 'Untitled')}</div>
                            <div class="flex items-center gap-3 text-xs text-muted flex-wrap">
                                <span>${Icons.calendar} ${formatDateTime(m.start_time)} — ${formatDateTime(m.end_time)}</span>
                                ${m.location ? `<span>${Icons.location} ${escapeHtml(m.location)}</span>` : ''}
                            </div>
                            ${m.description ? `<div class="text-secondary text-xs mt-2" style="line-height:1.6">${escapeHtml(m.description)}</div>` : ''}
                        </div>
                        <div class="flex gap-2 flex-shrink-0 flex-wrap">
                            ${m.calendar_link ? `<a href="${escapeHtml(m.calendar_link)}" target="_blank" class="btn btn-ghost btn-sm">${Icons.video} Join</a>` : ''}
                            <button class="btn btn-secondary btn-sm" data-action="notes" data-id="${escapeHtml(m.event_id)}">${Icons.notes} Notes</button>
                            <button class="btn btn-danger btn-sm" data-action="cancel" data-id="${escapeHtml(m.event_id)}">${Icons.x} Cancel</button>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join('');

    } catch (e) {
        document.getElementById('errorMsg').textContent = e.message;
        document.getElementById('errorBanner').classList.remove('hidden');
        container.innerHTML = `<div class="card">${emptyStateHTML('Failed to load meetings', e.message)}</div>`;
    }
}

async function scheduleMeeting() {
    const clientId = document.getElementById('meetClientId').value.trim();
    const startRaw = document.getElementById('meetStart').value;
    const endRaw   = document.getElementById('meetEnd').value;

    if (!clientId) { Toast.error('Please enter a Client ID'); return; }
    if (!startRaw) { Toast.error('Please select a start time'); return; }
    if (!endRaw)   { Toast.error('Please select an end time'); return; }

    const start = new Date(startRaw);
    const end   = new Date(endRaw);
    if (end <= start) { Toast.error('End time must be after start time'); return; }

    const btn = document.getElementById('scheduleBtn');
    setLoading(btn, true);
    try {
        const res = await API.post('/meetings', {
            client_id:    clientId,
            title:        document.getElementById('meetTitle').value.trim() || null,
            start_time:   start.toISOString(),
            end_time:     end.toISOString(),
            description:  document.getElementById('meetDesc').value.trim() || null,
            location:     document.getElementById('meetLocation').value.trim() || null,
            invite_client: document.getElementById('meetInvite').checked
        });
        if (res.ok) {
            Toast.success('Meeting scheduled');
            closeModal('scheduleMeetingModal');
            ['meetClientId','meetTitle','meetStart','meetEnd','meetLocation','meetDesc']
                .forEach(id => { document.getElementById(id).value = ''; });
            document.getElementById('meetInvite').checked = false;
            loadMeetings();
        }
    } catch (e) { Toast.error(e.message); }
    finally { setLoading(btn, false); }
}

function openNotesModal(eventId) {
    document.getElementById('notesEventId').value = eventId;
    document.getElementById('notesText').value    = '';
    openModal('notesModal');
}

async function saveNotes() {
    const eventId = document.getElementById('notesEventId').value;
    const notes   = document.getElementById('notesText').value.trim();
    if (!notes) { Toast.error('Notes cannot be empty'); return; }
    const btn = document.getElementById('saveNotesBtn');
    setLoading(btn, true);
    try {
        await API.post(`/meetings/${eventId}/notes`, { notes });
        Toast.success('Notes saved');
        closeModal('notesModal');
    } catch (e) { Toast.error(e.message); }
    finally { setLoading(btn, false); }
}

async function cancelMeeting(eventId) {
    if (!confirm('Cancel this meeting? It will be removed from your calendar.')) return;
    try {
        await API.delete(`/meetings/${eventId}?notify_attendees=true`);
        Toast.success('Meeting cancelled');
        loadMeetings();
    } catch (e) { Toast.error(e.message); }
}

// Event delegation for meeting cards
document.getElementById('meetingsList').addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const id     = btn.dataset.id;
    const action = btn.dataset.action;
    if (action === 'notes')  openNotesModal(id);
    if (action === 'cancel') cancelMeeting(id);
});

document.getElementById('daysFilter').addEventListener('change', loadMeetings);
document.getElementById('refreshBtn').addEventListener('click', loadMeetings);
document.getElementById('scheduleMeetingBtn').addEventListener('click', () => openModal('scheduleMeetingModal'));
document.getElementById('scheduleBtn').addEventListener('click', scheduleMeeting);
document.getElementById('cancelScheduleBtn').addEventListener('click', () => closeModal('scheduleMeetingModal'));
document.getElementById('saveNotesBtn').addEventListener('click', saveNotes);
document.getElementById('cancelNotesBtn').addEventListener('click', () => closeModal('notesModal'));

loadMeetings();