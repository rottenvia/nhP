// Entry point: boot → hydrate → mount shell → hide the :3 screen.
import { h, icon, $ } from './core/dom.js';
import { getJSON, pickFiles } from './core/api.js';
import { store } from './core/store.js';
import { router } from './core/router.js';
import { toast, closeTopModal, closeContextMenu } from './core/ui.js';
import { player } from './player/player.js';
import { homeView } from './views/home.js';
import { libraryView } from './views/library.js';
import { catalogView } from './views/catalog.js';
import { watchingView } from './views/watching.js';
import { downloadsView } from './views/downloads.js';
import { mergerView } from './views/merger.js';
import { settingsView } from './views/settings.js';
import { initTitlePage, close as closeTitle } from './features/titlePage.js';
import { initAssistant } from './features/assistant.js';
import { initShare } from './features/share.js';
import { playEpisode, searchLibrary } from './features/libraryOps.js';

const bootStatus = (t, pct) => { $('#boot-status').textContent = t; if (pct != null) $('#boot-bar').style.width = pct + '%'; };

async function boot() {
  const t0 = performance.now();
  bootStatus('Connecting…', 15);
  let data = null;
  for (let attempt = 0; attempt < 40 && !data; attempt++) {
    try { data = await getJSON('/api/boot', { timeout: 4000 }); }
    catch (e) { bootStatus(attempt < 3 ? 'Starting backend…' : `Waiting for backend (${attempt})…`, 20 + Math.min(40, attempt * 2)); await new Promise(r => setTimeout(r, 300 + attempt * 100)); }
  }
  if (!data) return bootFail('The local backend did not answer. Check that nothing else uses the port and restart the app.');
  bootStatus('Loading library…', 70);
  window.__hasWindow = !!data.app?.window;
  store.hydrate(data);
  bootStatus('Ready', 100);
  mountShell();
  const ms = Math.round(performance.now() - t0);
  console.info(`[boot] ready in ${ms} ms (backend ${data.boot_ms} ms)`);
  $('#app').hidden = false;
  requestAnimationFrame(() => { $('#boot').classList.add('is-hidden'); setTimeout(() => $('#boot').remove(), 600); });
}

function bootFail(msg) {
  bootStatus('Startup failed', 100);
  const err = $('#boot-error'); err.textContent = msg; err.style.display = 'block';
  const btn = $('#boot-retry'); btn.style.display = 'inline-block'; btn.onclick = () => location.reload();
}

function mountShell() {
  for (const v of [homeView, libraryView, catalogView, watchingView, downloadsView, mergerView, settingsView]) router.register(v);
  router.mountRail();
  initTitlePage();
  initAssistant();
  initShare();
  $('#nav-back').addEventListener('click', () => router.back());
  $('#btn-open-file').addEventListener('click', async () => { const f = await pickFiles({ multiple: true }); if (f.length) player.open(f, { index: 0 }); });

  // Global search: library first, Enter → catalog.
  const gs = $('#global-search');
  gs.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { const q = gs.value.trim(); if (!q) return; const hits = searchLibrary(q); if (hits.length && !e.shiftKey) router.go('library', { query: q }); else router.go('catalog', { query: q }); gs.blur(); }
    if (e.key === 'Escape') { gs.value = ''; gs.blur(); }
  });
  document.addEventListener('keydown', (e) => {
    const t = e.target; const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
    if (e.key === '/' && !typing && !document.body.classList.contains('player-full')) { e.preventDefault(); gs.focus(); gs.select(); }
    if (e.key === 'Escape' && !typing) { if (closeTopModal()) return; closeContextMenu(); if (!$('#title-page').hidden && !document.body.classList.contains('player-full')) return; if (!document.body.classList.contains('player-full')) router.back(); }
  });

  // Episode chaining from the player.
  document.addEventListener('player:play-episode', (e) => playEpisode(e.detail.item, e.detail.epNum, { startTime: 0 }));
  player.addEventListener('mode', (e) => { if (e.detail === 'full') closeTitle(); });

  // Drag & drop anywhere.
  let dragDepth = 0;
  const overlay = $('#drop-overlay');
  document.addEventListener('dragenter', (e) => { e.preventDefault(); dragDepth++; overlay.classList.add('show'); });
  document.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; overlay.classList.remove('show'); } });
  document.addEventListener('dragover', (e) => e.preventDefault());
  document.addEventListener('drop', (e) => {
    e.preventDefault(); dragDepth = 0; overlay.classList.remove('show');
    const files = [...(e.dataTransfer?.files || [])].map(f => ({ path: f.path || '', name: f.name, size: f.size, file: f.path ? undefined : f }));
    if (files.length) player.open(files, { index: 0 });
  });

  // Restore the previous playlist silently (not auto-playing).
  const pl = store.state.playlist;
  if (pl.length && store.state.playlistIndex >= 0) { player.playlist = pl.map(t => ({ ...t })); player.index = store.state.playlistIndex; }

  router.go('home', {}, { replace: true });
  document.addEventListener('view:change', () => { window.__currentTitle = null; });
  window.addEventListener('beforeunload', () => { try { player.saveProgress(true); } catch {} });
  window.addEventListener('error', (e) => console.error('[app]', e.error || e.message));
  window.addEventListener('unhandledrejection', (e) => console.error('[app] unhandled', e.reason));
}

boot();
