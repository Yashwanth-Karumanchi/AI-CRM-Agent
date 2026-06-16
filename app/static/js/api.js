// ── Central API Module ─────────────────────────────────
const API = (() => {
    let baseUrl = '';
    let authHeader = '';

    function init(url, username, password) {
        baseUrl = url.replace(/\/$/, '');
        authHeader = 'Basic ' + btoa(
            unescape(encodeURIComponent(username + ':' + password))
        );
        localStorage.setItem('aria_url', baseUrl);
        localStorage.setItem('aria_auth', authHeader);
        localStorage.setItem('aria_username', username);
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
        localStorage.removeItem('aria_username');
    }

    function redirectToLogin() {
        clear();
        window.location.href = '/aria/';
    }

    async function request(
        method, path, body = null, isBlob = false
    ) {
        if (!baseUrl || !authHeader) {
            redirectToLogin();
            throw new Error('Not authenticated');
        }

        const options = {
            method,
            headers: {
                'Authorization': authHeader,
                'Content-Type': 'application/json',
                // Prevent browser from showing native auth popup
                'X-Requested-With': 'XMLHttpRequest'
            },
            // Critical: never let browser handle auth challenges
            credentials: 'omit'
        };

        if (body && method !== 'GET') {
            options.body = JSON.stringify(body);
        }

        let res;
        try {
            res = await fetch(baseUrl + path, options);
        } catch (networkErr) {
            throw new Error(
                'Network error — is the server running?'
            );
        }

        if (res.status === 401 || res.status === 403) {
            redirectToLogin();
            throw new Error('Session expired — please log in again');
        }

        if (res.status === 429) {
            throw new Error(
                'Rate limit reached. Please wait 30 seconds.'
            );
        }

        if (isBlob) {
            if (!res.ok) {
                throw new Error(`Request failed: ${res.status}`);
            }
            return res.blob();
        }

        let data;
        try {
            data = await res.json();
        } catch {
            throw new Error(`Server error: ${res.status}`);
        }

        if (!res.ok) {
            throw new Error(
                data.detail || data.message ||
                `Request failed: ${res.status}`
            );
        }

        return data;
    }

    // Multipart form upload (no Content-Type header)
    async function upload(method, path, formData) {
        if (!baseUrl || !authHeader) {
            redirectToLogin();
            throw new Error('Not authenticated');
        }

        let res;
        try {
            res = await fetch(baseUrl + path, {
                method,
                headers: {
                    'Authorization': authHeader,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'omit',
                body: formData
            });
        } catch (networkErr) {
            throw new Error('Network error');
        }

        if (res.status === 401 || res.status === 403) {
            redirectToLogin();
            throw new Error('Session expired');
        }

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(
                err.detail || `Upload failed: ${res.status}`
            );
        }

        return res;
    }

    return {
        init,
        loadFromStorage,
        clear,
        redirectToLogin,
        get: (path) => request('GET', path),
        post: (path, body) => request('POST', path, body),
        put: (path, body) => request('PUT', path, body),
        delete: (path) => request('DELETE', path),
        blob: (method, path, body) =>
            request(method, path, body, true),
        upload,
        getBaseUrl: () => baseUrl,
        getAuthHeader: () => authHeader
    };
})();

window.API = API;