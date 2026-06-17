// ── ARIA Login ─────────────────────────────────────────
API.clear(); // clear any stale auth on login page

// Add spin keyframe dynamically (no CSS file on login)
const _spinStyle = document.createElement('style');
_spinStyle.textContent = '@keyframes spin{to{transform:rotate(360deg)}}';
document.head.appendChild(_spinStyle);

function showError(msg) {
    document.getElementById('loginErrorMsg').textContent = msg;
    document.getElementById('loginError').classList.remove('hidden');
}

function hideError() {
    document.getElementById('loginError').classList.add('hidden');
}

async function login() {
    const urlEl  = document.getElementById('loginUrl');
    const userEl = document.getElementById('loginUsername');
    const passEl = document.getElementById('loginPassword');
    const btn    = document.getElementById('loginBtn');

    const url      = urlEl.value.trim();
    const username = userEl.value.trim();
    const password = passEl.value;

    hideError();

    if (!url)      { showError('Please enter the API URL.');      urlEl.focus();  return; }
    if (!username) { showError('Please enter your username.');    userEl.focus(); return; }
    if (!password) { showError('Please enter your password.');    passEl.focus(); return; }

    btn.disabled      = true;
    btn._originalHTML = btn.innerHTML;
    btn.innerHTML     = `
        <div style="width:18px;height:18px;border:2px solid
             rgba(255,255,255,0.35);border-top-color:white;
             border-radius:50%;animation:spin 0.75s linear infinite">
        </div>
        Connecting...`;

    try {
        API.init(url, username, password);
        const res = await API.get('/health');
        if (res.ok) {
            window.location.href = '/aria/dashboard';
        } else {
            throw new Error('Health check failed');
        }
    } catch (e) {
        API.clear();
        passEl.value = '';
        const msg = e.message || '';

        if (msg.includes('401') || msg.includes('403') ||
            msg.includes('Session expired') || msg.includes('Unauthorized')) {
            showError('Incorrect username or password. Please try again.');
            passEl.focus();
        } else if (msg.includes('Network') || msg.includes('fetch') ||
                   msg.includes('reach')   || msg.includes('ERR_')) {
            showError('Cannot reach the server. Check the API URL and try again.');
            urlEl.focus();
        } else if (msg.includes('Rate limit')) {
            showError('Too many attempts. Please wait a moment.');
        } else if (msg.includes('Health check')) {
            showError('Server may be starting up — try again in 30 seconds.');
        } else {
            showError('Login failed: ' + msg);
        }

        btn.disabled  = false;
        btn.innerHTML = btn._originalHTML;
    }
}

// Attach listeners
document.getElementById('loginBtn')
        .addEventListener('click', login);

document.addEventListener('keydown', e => {
    if (e.key === 'Enter') login();
});