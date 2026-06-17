// ── ARIA Navigation ────────────────────────────────────
const Nav = (() => {

    // ── Route map ──────────────────────────────────────
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

    // ── Heroicon SVGs per nav item ─────────────────────
    const NAV_ICONS = {
        dashboard: `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="13" y="3" width="4" height="4" rx="1"/><rect x="13" y="10" width="4" height="7" rx="1"/><rect x="3" y="13" width="7" height="4" rx="1"/></svg>`,
        clients:   `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20H7m10 0v-2a4 4 0 00-4-4H7a4 4 0 00-4 4v2m14-10a4 4 0 11-8 0 4 4 0 018 0z"/></svg>`,
        chat:      `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>`,
        calendar:  `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>`,
        email:     `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>`,
        reports:   `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>`,
        intel:     `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path stroke-linecap="round" d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>`,
        search:    `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35"/></svg>`,
        import:    `<svg class="nav-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>`
    };

    // ── Sidebar HTML template ──────────────────────────
    function _buildSidebar() {
        const path = window.location.pathname;

        function navItem(key, label) {
            const href    = ROUTES[key] || '#';
            const active  = path === href || path.startsWith(href + '/');
            const icon    = NAV_ICONS[key] || '';
            return `
                <a href="${href}"
                   class="nav-item${active ? ' active' : ''}"
                   data-page="${key}"
                   aria-current="${active ? 'page' : 'false'}">
                    ${icon}
                    <span>${label}</span>
                </a>
            `;
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
                    <div class="text-muted text-xs">Loading stats...</div>
                </div>
            </div>
        `;
    }

    // ── Topbar HTML template ───────────────────────────
    function _buildTopbar() {
        const username = API.getUsername ? API.getUsername() : 'User';
        return `
            <div class="topbar" role="banner">
                <div class="topbar-brand">
                    <div class="topbar-logo" aria-hidden="true">
                        <svg width="20" height="20" viewBox="0 0 20 20"
                             fill="none" stroke="currentColor"
                             stroke-width="1.5">
                            <circle cx="10" cy="10" r="3"/>
                            <path stroke-linecap="round"
                                d="M10 2v2m0 12v2M2 10h2m12 0h2
                                   M4.93 4.93l1.41 1.41m7.32 7.32l1.41 1.41
                                   M4.93 15.07l1.41-1.41m7.32-7.32l1.41-1.41"/>
                        </svg>
                    </div>
                    <div>
                        <div class="topbar-title">ARIA</div>
                        <div class="topbar-subtitle">
                            AI Relationship Intelligence
                        </div>
                    </div>
                </div>
                <div class="topbar-right">
                    <div class="status-badge" id="connectionStatus">
                        <span class="status-badge-dot"></span>
                        Connected
                    </div>
                    <span class="text-sm text-muted hidden"
                          id="topbarUser">${escapeHtml(username)}</span>
                    <button
                        class="btn btn-secondary btn-sm"
                        onclick="Nav.logout()"
                        aria-label="Sign out">
                        ${Icons.signOut}
                        Sign Out
                    </button>
                </div>
            </div>
        `;
    }

    // ── Init ───────────────────────────────────────────

    function init() {
        // Check authentication
        if (!API.loadFromStorage()) {
            window.location.href = '/aria/';
            return false;
        }

        // Inject topbar if placeholder exists
        const topbarEl = document.getElementById('aria-topbar');
        if (topbarEl) {
            topbarEl.outerHTML = _buildTopbar();
        }

        // Inject sidebar if placeholder exists
        const sidebarEl = document.getElementById('aria-sidebar');
        if (sidebarEl) {
            sidebarEl.innerHTML = _buildSidebar();
        }

        // Load pipeline stats (non-blocking)
        loadSidebarStats();

        return true;
    }

    // ── Sidebar Stats ──────────────────────────────────

    async function loadSidebarStats() {
        const el = document.getElementById('sidebarStats');
        if (!el) return;

        try {
            const pipeline = await API.get('/pipeline');

            if (!pipeline.ok) {
                el.innerHTML = `
                    <div class="text-muted text-xs">
                        Stats unavailable
                    </div>
                `;
                return;
            }

            const total = pipeline.total_clients         || 0;
            const high  = pipeline.high_priority_pending_count || 0;
            const won   = pipeline.won_count             || 0;

            el.innerHTML = `
                <div class="sidebar-stat">
                    <span>Total Clients</span>
                    <span class="sidebar-stat-value">${total}</span>
                </div>
                <div class="sidebar-stat">
                    <span>High Priority</span>
                    <span class="sidebar-stat-value text-error">
                        ${high}
                    </span>
                </div>
                <div class="sidebar-stat">
                    <span>Won</span>
                    <span class="sidebar-stat-value text-success">
                        ${won}
                    </span>
                </div>
            `;
        } catch (e) {
            if (el) {
                el.innerHTML = `
                    <div class="text-muted text-xs">
                        Stats unavailable
                    </div>
                `;
            }
        }
    }

    // ── Navigation ─────────────────────────────────────

    function go(page) {
        const href = ROUTES[page];
        if (href) {
            window.location.href = href;
        }
    }

    function logout() {
        sessionStorage.removeItem('aria_session');
        API.clear();
        window.location.href = '/aria/';
    }

    return {
        init,
        go,
        logout,
        loadSidebarStats,
        routes: ROUTES
    };
})();

window.Nav = Nav;