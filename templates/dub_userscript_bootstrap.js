// Minimal Media Player Pro — DUB Browser userscript bootstrap
// Browser-assisted only: runs inside the visible DUB browser page. No backend extraction/downloader.
(function () {
  if (window.__MMP_DUB_USERSCRIPT_BOOTSTRAP__) return;
  window.__MMP_DUB_USERSCRIPT_BOOTSTRAP__ = true;

  const LS = {
    enabled: 'mmp_dub_userscript_enabled',
    custom: 'mmp_dub_custom_userscript',
    loginEnabled: 'mmp_dub_login_autofill_enabled',
    login: 'mmp_dub_login_value',
    pass: 'mmp_dub_password_value',
    lastRun: 'mmp_dub_last_run_status'
  };

  const DEFAULT_SCRIPT = `// MMP DUB Browser user script\n// Runs on the visible page, like a tiny built-in Tampermonkey.\n// Available helpers: GM_getValue, GM_setValue, GM_addStyle, unsafeWindow.\n\nGM_addStyle(\`\n  /* example: make video/player areas easier to click */\n  video { outline: 1px solid rgba(124,92,252,.25); }\n\`);\n\nconsole.log('[MMP Userscript] custom script is running on', location.href);\n`;

  function get(k, fallback = '') {
    try { const v = localStorage.getItem(k); return v === null ? fallback : v; } catch (_) { return fallback; }
  }
  function set(k, v) {
    try { localStorage.setItem(k, String(v)); } catch (_) {}
  }
  function bool(k, fallback = true) {
    const v = get(k, fallback ? '1' : '0');
    return v === '1' || v === 'true' || v === 'yes';
  }

  if (get(LS.custom, '') === '') set(LS.custom, DEFAULT_SCRIPT);
  if (get(LS.enabled, '') === '') set(LS.enabled, '1');

  function addStyle(css) {
    const st = document.createElement('style');
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
    return st;
  }

  addStyle(`
    #mmp-dub-panel, #mmp-dub-panel * { box-sizing: border-box; font-family: Inter, Segoe UI, Arial, sans-serif !important; }
    #mmp-dub-fab {
      position: fixed; right: 18px; bottom: 18px; z-index: 2147483647;
      width: 42px; height: 42px; border-radius: 50%; border: 1px solid rgba(255,255,255,.18);
      background: linear-gradient(135deg,#7c5cfc,#9b7cff); color: #fff; font-weight: 900;
      box-shadow: 0 14px 34px rgba(0,0,0,.38), 0 0 24px rgba(124,92,252,.28); cursor: pointer;
    }
    #mmp-dub-panel {
      position: fixed; right: 18px; bottom: 68px; width: 390px; max-width: calc(100vw - 36px);
      max-height: calc(100vh - 92px); overflow: auto; z-index: 2147483647; color: rgba(255,255,255,.9);
      background: rgba(8,8,12,.94); border: 1px solid rgba(255,255,255,.12); border-radius: 16px;
      box-shadow: 0 22px 70px rgba(0,0,0,.62); backdrop-filter: blur(18px) saturate(120%); padding: 14px;
    }
    #mmp-dub-panel.hidden { display: none; }
    .mmp-row { display:flex; align-items:center; justify-content:space-between; gap:10px; margin: 9px 0; }
    .mmp-title { font-weight:900; font-size:14px; letter-spacing:-.02em; }
    .mmp-sub { color:rgba(255,255,255,.48); font-size:11px; line-height:1.35; margin-top:3px; }
    .mmp-label { font-size:11px; color:rgba(255,255,255,.55); font-weight:800; text-transform:uppercase; letter-spacing:.08em; margin:12px 0 6px; }
    #mmp-dub-panel input, #mmp-dub-panel textarea {
      width:100%; border-radius:10px; border:1px solid rgba(255,255,255,.10); background:rgba(255,255,255,.055);
      color:#fff; outline:none; padding:9px 10px; font-size:12px;
    }
    #mmp-dub-panel textarea { min-height:180px; resize:vertical; font-family: Consolas, monospace !important; font-size:11px; line-height:1.45; }
    .mmp-btn { border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.07); color:#fff; border-radius:10px; padding:8px 10px; font-size:12px; font-weight:800; cursor:pointer; }
    .mmp-btn.primary { background:#7c5cfc; border-color:#7c5cfc; }
    .mmp-btn.danger { color:#ff9a9a; background:rgba(239,68,68,.10); border-color:rgba(239,68,68,.22); }
    .mmp-toggle { display:flex; gap:8px; align-items:center; font-size:12px; color:rgba(255,255,255,.78); }
    .mmp-toggle input { width:auto !important; }
    .mmp-status { font-size:11px; color:rgba(255,255,255,.50); white-space:pre-wrap; }
  `);

  function findLoginInputs() {
    const inputs = Array.from(document.querySelectorAll('input'));
    const visible = inputs.filter(i => {
      const r = i.getBoundingClientRect();
      return r.width > 1 && r.height > 1 && getComputedStyle(i).visibility !== 'hidden' && getComputedStyle(i).display !== 'none';
    });
    const user = visible.find(i => /login|user|email|name|mail|логин|почт/i.test([i.name, i.id, i.placeholder, i.autocomplete].join(' ')))
      || visible.find(i => ['text', 'email', 'tel', ''].includes((i.type || '').toLowerCase()));
    const pass = visible.find(i => (i.type || '').toLowerCase() === 'password');
    return { user, pass };
  }

  function setInputValue(input, value) {
    if (!input || !value) return false;
    input.focus();
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function autofillLogin() {
    if (!bool(LS.loginEnabled, false)) return 'Autofill disabled';
    const login = get(LS.login, '');
    const passVal = get(LS.pass, '');
    if (!login && !passVal) return 'No saved login/password in this DUB browser profile';
    const found = findLoginInputs();
    const u = setInputValue(found.user, login);
    const p = setInputValue(found.pass, passVal);
    return `Autofill: login ${u ? 'ok' : 'not found'}, password ${p ? 'ok' : 'not found'}`;
  }

  function runUserScript() {
    if (!bool(LS.enabled, true)) return 'Userscripts disabled';
    const code = get(LS.custom, DEFAULT_SCRIPT);
    function GM_xmlhttpRequest(details) {
      const method = details.method || 'GET';
      fetch(details.url, { method, headers: details.headers || {}, body: details.data || details.body || undefined, credentials: 'include' })
        .then(async r => {
          const responseText = await r.text();
          if (details.onload) details.onload({ status: r.status, statusText: r.statusText, responseText, finalUrl: r.url });
        })
        .catch(err => { if (details.onerror) details.onerror({ error: String(err) }); });
    }
    const GM_xmlHttpRequest = GM_xmlhttpRequest;
    const GM_info = {
      scriptHandler: 'MMP DUB Userscripts',
      version: '1.0.0',
      script: { name: 'MMP custom DUB userscript', version: '1.0.0', namespace: 'mmp-dub' },
      platform: { browserName: 'WebView2', arch: 'x64' }
    };
    const GM = {
      info: GM_info,
      getValue: (k, d) => get('mmp_gm_' + k, d),
      setValue: (k, v) => set('mmp_gm_' + k, v),
      addStyle,
      xmlHttpRequest: GM_xmlhttpRequest,
      xmlhttpRequest: GM_xmlhttpRequest
    };
    try {
      const fn = new Function('GM_getValue', 'GM_setValue', 'GM_addStyle', 'GM_xmlhttpRequest', 'GM_xmlHttpRequest', 'GM_info', 'GM', 'unsafeWindow', code + '\n//# sourceURL=mmp-dub-userscript.js');
      fn(GM.getValue, GM.setValue, GM.addStyle, GM_xmlhttpRequest, GM_xmlHttpRequest, GM_info, GM, window);
      set(LS.lastRun, 'OK: ' + new Date().toLocaleTimeString());
      return get(LS.lastRun);
    } catch (e) {
      const msg = 'ERROR: ' + (e && e.stack ? e.stack : e);
      console.error('[MMP Userscript]', e);
      set(LS.lastRun, msg);
      return msg;
    }
  }

  function buildPanel() {
    if (document.getElementById('mmp-dub-fab')) return;
    const fab = document.createElement('button');
    fab.id = 'mmp-dub-fab';
    fab.textContent = ':3';
    fab.title = 'MMP DUB userscripts';

    const panel = document.createElement('div');
    panel.id = 'mmp-dub-panel';
    panel.className = 'hidden';
    panel.innerHTML = `
      <div class="mmp-row">
        <div><div class="mmp-title">MMP DUB Userscripts</div><div class="mmp-sub">Built-in Tampermonkey-lite for this visible browser page.</div></div>
        <button class="mmp-btn" id="mmp-close">×</button>
      </div>
      <label class="mmp-toggle"><input type="checkbox" id="mmp-enable"> Enable custom userscript</label>
      <label class="mmp-toggle"><input type="checkbox" id="mmp-login-enable"> Autofill login form</label>
      <div class="mmp-label">Login autofill</div>
      <input id="mmp-login" placeholder="login / email (stored locally in this browser profile)">
      <div style="height:6px"></div>
      <input id="mmp-pass" type="password" placeholder="password (local profile storage)">
      <div class="mmp-row"><button class="mmp-btn" id="mmp-fill">Fill now</button><button class="mmp-btn" id="mmp-save-login">Save login</button><button class="mmp-btn danger" id="mmp-clear-login">Clear</button></div>
      <div class="mmp-label">Custom userscript</div>
      <textarea id="mmp-code"></textarea>
      <div class="mmp-row"><button class="mmp-btn primary" id="mmp-run">Save & Run</button><button class="mmp-btn" id="mmp-reset">Reset example</button></div>
      <div class="mmp-label">Status</div>
      <div class="mmp-status" id="mmp-status"></div>
    `;
    document.documentElement.appendChild(fab);
    document.documentElement.appendChild(panel);

    const $ = (id) => panel.querySelector(id);
    $('#mmp-enable').checked = bool(LS.enabled, true);
    $('#mmp-login-enable').checked = bool(LS.loginEnabled, false);
    $('#mmp-login').value = get(LS.login, '');
    $('#mmp-pass').value = get(LS.pass, '');
    $('#mmp-code').value = get(LS.custom, DEFAULT_SCRIPT);
    $('#mmp-status').textContent = get(LS.lastRun, 'Ready.');

    fab.onclick = () => panel.classList.toggle('hidden');
    $('#mmp-close').onclick = () => panel.classList.add('hidden');
    $('#mmp-enable').onchange = (e) => set(LS.enabled, e.target.checked ? '1' : '0');
    $('#mmp-login-enable').onchange = (e) => set(LS.loginEnabled, e.target.checked ? '1' : '0');
    $('#mmp-save-login').onclick = () => { set(LS.login, $('#mmp-login').value); set(LS.pass, $('#mmp-pass').value); $('#mmp-status').textContent = 'Login saved locally.'; };
    $('#mmp-clear-login').onclick = () => { set(LS.login, ''); set(LS.pass, ''); $('#mmp-login').value = ''; $('#mmp-pass').value = ''; $('#mmp-status').textContent = 'Login cleared.'; };
    $('#mmp-fill').onclick = () => { $('#mmp-status').textContent = autofillLogin(); };
    $('#mmp-run').onclick = () => { set(LS.custom, $('#mmp-code').value); $('#mmp-status').textContent = runUserScript(); };
    $('#mmp-reset').onclick = () => { $('#mmp-code').value = DEFAULT_SCRIPT; set(LS.custom, DEFAULT_SCRIPT); $('#mmp-status').textContent = 'Example restored.'; };
  }

  function boot() {
    buildPanel();
    const fillResult = autofillLogin();
    const runResult = runUserScript();
    console.log('[MMP DUB]', fillResult, runResult);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();

  // Some sites render login forms late. Try a few light retries; no heavy observer loop.
  [800, 1800, 3500].forEach(ms => setTimeout(() => { try { autofillLogin(); } catch (_) {} }, ms));
})();
