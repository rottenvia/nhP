(() => {
  if (window.__NOHOMO_DUB_HELPER_ACTIVE__) return;
  window.__NOHOMO_DUB_HELPER_ACTIVE__ = true;

  const state = window.__NOHOMO_DUB_CONTEXT__ || {};
  const css = `
    #nohomo-dub-helper {
      position: fixed;
      right: 18px;
      bottom: 22px;
      width: 330px;
      z-index: 2147483647;
      background: rgba(8, 8, 12, .94);
      color: #fff;
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 14px;
      box-shadow: 0 18px 48px rgba(0,0,0,.65);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      overflow: hidden;
      resize: both;
      backdrop-filter: blur(14px);
    }
    #nohomo-dub-helper * { box-sizing: border-box; }
    .ndh-head { padding: 13px 15px; border-bottom: 1px solid rgba(255,255,255,.08); display:flex; justify-content:space-between; gap:10px; align-items:center; }
    .ndh-title { font-size: 13px; font-weight: 900; letter-spacing:.02em; }
    .ndh-sub { color: rgba(255,255,255,.52); font-size: 11px; margin-top:2px; }
    .ndh-close { background:none; border:0; color:rgba(255,255,255,.55); font-size:20px; cursor:pointer; }
    .ndh-body { padding: 13px 15px 15px; display:flex; flex-direction:column; gap:10px; }
    .ndh-pill { border:1px solid rgba(124,92,252,.28); background:rgba(124,92,252,.12); color:#c4b5fd; border-radius:999px; padding:5px 9px; font-size:11px; font-weight:800; width:max-content; max-width:100%; }
    .ndh-text { color: rgba(255,255,255,.72); font-size:12px; line-height:1.45; }
    .ndh-row { display:flex; gap:8px; flex-wrap:wrap; }
    .ndh-btn { border:1px solid rgba(255,255,255,.10); background:rgba(255,255,255,.04); color:#fff; border-radius:8px; padding:8px 10px; font-size:12px; font-weight:800; cursor:pointer; }
    .ndh-btn.primary { background:#7c5cfc; border-color:#7c5cfc; }
    .ndh-log { max-height:120px; overflow:auto; color:rgba(255,255,255,.55); font-size:11px; line-height:1.35; border-top:1px solid rgba(255,255,255,.06); padding-top:8px; }
  `;

  const style = document.createElement('style');
  style.textContent = css;
  document.documentElement.appendChild(style);

  const box = document.createElement('div');
  box.id = 'nohomo-dub-helper';
  const ep = state.episode ? `S${String(state.season || 1).padStart(2, '0')}E${String(state.episode).padStart(2, '0')}` : 'episode not set';
  box.innerHTML = `
    <div class="ndh-head">
      <div>
        <div class="ndh-title">Nohomo DUB Helper</div>
        <div class="ndh-sub">Built into Minimal Media Player Pro</div>
      </div>
      <div style="display:flex;gap:6px;align-items:center;"><button class="ndh-btn" data-action="collapse" style="padding:4px 7px;font-size:11px;">_</button><button class="ndh-close" title="Close">×</button></div>
    </div>
    <div class="ndh-body">
      <div class="ndh-pill">Waiting for: ${state.title || 'Current title'} · ${ep}</div>
      <div class="ndh-text">
        Choose the voice you want on this page and start the site download normally.
        The player will catch the completed file from Downloads, move it to <b>dub/</b>, rename it, then sync and merge.
      </div>
      <div class="ndh-row">
        <button class="ndh-btn primary" data-action="import">I downloaded it</button>
        <button class="ndh-btn" data-action="scan">Scan DUB folder</button>
      </div>
      <div class="ndh-log" id="ndh-log">Helper injected. Login stays in this WebView profile.</div>
    </div>
  `;
  document.body.appendChild(box);

  const log = (msg) => {
    const el = document.getElementById('ndh-log');
    if (el) el.innerHTML = `${new Date().toLocaleTimeString()} — ${msg}<br>` + el.innerHTML;
  };

  let collapsed = false;
  box.querySelector('.ndh-close').onclick = () => box.remove();
  box.querySelector('[data-action="collapse"]').onclick = () => {
    collapsed = !collapsed;
    const body = box.querySelector('.ndh-body');
    if (body) body.style.display = collapsed ? 'none' : 'flex';
  };
  // Basic drag by header for cases where the helper covers site controls.
  (() => {
    const head = box.querySelector('.ndh-head');
    let dragging = false, sx = 0, sy = 0, ox = 0, oy = 0;
    head.style.cursor = 'move';
    head.addEventListener('mousedown', (e) => {
      dragging = true; sx = e.clientX; sy = e.clientY;
      const r = box.getBoundingClientRect(); ox = r.left; oy = r.top;
      box.style.left = ox + 'px'; box.style.top = oy + 'px'; box.style.right = 'auto'; box.style.bottom = 'auto';
      e.preventDefault();
    });
    window.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      box.style.left = Math.max(0, ox + e.clientX - sx) + 'px';
      box.style.top = Math.max(0, oy + e.clientY - sy) + 'px';
    });
    window.addEventListener('mouseup', () => dragging = false);
  })();
  box.querySelector('[data-action="import"]').onclick = async () => {
    try {
      log('Import requested...');
      if (window.pywebview && window.pywebview.api && window.pywebview.api.merger_import_downloads) {
        const raw = await window.pywebview.api.merger_import_downloads('dub_folder', true);
        log('Import result: ' + raw.slice(0, 180));
      } else {
        log('Player bridge not available on this page yet.');
      }
    } catch (e) { log('Import error: ' + e.message); }
  };
  box.querySelector('[data-action="scan"]').onclick = async () => {
    try {
      log('Scan requested...');
      if (window.pywebview && window.pywebview.api && window.pywebview.api.merger_scan) {
        const raw = await window.pywebview.api.merger_scan();
        log('Scan result: ' + raw.slice(0, 180));
      } else {
        log('Player bridge not available on this page yet.');
      }
    } catch (e) { log('Scan error: ' + e.message); }
  };
})();
