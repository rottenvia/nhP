import { h, icon, clear, renderList, baseName } from '../core/dom.js';
import { rpc, rpcSafe } from '../core/api.js';
import { store } from '../core/store.js';
import { toast, modal, confirm } from '../core/ui.js';
import { addToLibrary } from '../features/libraryOps.js';

export const mergerView = {
  id: 'merger', title: 'Merger', icon: 'merge', rail: true,
  async mount(el) {
    let busy = false;
    let scan = null;
    let watcher = null;
    const log = h('.log');
    const pairs = h('.list');
    const statusPill = h('span.badge', 'idle');
    const watchBtn = h('button.btn.lg.ghost', { onClick: () => toggleWatcher() }, icon('eye', 18), 'Watch Downloads');
    const voice = h('select.select', { style: { width: '190px' } }, h('option', { value: 'off' }, 'Voice: off'), h('option', { value: 'demucs' }, 'Voice: Demucs overlay'));
    const sync = h('select.select', { style: { width: '190px' } }, h('option', { value: 'auto' }, 'Sync: auto'), h('option', { value: 'multipoint' }, 'Sync: multipoint'), h('option', { value: 'global' }, 'Sync: global'));
    const folders = h('.hstack.wrap');
    el.append(h('.view-inner',
      h('.hero', { style: { minHeight: '0', padding: '28px 32px', marginBottom: '20px' } }, h('div', h('.kicker', 'Merger'), h('h2', 'Merge a dub into your episodes'), h('p', 'RAW video goes in raw/, the dub in dub/. Episodes are matched by number, audio is auto-synced, and a dubbed MKV lands in your library.'),
        h('.actions', h('button.btn.primary.lg', { onClick: () => smartAuto() }, icon('sparkles', 18), 'Smart auto'), h('button.btn.lg', { onClick: () => doScan() }, icon('refresh', 18), 'Scan'), h('button.btn.lg', { onClick: () => mergeAll() }, icon('merge', 18), 'Merge all'), watchBtn)),
        h('.stack', { style: { alignItems: 'flex-end', gap: '10px' } }, statusPill, voice, sync)),
      h('.merger-grid',
        h('div', h('.panel', h('.section-head', h('h3', 'Matched episodes'), h('.actions', h('button.btn.sm.ghost', { onClick: () => importDownloads('raw_folder') }, 'Import ↓ raw'), h('button.btn.sm.ghost', { onClick: () => importDownloads('dub_folder') }, 'Import ↓ dub'))), pairs),
          h('.panel', { style: { marginTop: '18px' } }, h('h3', 'Folders'), folders)),
        h('div', h('.panel', h('.section-head', h('h3', 'Log'), h('button.btn.sm.ghost', { onClick: () => clear(log) }, 'Clear')), log),
          h('.panel', { style: { marginTop: '18px' } }, h('h3', 'How it works'),
            step(1, 'Get the RAW', 'Use Downloads (or ask :3) to fetch the original episode into raw/.'),
            step(2, 'Get the DUB', 'Open the DUB browser, log in, pick a voice and download. Turn on "Watch Downloads" so files move to dub/ automatically.'),
            step(3, 'Merge', 'Smart auto scans, syncs and merges every matched pair, then files the result into your library.'),
            h('.hstack', { style: { marginTop: '10px' } }, h('button.btn', { onClick: () => openDubBrowser() }, icon('external', 16), 'Open DUB browser'), h('button.btn.ghost', { onClick: () => addOutputs() }, icon('plus', 16), 'Add outputs to library')))))));

    const line = (msg, cls = '') => { const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); log.appendChild(h('div', { class: cls }, h('span.t', `[${t}] `), msg)); log.scrollTop = log.scrollHeight; while (log.children.length > 300) log.firstChild.remove(); };
    const setStatus = (t, cls = '') => { statusPill.textContent = t; statusPill.className = 'badge ' + cls; };

    const renderFolders = () => { clear(folders); const f = scan?.folders || {}; for (const [k, label] of [['raw', 'raw/'], ['dub', 'dub/'], ['output', 'output/']]) folders.appendChild(h('button.btn.sm.ghost', { title: f[k] || '', onClick: () => rpcSafe('merger_open_folder', k + '_folder') }, icon('folder', 14), label)); folders.appendChild(h('button.btn.sm.ghost', { onClick: () => rpcSafe('open_library_folder') }, icon('folder', 14), 'library')); };

    const renderPairs = () => {
      const m = scan?.matched || [];
      renderList(pairs, m, { key: p => `${p.raw?.season || 1}:${p.raw?.episode}:${p.raw?.path}`, create: p => { const ep = p.raw?.episode ?? '?'; const se = p.raw?.season && p.raw.season > 1 ? `S${p.raw.season}` : ''; return h('.pair', h('.ep', `${se}E${String(ep).padStart(2, '0')}`), h('div', h('small', { title: p.raw?.path }, h('b', 'RAW '), p.raw?.name || ''), h('small', { title: p.dub?.path }, h('b', 'DUB '), p.dub?.name || ''))); } });
      if (!m.length) { clear(pairs); pairs.appendChild(h('p.muted.small', scan ? `${scan.raw?.length || 0} raw · ${scan.dub?.length || 0} dub files, no matching episode numbers.` : 'Scan to find pairs.')); }
      if (scan?.invalid?.length) for (const inv of scan.invalid) pairs.appendChild(h('p.small', { style: { color: 'var(--danger)' } }, `Skipped ${inv.folder}/${inv.name}: ${inv.reason}`));
    };

    const doScan = async (silent = false) => {
      if (!silent) setStatus('scanning', 'accent');
      const r = await rpcSafe('merger_scan');
      if (!r || r.status !== 'success') { line('Scan failed: ' + (r?.message || 'unknown'), 'err'); setStatus('error', 'danger'); return null; }
      scan = r; renderPairs(); renderFolders();
      if (!silent) { line(`Scan: ${r.raw?.length || 0} raw, ${r.dub?.length || 0} dub, ${r.matched?.length || 0} matched.`); setStatus(`${r.matched?.length || 0} pairs`); }
      return r;
    };

    const importDownloads = async (target, silent = false) => {
      const r = await rpcSafe('merger_import_downloads', target, true);
      const n = (r?.moved || r?.imported || []).length ?? 0;
      if (!silent || n) line(`Import → ${target === 'raw_folder' ? 'raw/' : 'dub/'}: ${r?.status || 'error'}${n ? ` (${n} file(s))` : ''}${r?.message ? ' · ' + r.message : ''}`);
      return r;
    };

    const mergeAll = async () => {
      if (busy) return toast('Merger is busy');
      busy = true; setStatus('merging', 'accent'); line(`Merge all started (voice=${voice.value}, sync=${sync.value}). This can take a while…`);
      const r = await rpcSafe('merger_autosync_merge_all', '', voice.value, sync.value);
      busy = false;
      if (!r) { line('Merge failed: backend error', 'err'); setStatus('error', 'danger'); return; }
      if (r.status === 'empty') { line(r.message || 'No pairs.'); setStatus('no pairs'); return; }
      if (r.status !== 'success') { line('Merge error: ' + (r.message || ''), 'err'); setStatus('error', 'danger'); return; }
      for (const res of r.results || []) { const ok = res.result?.status === 'success' || res.result?.ok; const ep = res.pair?.raw?.episode ?? res.pair?.episode; line(`E${ep}: ${ok ? 'merged → ' + baseName(res.result?.output || res.result?.organized || res.result?.path || '') : 'failed · ' + (res.result?.message || res.result?.error || '')}`, ok ? 'ok' : 'err'); }
      setStatus('done', 'ok'); toast('Merge finished', { kind: 'ok' });
      doScan(true);
    };

    const smartAuto = async () => {
      if (busy) return;
      line('Smart auto: importing downloads, scanning…');
      await importDownloads('raw_folder', true); await importDownloads('dub_folder', true);
      const r = await doScan();
      if (!r) return;
      if (r.matched?.length) return mergeAll();
      const raw = r.raw?.length || 0, dub = r.dub?.length || 0;
      if (!raw && !dub) { line('No RAW or DUB files. Download a RAW first, then a dub.'); setStatus('need files', 'warn'); }
      else if (!raw) { line('DUB present, RAW missing. Use Downloads or ask :3 for the RAW.'); setStatus('need RAW', 'warn'); }
      else if (!dub) { line('RAW present, DUB missing. Opening the DUB browser and watching Downloads.'); setStatus('need DUB', 'warn'); if (!watcher) toggleWatcher(); }
      else { line('Files exist but episode numbers do not match. Rename files to include S01E07 / Episode 7.'); setStatus('no match', 'warn'); }
    };

    const toggleWatcher = () => {
      if (watcher) { clearInterval(watcher); watcher = null; watchBtn.classList.remove('is-active'); watchBtn.replaceChildren(icon('eye', 18), 'Watch Downloads'); line('Watcher stopped.'); return; }
      watchBtn.classList.add('is-active'); watchBtn.replaceChildren(icon('eyeOff', 18), 'Watching…'); line('Watching ~/Downloads for dub files every 15 s.');
      watcher = setInterval(async () => { const r = await importDownloads('dub_folder', true); if ((r?.moved || r?.imported || []).length) { toast('New dub file imported', { kind: 'ok' }); await doScan(true); if (scan?.matched?.length && !busy) mergeAll(); } }, 15000);
    };

    const openDubBrowser = async () => {
      const url = store.state.settings?.keys?.DUB_SOURCE_URL || '';
      if (!url) { const ok = await confirm('No DUB source configured', 'Set "DUB source URL" in Settings → Downloads & sources first. Open settings now?'); if (ok) document.querySelector('[data-nav=settings]')?.click(); return; }
      const r = await rpcSafe('open_internal_url', url, '', 1, 0);
      toast(r ? 'DUB browser opened' : 'Could not open (desktop app only)', { kind: r ? 'ok' : 'err' });
    };

    const addOutputs = async () => {
      const r = await rpcSafe('merger_list_outputs');
      const files = r?.files || [];
      if (!files.length) return toast('No files in output/');
      const items = store.allItems();
      const sel = h('select.select', ...items.map(i => h('option', { value: `${i.category}:${i.id}` }, i.title)));
      const list = h('.stack', ...files.map(f => h('.list-row', h('span.muted.small', 'file'), h('.main', h('b', baseName(f.path || f))), h('span'))));
      const ok = await modal({ title: 'Add outputs to library', body: h('div', h('.field', h('label', 'Target title'), sel), h('div', { style: { marginTop: '12px' } }, list)), wide: true, actions: [{ label: 'Cancel', value: null, kind: 'ghost' }, { label: 'Link', value: true, kind: 'primary' }] });
      if (!ok) return;
      const [cat, id] = sel.value.split(':'); const item = store.findItem(id, cat); if (!item) return;
      const { guessEpisode } = await import('../core/dom.js');
      let n = 0;
      for (const f of files) { const path = f.path || f; const ep = guessEpisode(baseName(path)); if (!ep) continue; let e = item.episodes.find(x => Number(x.num) === ep); if (!e) { e = { num: ep }; item.episodes.push(e); } Object.assign(e, { path, name: baseName(path) }); if (ep > item.episodes_count) item.episodes_count = ep; n++; }
      item.episodes.sort((a, b) => a.num - b.num); store.updateItem(item); toast(`${n} episode(s) linked to ${item.title}`, { kind: 'ok' });
    };

    renderPairs(); renderFolders();
    return { show() { if (!scan) doScan(true); }, refresh() { doScan(); } };
  },
};

function step(n, title, text) { return h('.step', h('.n', String(n)), h('div', h('b', title), h('small', text))); }
