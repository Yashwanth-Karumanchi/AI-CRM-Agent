// ── Central API Module ─────────────────────────────────
const API = (() => {
    let baseUrl = '';
    let authHeader = '';

    function init(url, username, password) {
        baseUrl = url.replace(/\/$/, '');
        authHeader = 'Basic ' + btoa(username + ':' + password);
        localStorage.setItem('aria_url', baseUrl);
        localStorage.setItem('aria_auth', authHeader);
    }

    function loadFromStorage() {
        baseUrl = localStorage.getItem('aria_url') || '';
        authHeader = localStorage.getItem('aria_auth') || '';
        return !!(baseUrl && authHeader);
    }

    function clear() {
        baseUrl = '';
        authHeader = '';
        localStorage.removeItem('aria_url');
        localStorage.removeItem('aria_auth');
    }

    async function request(method, path, body = null, isBlob = false) {
        if (!baseUrl || !authHeader) {
            throw new Error('Not authenticated');
        }

        const options = {
            method,
            headers: {
                'Authorization': authHeader,
                'Content-Type': 'application/json'
            }
        };

        if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
        }

        const res = await fetch(baseUrl + path, options);

        if (res.status === 401) {
            clear();
            window.location.href = '/aria/';
            throw new Error('Unauthorized');
        }

        if (isBlob) return res.blob();

        const data = await res.json();
        return data;
    }

    return {
        init,
        loadFromStorage,
        clear,
        get: (path) => request('GET', path),
        post: (path, body) => request('POST', path, body),
        put: (path, body) => request('PUT', path, body),
        delete: (path) => request('DELETE', path),
        blob: (method, path, body) => request(method, path, body, true),
        getBaseUrl: () => baseUrl
    };
})();

window.API = API;