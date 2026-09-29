// MMP DUB Chromium Extension content script
// Persistent Tampermonkey-lite panel + autofill + custom userscript runner.
(function () {
  if (window.__MMP_DUB_CHROMIUM_CONTENT__) return;
  window.__MMP_DUB_CHROMIUM_CONTENT__ = true;

  const DEFAULT_SCRIPT = `// MMP built-in userscript\n// Runs on every DUB Browser page.\n// Helpers: GM_getValue, GM_setValue, GM_deleteValue, GM_addStyle, GM_xmlhttpRequest, GM_log, unsafeWindow.\n\nGM_addStyle(\`\n  /* Your CSS here */\n\`);\n\nGM_log('userscript loaded on', location.href);\n`;

  const defaults = {
    enabled: true,
    customScript: DEFAULT_SCRIPT,
    autofillEnabled: false,
    login: '',
    password: '',
    lastStatus: 'Ready.'
  };

  function storageGet(keys) {
    return new Promise(resolve => chrome.storage.local.get(keys, v => resolve(v || {})));
  }
  function storageSet(obj) {
    return new Promise(resolve => chrome.storage.local.set(obj, resolve));
  }

  function addCss(css) {
    if (document.getElementById('mmp-dub-style')) return;
    const st = document.createElement('style');
    st.id = 'mmp-dub-style';
    st.textContent = css;
    (document.head || document.documentElement).appendChild(st);
  }

  addCss(`
    #mmp-dub-fab, #mmp-dub-panel, #mmp-dub-panel * { box-sizing: border-box; font-family: Inter, Segoe UI, Arial, sans-serif !important; }
    #mmp-dub-fab { position: fixed; right: 18px; bottom: 18px; z-index: 2147483647; width: 42px; height: 42px; border-radius: 50%; border: 1px solid rgba(255,255,255,.18); background: linear-gradient(135deg,#7c5cfc,#9b7cff); color: #fff; font-weight: 900; box-shadow: 0 14px 34px rgba(0,0,0,.38), 0 0 24px rgba(124,92,252,.28); cursor: pointer; }
    #mmp-dub-panel { position: fixed; right: 18px; bottom: 68px; width: 420px; max-width: calc(100vw - 36px); max-height: calc(100vh - 92px); overflow: auto; z-index: 2147483647; color: rgba(255,255,255,.9); background: rgba(8,8,12,.95); border: 1px solid rgba(255,255,255,.12); border-radius: 16px; box-shadow: 0 22px 70px rgba(0,0,0,.62); backdrop-filter: blur(18px) saturate(120%); padding: 14px; }
    #mmp-dub-panel.hidden { display: none; }
    #mmp-dub-panel .mmp-row { display:flex; align-items:center; justify-content:space-between; gap:10px; margin: 9px 0; }
    #mmp-dub-panel .mmp-title { font-weight:900; font-size:14px; letter-spacing:-.02em; }
    #mmp-dub-panel .mmp-sub { color:rgba(255,255,255,.48); font-size:11px; line-height:1.35; margin-top:3px; }
    #mmp-dub-panel .mmp-label { font-size:11px; color:rgba(255,255,255,.55); font-weight:800; text-transform:uppercase; letter-spacing:.08em; margin:12px 0 6px; }
    #mmp-dub-panel input, #mmp-dub-panel textarea { width:100%; border-radius:10px; border:1px solid rgba(255,255,255,.10); background:rgba(255,255,255,.055); color:#fff; outline:none; padding:9px 10px; font-size:12px; }
    #mmp-dub-panel textarea { min-height:220px; resize:vertical; font-family: Consolas, monospace !important; font-size:11px; line-height:1.45; }
    #mmp-dub-panel .mmp-btn { border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.07); color:#fff; border-radius:10px; padding:8px 10px; font-size:12px; font-weight:800; cursor:pointer; }
    #mmp-dub-panel .mmp-btn.primary { background:#7c5cfc; border-color:#7c5cfc; }
    #mmp-dub-panel .mmp-btn.danger { color:#ff9a9a; background:rgba(239,68,68,.10); border-color:rgba(239,68,68,.22); }
    #mmp-dub-panel .mmp-toggle { display:flex; gap:8px; align-items:center; font-size:12px; color:rgba(255,255,255,.78); }
    #mmp-dub-panel .mmp-toggle input { width:auto !important; }
    #mmp-dub-panel .mmp-status { font-size:11px; color:rgba(255,255,255,.55); white-space:pre-wrap; max-height:90px; overflow:auto; }
  `);

  function setInputValue(input, value) {
    if (!input || !value) return false;
    try {
      input.focus();
      const proto = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      if (setter) setter.call(input, value); else input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    } catch (_) { return false; }
  }

  function visibleInputs() {
    return Array.from(document.querySelectorAll('input')).filter(i => {
      const r = i.getBoundingClientRect();
      const cs = getComputedStyle(i);
      return r.width > 1 && r.height > 1 && cs.display !== 'none' && cs.visibility !== 'hidden' && !i.disabled && !i.readOnly;
    });
  }

  function findLoginInputs() {
    const inputs = visibleInputs();
    const pass = inputs.find(i => (i.type || '').toLowerCase() === 'password');
    const user = inputs.find(i => /login|user|email|mail|name|логин|почт/i.test([i.name, i.id, i.placeholder, i.autocomplete].join(' ')))
      || (pass ? inputs.slice(0, inputs.indexOf(pass)).reverse().find(i => ['text','email','tel',''].includes((i.type || '').toLowerCase())) : null)
      || inputs.find(i => ['text','email','tel',''].includes((i.type || '').toLowerCase()));
    return { user, pass };
  }

  async function autofillLogin() {
    const cfg = Object.assign({}, defaults, await storageGet(Object.keys(defaults)));
    if (!cfg.autofillEnabled) return 'Autofill disabled';
    if (!cfg.login && !cfg.password) return 'No saved login/password';
    const found = findLoginInputs();
    const u = setInputValue(found.user, cfg.login);
    const p = setInputValue(found.pass, cfg.password);
    const msg = `Autofill: login ${u ? 'ok' : 'not found'}, password ${p ? 'ok' : 'not found'}`;
    await storageSet({ lastStatus: msg });
    return msg;
  }

  // GM_xmlhttpRequest bridge: page -> content -> background -> content -> page
  window.addEventListener('message', (ev) => {
    const m = ev.data;
    if (!m || !m.__mmp_gm_xhr || !m.details) return;
    chrome.runtime.sendMessage({ type: 'GM_XHR', url: m.details.url, method: m.details.method, headers: m.details.headers, body: m.details.data || m.details.body }, (res) => {
      window.postMessage({ __mmp_gm_xhr_result: true, id: m.id, ok: !!(res && res.ok), response: res || { ok:false, error:'no response' } }, '*');
    });
  });
  window.addEventListener('message', (ev) => {
    const m = ev.data;
    if (!m || !m.__mmp_gm_download || !m.details) return;
    chrome.runtime.sendMessage({ type: 'GM_DOWNLOAD', details: m.details }, (res) => {
      window.postMessage({ __mmp_gm_download_result: true, id: m.id, ok: !!(res && res.ok), response: res || { ok:false, error:'no response' } }, '*');
    });
  });

  async function runUserScript(reason) {
    const cfg = Object.assign({}, defaults, await storageGet(Object.keys(defaults)));
    if (!cfg.enabled) return 'Userscript disabled';
    const code = cfg.customScript || DEFAULT_SCRIPT;
    const injected = document.createElement('script');
    injected.textContent = `
(function(){
  const CODE = ${JSON.stringify(code)};
  function GM_addStyle(css){ const s=document.createElement('style'); s.textContent=css; (document.head||document.documentElement).appendChild(s); return s; }
  function GM_getValue(k,d){ try{ const v=localStorage.getItem('mmp_gm_'+k); return v===null?d:JSON.parse(v); }catch(e){ return d; } }
  function GM_setValue(k,v){ try{ localStorage.setItem('mmp_gm_'+k, JSON.stringify(v)); }catch(e){} }
  function GM_deleteValue(k){ try{ localStorage.removeItem('mmp_gm_'+k); }catch(e){} }
  function GM_log(){ console.log.apply(console, ['[MMP GM]'].concat(Array.from(arguments))); }
  function GM_xmlhttpRequest(details){
    const id=Math.random().toString(36).slice(2);
    window.__mmp_gm_callbacks = window.__mmp_gm_callbacks || {};
    window.__mmp_gm_callbacks[id] = { onload: details.onload || function(){}, onerror: details.onerror || function(){} };
    window.postMessage({__mmp_gm_xhr:true, id, details}, '*');
  }
  function GM_download(details, name){
    const opts = typeof details === 'string' ? { url: details, name: name || '' } : (details || {});
    const id=Math.random().toString(36).slice(2);
    window.__mmp_gm_download_callbacks = window.__mmp_gm_download_callbacks || {};
    window.__mmp_gm_download_callbacks[id] = { onload: opts.onload || opts.oncomplete || function(){}, onerror: opts.onerror || function(){} };
    window.postMessage({__mmp_gm_download:true, id, details: opts}, '*');
  }
  function GM_notification(details, title, image, onclick){
    const opts = typeof details === 'string' ? { text: details, title: title || 'MMP DUB', image, onclick } : (details || {});
    try {
      if (window.Notification && Notification.permission === 'granted') {
        const n = new Notification(opts.title || 'MMP DUB', { body: opts.text || opts.body || '', icon: opts.image || opts.icon || '' });
        n.onclick = opts.onclick || function(){};
      } else if (window.Notification && Notification.permission !== 'denied') {
        Notification.requestPermission().then(p => { if (p === 'granted') GM_notification(opts); });
      } else {
        console.log('[MMP Notification]', opts.title || 'MMP DUB', opts.text || opts.body || '');
      }
    } catch(e) { console.log('[MMP Notification]', opts.title || 'MMP DUB', opts.text || opts.body || ''); }
  }
  // Tampermonkey scripts in the wild use both spellings. Support both.
  const GM_xmlHttpRequest = GM_xmlhttpRequest;
  const GM_info = {
    scriptHandler: 'MMP DUB Userscripts',
    version: '1.0.0',
    script: { name: 'MMP custom DUB userscript', version: '1.0.0', namespace: 'mmp-dub' },
    platform: { browserName: 'Chromium/WebView', arch: 'x64' }
  };
  const GM = { info: GM_info, getValue: GM_getValue, setValue: GM_setValue, deleteValue: GM_deleteValue, addStyle: GM_addStyle, xmlHttpRequest: GM_xmlhttpRequest, xmlhttpRequest: GM_xmlhttpRequest, download: GM_download, notification: GM_notification, log: GM_log };
  if(!window.__mmp_gm_result_listener){
    window.__mmp_gm_result_listener = true;
    window.addEventListener('message', function(ev){
      const m=ev.data;
      if(m && m.__mmp_gm_xhr_result){
        const cb=window.__mmp_gm_callbacks && window.__mmp_gm_callbacks[m.id];
        if(cb){ try{ (m.ok ? cb.onload : cb.onerror)(m.response); }catch(e){ console.error(e); } delete window.__mmp_gm_callbacks[m.id]; }
      }
      if(m && m.__mmp_gm_download_result){
        const cb=window.__mmp_gm_download_callbacks && window.__mmp_gm_download_callbacks[m.id];
        if(cb){ try{ (m.ok ? cb.onload : cb.onerror)(m.response); }catch(e){ console.error(e); } delete window.__mmp_gm_download_callbacks[m.id]; }
      }
    });
  }
  try{ new Function('GM_getValue','GM_setValue','GM_deleteValue','GM_addStyle','GM_xmlhttpRequest','GM_xmlHttpRequest','GM_download','GM_notification','GM_info','GM','GM_log','unsafeWindow', CODE + '\n//# sourceURL=mmp-custom-dub-userscript.user.js')(GM_getValue,GM_setValue,GM_deleteValue,GM_addStyle,GM_xmlhttpRequest,GM_xmlHttpRequest,GM_download,GM_notification,GM_info,GM,GM_log,window); }
  catch(e){ console.error('[MMP DUB Userscript] failed:', e); }
})();`;
    (document.head || document.documentElement).appendChild(injected);
    injected.remove();
    const msg = 'Userscript injected: ' + reason + ' @ ' + new Date().toLocaleTimeString();
    await storageSet({ lastStatus: msg });
    return msg;
  }

  async function buildPanel() {
    if (document.getElementById('mmp-dub-fab')) return;
    const cfg = Object.assign({}, defaults, await storageGet(Object.keys(defaults)));
    const fab = document.createElement('button');
    fab.id = 'mmp-dub-fab';
    fab.textContent = ':3';
    fab.title = 'MMP DUB userscripts';
    const panel = document.createElement('div');
    panel.id = 'mmp-dub-panel';
    panel.className = 'hidden';
    panel.innerHTML = `
      <div class="mmp-row"><div><div class="mmp-title">MMP DUB Userscripts</div><div class="mmp-sub">Persistent Chromium extension mode. Survives login/navigation.</div></div><button class="mmp-btn" id="mmp-close">×</button></div>
      <label class="mmp-toggle"><input type="checkbox" id="mmp-enable"> Enable custom userscript</label>
      <label class="mmp-toggle"><input type="checkbox" id="mmp-login-enable"> Autofill login form</label>
      <div class="mmp-label">Login autofill</div><input id="mmp-login" placeholder="login / email"><div style="height:6px"></div><input id="mmp-pass" type="password" placeholder="password">
      <div class="mmp-row"><button class="mmp-btn" id="mmp-fill">Fill now</button><button class="mmp-btn" id="mmp-save-login">Save login</button><button class="mmp-btn danger" id="mmp-clear-login">Clear</button></div>
      <div class="mmp-label">Custom userscript</div><textarea id="mmp-code"></textarea>
      <div class="mmp-row"><button class="mmp-btn primary" id="mmp-run">Save & Run</button><button class="mmp-btn" id="mmp-reset">Reset example</button></div>
      <div class="mmp-label">Status</div><div class="mmp-status" id="mmp-status"></div>`;
    document.documentElement.appendChild(fab);
    document.documentElement.appendChild(panel);
    const $ = (id) => panel.querySelector(id);
    $('#mmp-enable').checked = !!cfg.enabled;
    $('#mmp-login-enable').checked = !!cfg.autofillEnabled;
    $('#mmp-login').value = cfg.login || '';
    $('#mmp-pass').value = cfg.password || '';
    $('#mmp-code').value = cfg.customScript || DEFAULT_SCRIPT;
    $('#mmp-status').textContent = cfg.lastStatus || 'Ready.';
    fab.onclick = () => panel.classList.toggle('hidden');
    $('#mmp-close').onclick = () => panel.classList.add('hidden');
    $('#mmp-enable').onchange = async e => storageSet({ enabled: e.target.checked });
    $('#mmp-login-enable').onchange = async e => storageSet({ autofillEnabled: e.target.checked });
    $('#mmp-save-login').onclick = async () => { await storageSet({ login: $('#mmp-login').value, password: $('#mmp-pass').value }); $('#mmp-status').textContent = 'Login saved in DUB Chromium profile.'; };
    $('#mmp-clear-login').onclick = async () => { await storageSet({ login:'', password:'' }); $('#mmp-login').value=''; $('#mmp-pass').value=''; $('#mmp-status').textContent='Login cleared.'; };
    $('#mmp-fill').onclick = async () => { $('#mmp-status').textContent = await autofillLogin(); };
    $('#mmp-run').onclick = async () => { await storageSet({ customScript: $('#mmp-code').value, enabled: $('#mmp-enable').checked }); $('#mmp-status').textContent = await runUserScript('manual'); };
    $('#mmp-reset').onclick = async () => { $('#mmp-code').value = DEFAULT_SCRIPT; await storageSet({ customScript: DEFAULT_SCRIPT }); $('#mmp-status').textContent = 'Example restored.'; };
  }

  async function boot() {
    await buildPanel();
    setTimeout(async () => { await autofillLogin(); }, 350);
    setTimeout(async () => { await runUserScript('auto'); }, 550);
    [1000, 2200, 4200].forEach(ms => setTimeout(() => autofillLogin(), ms));
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once:true });
  else boot();
})();
