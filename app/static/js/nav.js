// ── ARIA Navigation ────────────────────────────────────
const Nav = (() => {

    const ROUTES = {
        dashboard: '/aria/dashboard',
        clients:   '/aria/clients',
        chat:      '/aria/chat',
        calendar:  '/aria/calendar',
        email:     '/aria/email',
        reports:   '/aria/reports',
        intel:     '/aria/intel',
        search:    '/aria/search',
        import:    '/aria/import'
    };

    // ── Single source of truth for all nav icons ───────
    const NAV_ICONS = {
        dashboard: `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="4" rx="1"/><rect x="14" y="10" width="7" height="7" rx="1"/><rect x="3" y="13" width="7" height="7" rx="1"/></svg>`,
        clients:   `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path stroke-linecap="round" stroke-linejoin="round" d="M23 21v-2a4 4 0 00-3-3.87"/><path stroke-linecap="round" stroke-linejoin="round" d="M16 3.13a4 4 0 010 7.75"/></svg>`,
        chat:      `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>`,
        calendar:  `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
        email:     `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline stroke-linecap="round" stroke-linejoin="round" points="22,6 12,13 2,6"/></svg>`,
        reports:   `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline stroke-linecap="round" stroke-linejoin="round" points="14,2 14,8 20,8"/><line stroke-linecap="round" x1="16" y1="13" x2="8" y2="13"/><line stroke-linecap="round" x1="16" y1="17" x2="8" y2="17"/><polyline stroke-linecap="round" points="10,9 9,9 8,9"/></svg>`,
        intel:     `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path stroke-linecap="round" d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`,
        search:    `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line stroke-linecap="round" x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
        import:    `<svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline stroke-linecap="round" stroke-linejoin="round" points="7,10 12,15 17,10"/><line stroke-linecap="round" x1="12" y1="15" x2="12" y2="3"/></svg>`
    };

    // ── Cached pipeline data ───────────────────────────
    let _pipelineCache   = null;
    let _pipelineCacheTs = 0;
    const _PIPELINE_TTL  = 30000; // 30s

    async function _getPipeline() {
        if (_pipelineCache && Date.now() - _pipelineCacheTs < _PIPELINE_TTL) {
            return _pipelineCache;
        }
        _pipelineCache   = await API.get('/pipeline');
        _pipelineCacheTs = Date.now();
        return _pipelineCache;
    }

    // ── Build sidebar HTML ─────────────────────────────
    function _buildSidebar() {
        const path = window.location.pathname;

        function navItem(key, label) {
            const href   = ROUTES[key] || '#';
            const active = path === href || path.startsWith(href + '/');
            return `<a href="${href}"
                       class="nav-item${active ? ' active' : ''}"
                       data-page="${key}"
                       aria-current="${active ? 'page' : 'false'}">
                ${NAV_ICONS[key] || ''}
                <span>${label}</span>
            </a>`;
        }

        return `
            <nav class="sidebar-nav" aria-label="Main navigation">
                <div class="nav-section">
                    <div class="nav-section-label">Main</div>
                    ${navItem('dashboard', 'Dashboard')}
                    ${navItem('clients',   'Clients')}
                    ${navItem('chat',      'Chat with ARIA')}
                </div>
                <div class="nav-section">
                    <div class="nav-section-label">Tools</div>
                    ${navItem('calendar', 'Calendar')}
                    ${navItem('email',    'Email')}
                    ${navItem('reports',  'Reports')}
                </div>
                <div class="nav-section">
                    <div class="nav-section-label">Intelligence</div>
                    ${navItem('intel',  'Intelligence')}
                    ${navItem('search', 'Smart Search')}
                </div>
                <div class="nav-section">
                    <div class="nav-section-label">Data</div>
                    ${navItem('import', 'Bulk Import')}
                </div>
            </nav>
            <div class="sidebar-footer">
                <div class="sidebar-stats" id="sidebarStats">
                    <div class="text-muted text-xs">Loading...</div>
                </div>
            </div>`;
    }

    // ── Build topbar HTML ──────────────────────────────
    function _buildTopbar() {
        return `<div class="topbar" role="banner">
            <div class="topbar-brand">
                <div class="topbar-logo" aria-hidden="true">
                    <svg width="20" height="20" viewBox="0 0 20 20"
                         fill="none" stroke="currentColor" stroke-width="1.5">
                        <circle cx="10" cy="10" r="3"/>
                        <path stroke-linecap="round"
                            d="M10 2v2m0 12v2M2 10h2m12 0h2
                               M4.93 4.93l1.41 1.41m7.32 7.32l1.41 1.41
                               M4.93 15.07l1.41-1.41m7.32-7.32l1.41-1.41"/>
                    </svg>
                </div>
                <div>
                    <div class="topbar-title">ARIA</div>
                    <div class="topbar-subtitle">AI Relationship Intelligence</div>
                </div>
            </div>
            <div class="topbar-right">
                <div class="status-badge" id="connectionStatus">
                    <span class="status-badge-dot"></span>
                    Connected
                </div>
                <button id="signOutBtn"
                    class="btn btn-secondary btn-sm"
                    aria-label="Sign out">
                    ${Icons.signOut}
                    Sign Out
                </button>
            </div>
        </div>`;
    }

    // ── Init — call once per page ──────────────────────
    function init() {
        if (!API.loadFromStorage()) {
            window.location.href = '/aria/';
            return false;
        }

        // Inject topbar
        const topbarEl = document.getElementById('aria-topbar');
        if (topbarEl) {
            topbarEl.outerHTML = _buildTopbar();
            // Attach sign-out after injection
            document.getElementById('signOutBtn')
                    ?.addEventListener('click', logout);
        }

        // Inject sidebar
        const sidebarEl = document.getElementById('aria-sidebar');
        if (sidebarEl) {
            sidebarEl.innerHTML = _buildSidebar();
        }

        loadSidebarStats();
        return true;
    }

    // ── Sidebar stats ──────────────────────────────────
    async function loadSidebarStats() {
        const el = document.getElementById('sidebarStats');
        if (!el) return;
        try {
            const pipeline = await _getPipeline();
            if (!pipeline.ok) throw new Error('unavailable');
            const total = pipeline.total_clients                  || 0;
            const high  = pipeline.high_priority_pending_count    || 0;
            const won   = pipeline.won_count                      || 0;
            el.innerHTML = `
                <div class="sidebar-stat">
                    <span>Total Clients</span>
                    <span class="sidebar-stat-value">${total}</span>
                </div>
                <div class="sidebar-stat">
                    <span>High Priority</span>
                    <span class="sidebar-stat-value text-error">${high}</span>
                </div>
                <div class="sidebar-stat">
                    <span>Won</span>
                    <span class="sidebar-stat-value text-success">${won}</span>
                </div>`;
        } catch {
            if (el) el.innerHTML = `<div class="text-muted text-xs">Stats unavailable</div>`;
        }
    }

    // ── Logout ─────────────────────────────────────────
    function logout() {
        sessionStorage.removeItem('aria_session');
        API.clear();
        window.location.href = '/aria/';
    }

    function go(page) {
        const href = ROUTES[page];
        if (href) window.location.href = href;
    }

    return { init, go, logout, loadSidebarStats, routes: ROUTES };
})();

window.Nav = Nav;