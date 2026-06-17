// ── ARIA Central API Module ────────────────────────────
// All HTTP calls go through here.
// Handles auth, 401 redirect, file uploads, blobs.

const API = (() => {
    let _baseUrl = '';
    let _authHeader = '';

    // ── Init & Storage ─────────────────────────────────

    function init(url, username, password) {
        _baseUrl = url.replace(/\/$/, '');
        // btoa with URI encoding handles special chars
        _authHeader = 'Basic ' + btoa(
            unescape(encodeURIComponent(
                username + ':' + password
            ))
        );
        localStorage.setItem('aria_url', _baseUrl);
        localStorage.setItem('aria_auth', _authHeader);
        localStorage.setItem('aria_user', username);
    }

    function loadFromStorage() {
        _baseUrl     = localStorage.getItem('aria_url')  || '';
        _authHeader  = localStorage.getItem('aria_auth') || '';
        return !!(_baseUrl && _authHeader);
    }

    function clear() {
        _baseUrl = '';
        _authHeader = '';
        localStorage.removeItem('aria_url');
        localStorage.removeItem('aria_auth');
        localStorage.removeItem('aria_user');
    }

    function redirectToLogin() {
        clear();
        window.location.href = '/aria/';
    }

    function getUsername() {
        return localStorage.getItem('aria_user') || 'User';
    }

    // ── Core Request ───────────────────────────────────

    async function request(
        method,
        path,
        body = null,
        isBlob = false
    ) {
        if (!_baseUrl || !_authHeader) {
            redirectToLogin();
            throw new Error('Not authenticated');
        }

        const headers = {
            'Authorization': _authHeader,
            // Tells FastAPI this is XHR → suppress
            // browser's native Basic Auth popup on 401
            'X-Requested-With': 'XMLHttpRequest'
        };

        if (!isBlob && body !== null) {
            headers['Content-Type'] = 'application/json';
        }

        const options = {
            method,
            headers,
            credentials: 'omit'
        };

        if (body !== null && method !== 'GET') {
            options.body = JSON.stringify(body);
        }

        let res;
        try {
            res = await fetch(_baseUrl + path, options);
        } catch (err) {
            throw new Error(
                'Cannot reach server. Check your connection.'
            );
        }

        // Auth failure → go to login
        if (res.status === 401 || res.status === 403) {
            redirectToLogin();
            throw new Error(
                'Session expired. Please sign in again.'
            );
        }

        // Rate limit
        if (res.status === 429) {
            throw new Error(
                'Rate limit reached. Wait 30 seconds.'
            );
        }

        // Blob download
        if (isBlob) {
            if (!res.ok) {
                throw new Error(
                    `Download failed: ${res.status}`
                );
            }
            return res.blob();
        }

        // JSON response
        let data;
        try {
            data = await res.json();
        } catch {
            throw new Error(
                `Server returned invalid response (${res.status})`
            );
        }

        if (!res.ok) {
            const msg =
                data?.detail ||
                data?.message ||
                `Request failed: ${res.status}`;
            throw new Error(msg);
        }

        return data;
    }

    // ── File Upload (multipart) ────────────────────────

    async function upload(method, path, formData, signal) {
        if (!_baseUrl || !_authHeader) {
            redirectToLogin();
            throw new Error('Not authenticated');
        }

        let res;
        try {
            res = await fetch(_baseUrl + path, {
                method,
                headers: {
                    'Authorization': _authHeader,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'omit',
                body: formData,
                signal  // allows AbortController timeout
            });
        } catch (err) {
            if (err.name === 'AbortError') {
                throw new Error(
                    'Upload timed out. Please try again.'
                );
            }
            throw new Error('Network error during upload');
        }

        if (res.status === 401 || res.status === 403) {
            redirectToLogin();
            throw new Error('Session expired');
        }

        if (!res.ok) {
            let detail = `Upload failed: ${res.status}`;
            try {
                const err = await res.json();
                detail = err.detail || detail;
            } catch { /* ignore */ }
            throw new Error(detail);
        }

        return res;
    }

    // ── Streaming (SSE) ────────────────────────────────

    async function stream(method, path, formData, signal) {
        if (!_baseUrl || !_authHeader) {
            redirectToLogin();
            throw new Error('Not authenticated');
        }

        const res = await fetch(_baseUrl + path, {
            method,
            headers: {
                'Authorization': _authHeader,
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'omit',
            body: formData,
            signal
        });

        if (res.status === 401 || res.status === 403) {
            redirectToLogin();
            throw new Error('Session expired');
        }

        if (!res.ok) {
            let detail = `Stream failed: ${res.status}`;
            try {
                const err = await res.json();
                detail = err.detail || detail;
            } catch { /* ignore */ }
            throw new Error(detail);
        }

        return res;
    }

    // ── Public API ─────────────────────────────────────

    return {
        init,
        loadFromStorage,
        clear,
        redirectToLogin,
        getUsername,

        get:    (path)        => request('GET',    path),
        post:   (path, body)  => request('POST',   path, body),
        put:    (path, body)  => request('PUT',    path, body),
        patch:  (path, body)  => request('PATCH',  path, body),
        delete: (path)        => request('DELETE', path),

        // File downloads
        blob: (method, path, body) =>
            request(method, path, body, true),

        // Multipart file upload
        upload,

        // SSE streaming (returns raw Response)
        stream,

        getBaseUrl:    () => _baseUrl,
        getAuthHeader: () => _authHeader,
        isAuthenticated: () => !!(_baseUrl && _authHeader)
    };
})();

window.API = API;