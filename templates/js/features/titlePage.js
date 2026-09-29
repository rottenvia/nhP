// Full-screen title page: poster, facts, franchise parts (anime), seasons (shows), episode grid,
// episode list with descriptions, linking and playback.
import { h, icon, $, clear, renderList, fmtTime, baseName, posterImg } from '../core/dom.js';
import { meta } from '../core/api.js';
import { store } from '../core/store.js';
import { toast, contextMenu, confirm } from '../core/ui.js';
import { playEpisode, resumeItem, linkEpisodeFile, linkFolder, linkMultipleFiles, unlinkEpisode, addToLibrary, removeFromLibrary, refreshMetadata, openTitle } from './libraryOps.js';

const root = $('#title-page');
let current = null;        // item being displayed
let unsub = [];
let partsCache = new Map(); // anime id -> parts
let activePart = null;     // {id,...} for franchise navigation
let activeSeason = 1;

export function initTitlePage() {
  document.addEventListener('title:open', (e) => open(e.detail.item));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && root.classList.contains('is-open') && !document.querySelector('.modal-backdrop') && document.body.classList.contains('player-full') === false) close(); });
}

export function close() {
  root.classList.remove('is-open');
  setTimeout(() => { if (!root.classList.contains('is-open')) { root.hidden = true; clear(root); } }, 320);
  unsub.forEach(u => u()); unsub = [];
  current = null;
}

export async function open(item) {
  current = item;
  activeSeason = 1;
  root.hidden = false;
  render();
  requestAnimationFrame(() => root.classList.add('is-open'));
  root.scrollTop = 0;
  unsub.forEach(u => u()); unsub = [];
  unsub.push(store.on('library', () => { const fresh = store.findItem(current.id, current.category); if (fresh) current = fresh; renderEpisodes(); renderActions(); }));
  unsub.push(store.on('watched', renderEpisodes));
  unsub.push(store.on('progress', renderEpisodes));
  // Enrich from metadata if the item is thin (catalog result or old library entry).
  if (!item.genres?.length || !item.synopsis) {
    const r = await meta.details(item.category, item.id).catch(() => null);
    if (r?.status === 'success' && current === item) {
      const lib = store.findItem(item.id, item.category);
      Object.assign(item, { ...r.item, episodes: item.episodes, episodes_count: Math.max(item.episodes_count || 0, r.item.episodes || 0) });
      if (lib) { Object.assign(lib, { genres: r.item.genres, synopsis: r.item.synopsis, backdrop: r.item.backdrop, studio: r.item.studio, score: r.item.score, year: r.item.year, seasons: r.item.seasons, poster: lib.poster || r.item.poster }); if (!lib.episodes_count && r.item.episodes) { lib.episodes_count = r.item.episodes; } store.updateItem(lib); }
      render();
    }
  }
  if (item.category === 'anime') loadFranchise(item);
  loadEpisodeDetails(item);
}

function render() {
  const item = current; if (!item) return;
  clear(root);
  const backdrop = h('.backdrop', { class: item.backdrop ? '' : 'blur', style: { backgroundImage: `url("${item.backdrop || item.poster}")` } });
  const posterCol = h('.poster-col', posterImg(item.poster, item.title), h('.stack.actions-col'));
  const head = h('.head', posterCol, h('div',
    h('h1', item.title),
    item.title_original && item.title_original !== item.title ? h('.alt', item.title_original) : null,
    h('.pills', h('span.badge.accent', item.category === 'show' ? 'TV Show' : item.category), item.type && item.type !== 'TV' ? h('span.badge', item.type) : null, item.status && item.status !== 'unknown' ? h('span.badge', { class: item.status === 'airing' ? 'ok' : '' }, item.status) : null, item.year ? h('span.badge', String(item.year)) : null, item.episodes_count ? h('span.badge', `${item.episodes_count} episodes`) : null, item.score ? h('span.badge', `★ ${item.score}`) : null),
    synopsisEl(item.synopsis),
    factsEl(item),
    h('.parts-wrap'),
    h('.episodes-wrap'),
  ));
  root.append(backdrop, h('.content', h('.top', h('button.btn.ghost', { onClick: close }, icon('back', 16), 'Back'), h('.grow'), h('button.btn.ghost.sm', { onClick: () => refreshMetadata(store.findItem(item.id, item.category) || item) }, icon('refresh', 14), 'Refresh')), head));
  renderActions();
  renderParts();
  renderEpisodes();
}

function fact(label, value) { if (!value) return null; return h('div', h('dt', label), h('dd', value)); }
function factsEl(item) {
  const facts = [fact('Studio / Network', item.studio), fact('Genres', (item.genres || []).join(', ')), fact('Source', item.source_material), fact('Runtime', item.runtime ? `${item.runtime} min` : ''), fact('Broadcast', item.broadcast), fact('Next episode', item.next_episode?.air_date ? `Ep ${item.next_episode.episode_number} · ${item.next_episode.air_date}` : '')].filter(Boolean);
  return facts.length ? h('dl.facts', ...facts) : null;
}
function synopsisEl(text) {
  if (!text) return h('p.synopsis.muted', 'No synopsis.');
  const p = h('p.synopsis.clamp', text);
  if (text.length > 320) p.addEventListener('click', () => p.classList.toggle('clamp'));
  return p;
}

function renderActions() {
  const item = current; const col = root.querySelector('.actions-col'); if (!col) return;
  clear(col);
  const lib = store.findItem(item.id, item.category);
  if (lib) {
    const prog = store.getProgress(lib.id);
    const hasFiles = lib.episodes.some(e => e.path);
    col.append(
      h('button.btn.primary.lg', { onClick: () => resumeItem(lib), disabled: !hasFiles && lib.category !== 'movie' }, icon('play'), prog ? `Resume Ep ${prog.epNum} · ${fmtTime(prog.time)}` : (hasFiles ? 'Play' : 'Play')),
      h('button.btn', { onClick: () => linkFolder(lib) }, icon('folder', 16), 'Link folder'),
      h('button.btn', { onClick: () => linkMultipleFiles(lib) }, icon('link', 16), 'Link files'),
      h('button.btn.ghost.danger', { onClick: async () => { if (await removeFromLibrary(lib)) close(); } }, icon('trash', 16), 'Remove'),
    );
  } else {
    col.append(h('button.btn.primary.lg', { onClick: async () => { const added = await addToLibrary(item); current = added; render(); } }, icon('plus'), 'Add to library'));
  }
}

// ───────── franchise parts (anime) / seasons (shows) ─────────
async function loadFranchise(item) {
  if (partsCache.has(item.id)) { renderParts(); return; }
  const wrap = root.querySelector('.parts-wrap'); if (wrap) wrap.appendChild(h('.hstack.muted.small', { dataset: { loading: 1 } }, h('.spinner'), 'Loading watch order…'));
  const r = await meta.franchise(item.id).catch(() => null);
  wrap?.querySelector('[data-loading]')?.remove();
  if (r?.status === 'success' && r.parts?.length > 1) partsCache.set(item.id, r.parts);
  else partsCache.set(item.id, []);
  if (current === item) renderParts();
}

function renderParts() {
  const item = current; const wrap = root.querySelector('.parts-wrap'); if (!wrap) return;
  clear(wrap);
  if (item.category === 'show' && item.seasons?.length > 1) {
    wrap.append(h('.section-head', { style: { marginTop: '22px' } }, h('h2', 'Seasons'), h('span.sub', `${item.seasons.length} seasons`)));
    const bar = h('.parts');
    for (const s of item.seasons) bar.appendChild(h('button.part', { class: s.season === activeSeason ? 'is-active' : '', onClick: () => { activeSeason = s.season; renderParts(); renderEpisodes(); loadEpisodeDetails(item); } }, h('span.n', `S${s.season}`), h('div', h('b', s.name || `Season ${s.season}`), h('small', `${s.episodes} ep${s.air_date ? ' · ' + s.air_date.slice(0, 4) : ''}`))));
    wrap.appendChild(bar);
    return;
  }
  const parts = partsCache.get(item.id) || [];
  if (parts.length < 2) return;
  wrap.append(h('.section-head', { style: { marginTop: '22px' } }, h('h2', 'Watch order'), h('span.sub', 'Franchise parts in chronological order')));
  const bar = h('.parts');
  parts.forEach((p, i) => bar.appendChild(h('button.part', { class: String(p.id) === String(item.id) ? 'is-active' : '', title: p.title, onClick: () => openPart(p) },
    h('span.n', String(i + 1).padStart(2, '0')), h('div', h('b', p.title), h('small', [p.type, p.episodes ? `${p.episodes} ep` : null, p.year, p.relation !== 'main' ? p.relation : null].filter(Boolean).join(' · '))))));
  wrap.appendChild(bar);
}

async function openPart(p) {
  const lib = store.findItem(p.id, 'anime');
  if (lib) return open(lib);
  const r = await meta.details('anime', p.id).catch(() => null);
  if (r?.status === 'success') open({ ...r.item, episodes: [], episodes_count: r.item.episodes || 0 });
}

// ───────── episodes ─────────
const epDetails = new Map(); // key -> [{number,title,aired,overview,still}]

async function loadEpisodeDetails(item) {
  const key = item.category === 'show' ? `${item.id}:s${activeSeason}` : String(item.id);
  if (epDetails.has(key)) { renderEpisodes(); return; }
  let eps = [];
  try {
    if (item.category === 'anime') {
      let page = 1;
      for (;;) { const r = await meta.episodes(item.id, page); if (r.status !== 'success') break; eps.push(...(r.episodes || [])); if (!r.has_next || page >= 8) break; page++; }
    } else if (item.category === 'show') {
      const r = await meta.season(item.id, activeSeason); if (r.status === 'success') eps = r.episodes || [];
    }
  } catch {}
  epDetails.set(key, eps);
  if (current === item) renderEpisodes();
}

function seasonOffset(item) {
  if (item.category !== 'show' || !item.seasons?.length) return 0;
  let off = 0;
  for (const s of item.seasons) { if (s.season >= activeSeason) break; off += s.episodes || 0; }
  return off;
}

function renderEpisodes() {
  const item = current; const wrap = root.querySelector('.episodes-wrap'); if (!wrap || !item) return;
  clear(wrap);
  const lib = store.findItem(item.id, item.category);
  const total = item.category === 'show' && item.seasons?.length ? (item.seasons.find(s => s.season === activeSeason)?.episodes || 0) : Math.max(item.episodes_count || 0, (lib?.episodes || []).length, item.category === 'movie' ? 1 : 0);
  const offset = seasonOffset(item);
  const key = item.category === 'show' ? `${item.id}:s${activeSeason}` : String(item.id);
  const details = epDetails.get(key) || [];
  const linkedCount = (lib?.episodes || []).filter(e => e.path).length;
  wrap.append(h('.section-head', { style: { marginTop: '22px' } }, h('h2', item.category === 'movie' ? 'Movie' : 'Episodes'), h('span.linked-counter', lib ? `${linkedCount} / ${lib.episodes_count || total} linked` : 'Add to library to link files')));
  if (!total) { wrap.appendChild(h('.empty', h('h3', 'Episode count unknown'), h('p', 'Link files to create episodes.'))); return; }
  const grid = h('.episodes');
  const prog = lib ? store.getProgress(lib.id) : null;
  const playing = window.__player?.getState();
  for (let n = 1; n <= total; n++) {
    const abs = offset + n;
    const ep = lib?.episodes.find(e => Number(e.num) === abs);
    const d = details.find(x => Number(x.number) === n);
    const unaired = d?.aired ? new Date(d.aired) > new Date() : (item.status === 'upcoming');
    const btn = h('button.ep', { class: [ep?.path ? 'linked' : '', lib && store.isWatched(lib.id, abs) ? 'watched' : '', unaired ? 'unaired' : '', playing?.open && playing.item?.id === item.id && Number(playing.epNum) === abs ? 'active' : ''].join(' '), title: d?.title ? `${abs}. ${d.title}${ep?.path ? '\n' + ep.path : ''}` : (ep?.path || `Episode ${abs}`) }, String(item.category === 'movie' ? '▶' : abs));
    if (prog && Number(prog.epNum) === abs && prog.duration) btn.appendChild(h('.bar', { style: { width: `${Math.min(100, prog.time / prog.duration * 100)}%` } }));
    btn.addEventListener('click', () => lib ? playEpisode(lib, abs) : addThenPlay(item, abs));
    btn.addEventListener('contextmenu', (e) => { e.preventDefault(); if (!lib) return; episodeMenu(e, lib, abs, ep); });
    grid.appendChild(btn);
  }
  wrap.appendChild(grid);
  if (details.length) {
    const list = h('.ep-list');
    for (const d of details.slice(0, 200)) {
      const abs = offset + Number(d.number);
      list.appendChild(h('.ep-row', { onClick: () => lib ? playEpisode(lib, abs) : addThenPlay(item, abs) },
        d.still ? h('img', { src: d.still, loading: 'lazy', alt: '' }) : h('.skeleton', { style: { width: '96px', height: '54px', animation: 'none' } }),
        h('div', h('.t', `${abs}. ${d.title || 'Episode ' + abs}`), h('.d', d.overview || [d.aired ? `Aired ${String(d.aired).slice(0, 10)}` : '', d.filler ? 'Filler' : '', d.recap ? 'Recap' : ''].filter(Boolean).join(' · '))),
        h('span.muted.small', lib?.episodes.find(e => Number(e.num) === abs)?.path ? 'linked' : '')));
    }
    wrap.appendChild(list);
  }
}

async function addThenPlay(item, ep) {
  const added = await addToLibrary(item); current = added; render(); playEpisode(added, ep);
}

function episodeMenu(e, lib, epNum, ep) {
  const items = [
    { label: 'Play', icon: 'play', onClick: () => playEpisode(lib, epNum) },
    { label: ep?.path ? 'Relink file…' : 'Link file…', icon: 'link', onClick: () => linkEpisodeFile(lib, epNum) },
    { label: store.isWatched(lib.id, epNum) ? 'Mark unwatched' : 'Mark watched', icon: 'check', onClick: () => store.setWatched(lib.id, epNum, !store.isWatched(lib.id, epNum)) },
    { label: 'Mark all up to here watched', icon: 'check', onClick: () => { for (let n = 1; n <= epNum; n++) store.setWatched(lib.id, n, true); } },
  ];
  if (ep?.path) items.push({ sep: true }, { label: 'Unlink file', icon: 'x', danger: true, onClick: async () => { if (await confirm('Unlink', `Unlink episode ${epNum}? The file stays on disk.`)) unlinkEpisode(lib, epNum); } });
  contextMenu(e.clientX, e.clientY, items);
}
