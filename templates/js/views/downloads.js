import { h, icon, clear, renderList, fmtBytes } from '../core/dom.js';
import { rpc, rpcSafe } from '../core/api.js';
import { store } from '../core/store.js';
import { toast, contextMenu } from '../core/ui.js';

export const downloadsView = {
  id: 'downloads', title: 'Downloads', icon: 'download', rail: true,
  async mount(el) {
    let kind = 'anime';
    let results = [];
    let seq = 0;
    let pollTimer = null;
    const input = h('input.input', { placeholder: 'Title + episode, e.g. "Kill Blue 07" or "Zodiac 2007"' });
    const kinds = h('.chips');
    const status = h('span.muted.small');
    const list = h('.stack');
    const verdict = h('.ai-verdict.muted', 'Search to get an expert verdict on the best release.');
    const active = h('.stack');
    const activeSec = h('.panel', h('.section-head', h('h3', 'Active downloads'), h('button.btn.sm.ghost', { onClick: () => poll() }, icon('refresh', 14), 'Refresh')), active);
    el.append(h('.view-inner',
      h('.toolbar', kinds, h('.spacer'), h('.search', { style: { width: 'min(560px,100%)' } }, icon('search'), input), h('button.btn.primary', { onClick: () => run() }, 'Search')),
      h('.merger-grid', h('div', h('.section-head', h('h2', 'Releases'), status), list), h('.stack', h('.panel', h('h3', 'Verdict'), verdict), activeSec)),
    ));
    const renderKinds = () => { clear(kinds); for (const [v, l] of [['anime', 'Anime · Nyaa'], ['movie', 'Movies · Prowlarr'], ['show', 'Shows · Prowlarr']]) kinds.appendChild(h('button.chip', { class: v === kind ? 'is-active' : '', onClick: () => { kind = v; renderKinds(); } }, l)); };
    renderKinds();
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') run(); });

    const run = async () => {
      const q = input.value.trim(); if (!q) return;
      const my = ++seq;
      status.textContent = 'Searching…'; clear(list);
      for (let i = 0; i < 4; i++) list.appendChild(h('.skeleton', { style: { height: '86px' } }));
      let data;
      try { data = kind === 'anime' ? await rpc('search_nyaa_torrents', q, false) : await rpc('movie_raw_search', q); } catch (e) { data = { status: 'error', message: e.message }; }
      if (my !== seq) return;
      clear(list);
      if (data.status === 'not_configured') { status.textContent = ''; list.appendChild(h('.empty', h('h3', 'Prowlarr not configured'), h('p', data.message || ''), h('button.btn.primary', { onClick: () => document.querySelector('[data-nav=settings]')?.click() }, 'Open settings'))); return; }
      if (data.status !== 'success') { status.textContent = ''; list.appendChild(h('.empty', h('h3', 'Search failed'), h('p', data.message || 'Unknown error'))); return; }
      results = (data.results || []).map(normalize);
      status.textContent = `${results.length} release${results.length === 1 ? '' : 's'}${data.query && data.query !== q ? ` · query: ${data.query}` : ''}`;
      verdict.textContent = ''; verdict.classList.remove('muted');
      if (data.ai_verdict) verdict.appendChild(renderVerdict(data.ai_verdict)); else verdict.append(h('span.muted', results.length ? 'Top result is highlighted. Add an OpenAI key in Settings for a written verdict.' : 'No results.'));
      if (!results.length) list.appendChild(h('.empty', h('h3', 'No releases found'), h('p', 'Try the romaji title or a shorter query.')));
      results.forEach((r, i) => list.appendChild(row(r, i === 0)));
    };

    const row = (r, best) => h('.torrent-row', { style: best ? { borderColor: 'rgba(124,92,252,.5)' } : {} },
      h('div', h('.name', r.title), h('.tags', best ? h('span.badge.accent', 'best pick') : null, r.type ? h('span.badge', r.type) : null, r.source ? h('span.badge', r.source) : null, r.group ? h('span.badge', r.group) : null, r.indexer ? h('span.badge', r.indexer) : null, r.censorship === 'UNCENSORED' ? h('span.badge.warn', 'uncensored') : null), r.comment ? h('p.small.muted', { style: { marginTop: '6px' } }, r.comment) : null,
        h('.stats', h('span', 'Size ', h('b', r.size)), h('span', 'Seeds ', h('b', String(r.seeders ?? '?'))), r.leechers != null ? h('span', 'Peers ', h('b', String(r.leechers))) : null)),
      h('.end', h('span.score', String(Math.round(r.score || 0))), h('button.btn.primary.sm', { onClick: () => download(r) }, icon('download', 14), 'Download'), h('button.btn.sm.ghost', { onClick: (e) => contextMenu(e.clientX, e.clientY, [
        { label: 'Open magnet in system client', icon: 'external', onClick: () => r.magnet ? rpcSafe('start_magnet_link', r.magnet) : toast('No magnet link') },
        { label: 'Save .torrent file', icon: 'file', onClick: async () => { const p = await rpcSafe('download_torrent_to_watch', r.torrent, r.title); toast(p ? 'Saved: ' + p : 'Failed', { kind: p ? 'ok' : 'err' }); } },
        { label: 'Copy magnet', icon: 'link', onClick: () => { navigator.clipboard.writeText(r.magnet || r.torrent || ''); toast('Copied'); } },
      ]) }, icon('more', 14))));

    const download = async (r) => {
      toast('Adding torrent…');
      const res = await rpcSafe('torrent_add_raw', r.torrent || '', r.magnet || '', r.title);
      if (!res) return toast('Failed to add torrent', { kind: 'err' });
      const msg = res.message || (res.status === 'success' ? 'Added to downloads' : res.status);
      toast(msg, { kind: res.status === 'success' || res.status === 'started' ? 'ok' : 'err', ms: 4500 });
      poll();
    };

    const poll = async () => {
      const st = await rpcSafe('torrent_status');
      const items = st?.downloads || [];
      renderList(active, items, {
        key: d => d.id,
        create: d => h('.list-row', h('span.mono.small', `${Math.round(d.progress || 0)}%`), h('.main', h('b', d.name || 'torrent'), h('small', `${d.downloaded_mb || 0} / ${d.total_mb || 0} MB · ↓ ${d.download_rate_kb || 0} KB/s · peers ${d.num_peers || 0}${d.error ? ' · ' + d.error : ''}`), h('.progress-bar', { style: { marginTop: '6px' } }, h('i', { style: { width: (d.progress || 0) + '%' } }))), h('span.badge', { class: d.finished ? 'ok' : '' }, d.finished ? 'done' : (d.state || ''))),
        update: (el, d) => { el.querySelector('.mono').textContent = `${Math.round(d.progress || 0)}%`; el.querySelector('small').textContent = `${d.downloaded_mb || 0} / ${d.total_mb || 0} MB · ↓ ${d.download_rate_kb || 0} KB/s · peers ${d.num_peers || 0}`; el.querySelector('.progress-bar i').style.width = (d.progress || 0) + '%'; },
      });
      if (!items.length) { clear(active); active.appendChild(h('p.muted.small', st?.engine === 'libtorrent' ? 'No active downloads.' : 'Internal engine unavailable; downloads go to qBittorrent or .torrent files.')); }
    };

    return {
      show(p) { if (p?.query) { input.value = p.query; if (p.kind) { kind = p.kind; renderKinds(); } run(); } poll(); clearInterval(pollTimer); pollTimer = setInterval(poll, 5000); },
      hide() { clearInterval(pollTimer); pollTimer = null; },
      refresh() { poll(); },
    };
  },
};

function normalize(r) {
  return {
    title: r.title || '', size: r.size ? String(r.size) : (r.size_gb ? `${r.size_gb} GB` : '?'), seeders: r.seeders, leechers: r.leechers,
    type: r.type, source: r.source, group: r.group, comment: r.comment, censorship: r.censorship, score: r.score, indexer: r.indexer,
    magnet: r.magnet_link || r.magnetUrl || '', torrent: r.torrent_link || r.downloadUrl || '',
  };
}

function renderVerdict(text) {
  // The verdict may contain <a href> links; allow only those and strip everything else.
  const tpl = document.createElement('template');
  tpl.innerHTML = String(text);
  const out = document.createDocumentFragment();
  const walk = (node) => {
    for (const c of node.childNodes) {
      if (c.nodeType === 3) out.appendChild(document.createTextNode(c.textContent));
      else if (c.nodeType === 1 && c.tagName === 'A' && /^(magnet:|https?:)/i.test(c.getAttribute('href') || '')) { const a = h('a', { href: c.getAttribute('href'), onClick: (e) => { e.preventDefault(); const href = a.getAttribute('href'); if (href.startsWith('magnet:')) rpcSafe('start_magnet_link', href); else rpcSafe('open_external_url', href); } }, c.textContent); out.appendChild(a); }
      else if (c.nodeType === 1 && c.tagName === 'BR') out.appendChild(document.createTextNode('\n'));
      else if (c.nodeType === 1) walk(c);
    }
  };
  walk(tpl.content);
  return out;
}
