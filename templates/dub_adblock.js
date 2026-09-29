(() => {
  if (window.__NOHOMO_UBLOCK_LITE__) {
    try { window.__NOHOMO_UBLOCK_LITE__.sweep('manual reinject'); } catch(e) {}
    return;
  }

  const BAD = /beton|slot|slotcity|casino|vulkan|1xbet|melbet|parimatch|ggbet|pin[-_ ]?up|mostbet|fonbet|adservice|doubleclick|googlesyndication|googleadservices|adfox|adriver|yandex\.ru\/ads|mgid|taboola|traffic|popunder|clickunder|banner|teaser|promo|реклама|казино|ставк|букмек/i;
  const SAFE = /player|cdnplayer|video|episode|season|translator|simple|movie|film|post|content|b-post|b-simple|b-player|jwplayer|vjs|plyr/i;
  const state = { removed: 0, hidden: 0, lastReason: 'init' };

  function addStyle() {
    if (document.getElementById('nohomo-ublock-lite-style')) return;
    const style = document.createElement('style');
    style.id = 'nohomo-ublock-lite-style';
    style.textContent = `
      html, body { background-image: none !important; }
      iframe[src*="doubleclick"], iframe[src*="googlesyndication"], iframe[src*="googleads"], iframe[src*="adservice"],
      iframe[src*="adfox"], iframe[src*="adriver"], iframe[src*="mgid"], iframe[src*="taboola"],
      a[href*="beton"], a[href*="slot"], a[href*="casino"], a[href*="1xbet"], a[href*="melbet"], a[href*="parimatch"], a[href*="ggbet"],
      img[src*="beton"], img[src*="slot"], img[src*="casino"], img[src*="1xbet"], img[src*="melbet"], img[src*="parimatch"], img[src*="ggbet"],
      [id^="adriver"], [id*="adfox"], [id*="adriver"], [id*="advert"], [id*="banner"],
      [class*="adfox"], [class*="adriver"], [class*="advert"], [class*="banner"], [class*="teaser"], [class*="popup"], [class*="popunder"] {
        display: none !important; visibility: hidden !important; pointer-events: none !important;
        width: 0 !important; height: 0 !important; max-width: 0 !important; max-height: 0 !important; overflow: hidden !important;
      }
      #nohomo-adblock-panel { position: fixed; right: 18px; bottom: 18px; z-index: 2147483647; width: 260px; background: rgba(8,8,12,.92); color: #fff; border: 1px solid rgba(255,255,255,.12); border-radius: 14px; box-shadow: 0 14px 36px rgba(0,0,0,.55); font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif; overflow: hidden; backdrop-filter: blur(12px); }
      #nohomo-adblock-panel .nh-head { padding: 10px 12px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,.08); }
      #nohomo-adblock-panel .nh-title { font-size:12px; font-weight:900; }
      #nohomo-adblock-panel .nh-body { padding: 10px 12px; display:flex; flex-direction:column; gap:8px; }
      #nohomo-adblock-panel .nh-text { color:rgba(255,255,255,.68); font-size:11px; line-height:1.35; }
      #nohomo-adblock-panel .nh-row { display:flex; gap:6px; flex-wrap:wrap; }
      #nohomo-adblock-panel button { border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.05); color:#fff; border-radius:8px; padding:6px 8px; font-size:11px; font-weight:800; cursor:pointer; }
      #nohomo-adblock-panel button.primary { background:#7c5cfc; border-color:#7c5cfc; }
    `;
    document.documentElement.appendChild(style);
  }

  function infoOf(el) {
    return [el.getAttribute('src'), el.getAttribute('href'), el.getAttribute('data-src'), el.getAttribute('data-href'), el.id, typeof el.className === 'string' ? el.className : '', el.getAttribute('style'), el.getAttribute('title'), el.getAttribute('alt')].filter(Boolean).join(' ').slice(0, 1800);
  }

  function isPlayerOrContent(el) {
    let cur = el;
    for (let i = 0; cur && i < 4; i++, cur = cur.parentElement) {
      const text = ((cur.id || '') + ' ' + (typeof cur.className === 'string' ? cur.className : '')).slice(0, 600);
      if (SAFE.test(text)) return true;
    }
    return false;
  }

  function isAdLike(el) {
    if (!el || el.nodeType !== 1 || el.id === 'nohomo-adblock-panel' || el.closest('#nohomo-adblock-panel')) return false;
    const tag = el.tagName;
    const txt = infoOf(el);
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    if (isPlayerOrContent(el) && !BAD.test(txt)) return false;
    if (BAD.test(txt)) return true;
    const fixedOrAbs = style.position === 'fixed' || style.position === 'absolute' || style.position === 'sticky';
    const side = rect.width >= 120 && rect.height >= 300 && (rect.right < vw * 0.28 || rect.left > vw * 0.72);
    if (fixedOrAbs && side) return true;
    const ratio = rect.height > 0 ? rect.width / rect.height : 0;
    const wideBanner = rect.width >= 420 && rect.height >= 45 && rect.height <= 180 && ratio >= 3.0;
    if ((tag === 'IMG' || tag === 'IFRAME' || tag === 'A' || fixedOrAbs) && wideBanner && !isPlayerOrContent(el)) return true;
    const tallAd = (tag === 'IMG' || tag === 'IFRAME' || tag === 'A') && rect.height >= 250 && rect.width >= 90 && (rect.left < 80 || rect.right > vw - 80 || side);
    if (tallAd) return true;
    return false;
  }

  function zap(el) {
    try {
      const tag = el.tagName;
      if (tag === 'IFRAME' || tag === 'IMG' || tag === 'A') { el.remove(); state.removed++; }
      else { el.style.setProperty('display', 'none', 'important'); el.style.setProperty('visibility', 'hidden', 'important'); el.style.setProperty('pointer-events', 'none', 'important'); state.hidden++; }
    } catch(e) {}
  }

  function sweep(reason='sweep') {
    state.lastReason = reason;
    addStyle();
    const nodes = Array.from(document.querySelectorAll('iframe,img,a,div,aside,section,ins'));
    let checked = 0;
    for (const el of nodes) { if (++checked > 2500) break; if (isAdLike(el)) zap(el); }
    // Text-based cosmetic cleanup for promo bars/buttons that do not expose ad-like URLs.
    const textNodes = Array.from(document.querySelectorAll('div,section,a,button,span'));
    for (const el of textNodes) {
      if (!el || el.closest('#nohomo-adblock-panel') || isPlayerOrContent(el)) continue;
      const txt = (el.innerText || el.textContent || '').trim().slice(0, 500);
      if (!txt) continue;
      if (/HDREZKA\s+буде\s+заблокована|Premium|Премиум|Реклама\s*\d|Пропустить\s+через|промокод|бонус|гравц|казино|ставк/i.test(txt)) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 120 && rect.height > 20) zap(el);
      }
    }
    updatePanel();
    return { removed: state.removed, hidden: state.hidden, reason };
  }

  let pending = false;
  function schedule(reason='mutation') { if (pending) return; pending = true; setTimeout(() => { pending = false; sweep(reason); }, 700); }

  function makePanel() {
    if (document.getElementById('nohomo-adblock-panel')) return;
    const ctx = window.__NOHOMO_DUB_CONTEXT__ || {};
    const ep = ctx.episode ? `S${String(ctx.season || 1).padStart(2, '0')}E${String(ctx.episode).padStart(2, '0')}` : 'episode not set';
    const panel = document.createElement('div');
    panel.id = 'nohomo-adblock-panel';
    panel.innerHTML = `
      <div class="nh-head"><div><div class="nh-title">:3 DUB Helper</div><div style="font-size:10px;color:rgba(255,255,255,.5);margin-top:2px;">AdBlock + download watcher</div></div><button data-nh="close">×</button></div>
      <div class="nh-body">
        <div class="nh-text"><b>Waiting for:</b> ${ctx.title || 'Current title'} · ${ep}</div>
        <div class="nh-text" id="nh-adblock-status">Cleaning page...</div>
        <div class="nh-row">
          <button class="primary" data-nh="downloaded">I downloaded it</button>
          <button data-nh="scan">Scan DUB</button>
          <button data-nh="clean">Clean ads</button>
          <button data-nh="collapse">Hide</button>
        </div>
        <div class="nh-text" id="nh-helper-log">Choose voice on the page and start the site download. The player will catch the finished file from Downloads/dub.</div>
      </div>
    `;
    document.body.appendChild(panel);
    panel.querySelector('[data-nh="close"]').onclick = () => panel.remove();
    panel.querySelector('[data-nh="collapse"]').onclick = () => { const b = panel.querySelector('.nh-body'); if (b) b.style.display = b.style.display === 'none' ? 'flex' : 'none'; };
    panel.querySelector('[data-nh="clean"]').onclick = () => sweep('manual');
    const helperLog = (msg) => { const el = document.getElementById('nh-helper-log'); if (el) el.textContent = msg; };
    panel.querySelector('[data-nh="downloaded"]').onclick = async () => {
      try {
        helperLog('Importing Downloads into dub/...');
        if (window.pywebview && window.pywebview.api && window.pywebview.api.merger_import_downloads) {
          const raw = await window.pywebview.api.merger_import_downloads('dub_folder', true);
          helperLog('Import result: ' + raw.slice(0, 220));
          if (window.pywebview.api.merger_scan) await window.pywebview.api.merger_scan();
        } else helperLog('Player bridge is not ready. Return to the main Merger tab and use Import Downloads → dub/.');
      } catch(e) { helperLog('Import error: ' + e.message); }
    };
    panel.querySelector('[data-nh="scan"]').onclick = async () => {
      try {
        helperLog('Scanning dub/raw...');
        if (window.pywebview && window.pywebview.api && window.pywebview.api.merger_scan) {
          const raw = await window.pywebview.api.merger_scan();
          helperLog('Scan result: ' + raw.slice(0, 220));
        } else helperLog('Player bridge is not ready.');
      } catch(e) { helperLog('Scan error: ' + e.message); }
    };
  }


  function updatePanel() { const el = document.getElementById('nh-adblock-status'); if (el) el.textContent = `Removed: ${state.removed} · Hidden: ${state.hidden} · ${state.lastReason}`; }

  addStyle(); makePanel(); sweep('initial'); setTimeout(() => sweep('delayed 1'), 1500); setTimeout(() => sweep('delayed 2'), 3500);
  const observer = new MutationObserver(() => schedule('mutation'));
  observer.observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ['src','href','class','style','id'] });
  window.__NOHOMO_UBLOCK_LITE__ = { sweep, state, observer };
})();
