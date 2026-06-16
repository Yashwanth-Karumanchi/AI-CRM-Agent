// ── Navigation ─────────────────────────────────────────
const Nav = (() => {
    const pages = {
        'dashboard': '/aria/dashboard',
        'clients': '/aria/clients',
        'chat': '/aria/chat',
        'calendar': '/aria/calendar',
        'email': '/aria/email',
        'reports': '/aria/reports',
        'intel': '/aria/intel',
        'search': '/aria/search'
    };

    function init() {
        if (!API.loadFromStorage()) {
            window.location.href = '/aria/';
            return false;
        }
        highlightActive();
        loadSidebarStats();
        return true;
    }

    function go(page) {
        window.location.href = pages[page] || '/aria/dashboard';
    }

    function highlightActive() {
        const path = window.location.pathname;
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.page &&
                path.includes(item.dataset.page)) {
                item.classList.add('active');
            }
        });
    }

    async function loadSidebarStats() {
        try {
            const pipeline = await API.get('/pipeline');
            const el = document.getElementById('sidebarStats');
            if (el && pipeline.ok) {
                el.innerHTML = `
                    <div class="sidebar-stat">
                        <span>Total</span>
                        <span class="sidebar-stat-value">
                            ${pipeline.total_clients || 0}
                        </span>
                    </div>
                    <div class="sidebar-stat">
                        <span>High Priority</span>
                        <span class="sidebar-stat-value text-error">
                            ${pipeline.high_priority_pending_count || 0}
                        </span>
                    </div>
                    <div class="sidebar-stat">
                        <span>Won</span>
                        <span class="sidebar-stat-value text-success">
                            ${pipeline.won_count || 0}
                        </span>
                    </div>
                `;
            }
        } catch (e) {
            console.error('Sidebar stats failed:', e);
        }
    }

    return { init, go, loadSidebarStats };
})();

window.Nav = Nav;