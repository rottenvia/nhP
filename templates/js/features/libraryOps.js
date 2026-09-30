// Shared library operations used by views, the title page, context menus and the assistant.
import { h, icon, posterImg, guessEpisode, baseName } from '../core/dom.js';
import { rpc, rpcSafe, pickFiles, pickFolder, meta, getJSON } from '../core/api.js';
import { store, normalizeItem } from '../core/store.js';
import { toast, confirm, modal, contextMenu, taskOverlay, hideTask } from '../core/ui.js';
import { player } from '../player/player.js';

export function openTitle(item) {
  document.dispatchEvent(new CustomEvent('title:open', { detail: { item } }));
}

/** Play a library episode (or resume it). */
export async function playEpisode(item, epNum, { startTime = null, source = 'ui' } = {}) {
  item = store.findItem(item.id, item.category) || item;
  let ep = item.episodes.find(e => Number(e.num) === Number(epNum));
  if (!ep || !ep.path) {
    const ok = await confirm('Episode not linked', `Episode ${epNum} of "${item.title}" has no file yet. Link one now?`, { okLabel: 'Link file' });
    if (!ok) return false;
    const linked = await linkEpisodeFile(item, epNum);
    if (!linked) return false;
    ep = item.episodes.find(e => Number(e.num) === Number(epNum));
  }
  let start = startTime;
  if (start == null) {
    const p = store.getProgress(item.id);
    if (p && Number(p.epNum) === Number(epNum) && p.time > 15) start = p.time;
  }
  // Build a playlist of all linked episodes so next/prev work naturally.
  const linked = item.episodes.filter(e => e.path);
  const tracks = linked.map(e => ({ name: e.name || baseName(e.path), path: e.path, size: e.size, audioSidecarPath: e.audioSidecarPath, audioCompatMode: e.audioCompatMode, libraryId: item.id, category: item.category, epNum: Number(e.num) }));
  const index = Math.max(0, linked.findIndex(e => Number(e.num) === Number(epNum)));
  await player.open(tracks, { index, item, epNum: Number(epNum), startTime: start || 0 });
  return true;
}

export async function resumeItem(item) {
  const p = store.getProgress(item.id);
  if (p) return playEpisode(item, p.epNum, { startTime: p.time });
  const first = item.episodes.find(e => e.path && !store.isWatched(item.id, e.num)) || item.episodes.find(e => e.path);
  if (first) return playEpisode(item, first.num);
  return playEpisode(item, 1);
}

export async function linkEpisodeFile(item, epNum) {
  const files = await pickFiles({ kind: 'video', multiple: false });
  if (!files.length) return false;
  const f = files[0];
  if (!f.path) { toast('Browser-picked files cannot be linked; use the desktop app', { kind: 'err' }); return false; }
  taskOverlay('Linking file…', f.name);
  const res = await rpcSafe('link_media_files', item.title, [{ path: f.path }]);
  hideTask();
  const info = res?.files?.[0] || { path: f.path, name: f.name, size: f.size };
  applyLink(item, epNum, info);
  toast(`Episode ${epNum} linked`, { kind: 'ok' });
  return true;
}

export async function linkFolder(item) {
  const folder = await pickFolder();
  if (!folder) { return linkMultipleFiles(item); }
  const res = await getJSON(`/api/fs/list?path=${encodeURIComponent(folder)}&recursive=1`);
  const files = (res.files || []).filter(f => f.kind === 'video');
  if (!files.length) return toast('No video files in that folder', { kind: 'err' });
  return assignFiles(item, files);
}

export async function linkMultipleFiles(item) {
  const files = await pickFiles({ kind: 'video', multiple: true });
  if (!files.length) return false;
  if (files.some(f => !f.path)) return toast('Use the desktop app to link local files', { kind: 'err' });
  return assignFiles(item, files);
}

/** Map files → episodes with a review dialog before committing. */
async function assignFiles(item, files) {
  const rows = files.map(f => ({ f, ep: guessEpisode(f.name) })).sort((a, b) => (a.ep || 999) - (b.ep || 999));
  // Fill gaps sequentially for unmatched names.
  let next = 1;
  for (const r of rows) { if (!r.ep) { while (rows.some(x => x.ep === next)) next++; r.ep = next++; } }
  const list = h('.stack');
  const inputs = [];
  for (const r of rows) {
    const inp = h('input.input', { type: 'number', min: 1, value: r.ep, style: { width: '80px' } });
    inputs.push([r, inp]);
    list.appendChild(h('.list-row', h('span.muted.small', 'Ep'), h('.main', h('b', r.f.name), h('small', r.f.path)), inp));
  }
  const ok = await modal({ title: `Link ${rows.length} file(s) to "${item.title}"`, body: h('div', h('p.muted.small', { style: { marginBottom: '10px' } }, 'Episode numbers were guessed from file names. Fix any that are wrong.'), list), wide: true, actions: [{ label: 'Cancel', value: null, kind: 'ghost' }, { label: 'Link', value: true, kind: 'primary' }] });
  if (!ok) return false;
  taskOverlay('Linking files…', `${rows.length} file(s)`);
  const res = await rpcSafe('link_media_files', item.title, rows.map(r => ({ path: r.f.path })));
  hideTask();
  const infos = res?.files || rows.map(r => ({ path: r.f.path, name: r.f.name, size: r.f.size, source_path: r.f.path }));
  let n = 0;
  for (const [r, inp] of inputs) {
    const ep = Number(inp.value); if (!ep) continue;
    const info = infos.find(i => i.source_path === r.f.path || i.path === r.f.path) || { path: r.f.path, name: r.f.name, size: r.f.size };
    applyLink(item, ep, info, false); n++;
  }
  store.updateItem(item);
  toast(`${n} episode(s) linked`, { kind: 'ok' });
  return true;
}

function applyLink(item, epNum, info, save = true) {
  epNum = Number(epNum);
  let ep = item.episodes.find(e => Number(e.num) === epNum);
  if (!ep) { ep = { num: epNum }; item.episodes.push(ep); item.episodes.sort((a, b) => a.num - b.num); }
  if (epNum > item.episodes_count) item.episodes_count = epNum;
  Object.assign(ep, { path: info.path, name: info.name || baseName(info.path), size: info.size || 0, is_remuxed: !!info.is_remuxed, linked_directly: info.linked_directly !== false, audioSidecarPath: undefined, audioCompatMode: undefined });
  if (save) store.updateItem(item);
}

export function unlinkEpisode(item, epNum) {
  const ep = item.episodes.find(e => Number(e.num) === Number(epNum));
  if (!ep) return;
  Object.assign(ep, { path: '', name: '', size: 0, audioSidecarPath: undefined, audioCompatMode: undefined });
  store.updateItem(item);
}

export async function addToLibrary(catalogItem) {
  let full = catalogItem;
  if (!catalogItem._detailed) {
    const r = await meta.details(catalogItem.category, catalogItem.id).catch(() => null);
    if (r && r.status === 'success') full = { ...catalogItem, ...r.item, _detailed: true };
  }
  const item = store.addItem({ ...full, episodes_count: full.episodes || full.episodes_count || (full.category === 'movie' ? 1 : 0), episodes: [] });
  toast(`Added "${item.title}" to library`, { kind: 'ok' });
  return item;
}

export async function removeFromLibrary(item) {
  const ok = await confirm('Remove from library', `Remove "${item.title}"? Linked files stay on disk.`, { okLabel: 'Remove', danger: true });
  if (!ok) return false;
  store.removeItem(item.id, item.category);
  store.removeProgress(item.id);
  toast('Removed', { kind: 'ok' });
  return true;
}

export async function refreshMetadata(item) {
  const r = await meta.details(item.category, item.id).catch(() => null);
  if (!r || r.status !== 'success') return toast('Metadata refresh failed', { kind: 'err' });
  const fresh = r.item;
  const keep = { episodes: item.episodes, added_at: item.added_at };
  Object.assign(item, fresh, keep, { episodes_count: Math.max(item.episodes_count, fresh.episodes || 0) });
  Object.assign(item, normalizeItem(item, item.category));
  store.updateItem(item);
  toast('Metadata updated', { kind: 'ok' });
}

/** A media card used in library/catalog/home rows. */
export function mediaCard(item, { inLibrary = null, onClick, showProgress = true, sub } = {}) {
  const lib = inLibrary ?? store.inLibrary(item.id, item.category);
  const p = showProgress ? store.getProgress(item.id) : null;
  const poster = posterImg(item.poster, item.title);
  if (item.status === 'airing') poster.appendChild(h('.flag', { title: 'Airing' }));
  poster.appendChild(h('.play', h('span', icon('play', 18))));
  if (p && p.duration) poster.appendChild(h('.progress', h('i', { style: { width: `${Math.min(100, p.time / p.duration * 100)}%` } })));
  const kind = item.category === 'show' ? 'Series' : item.category === 'anime' ? 'Anime' : 'Movie';
  const eps = item.category === 'movie' ? null : (item.episodes_count ? `${item.episodes_count} ep` : (typeof item.episodes === 'number' && item.episodes ? `${item.episodes} ep` : null));
  const subText = sub ?? [kind, item.year, eps, item.score ? `★ ${item.score}` : null].filter(Boolean).join(' · ');
  const card = h('.card', { tabindex: 0, dataset: { id: item.id, category: item.category } }, poster, h('.meta', h('.title', item.title), h('.sub', subText)));
  card.addEventListener('click', () => onClick ? onClick(item) : (lib ? openTitle(store.findItem(item.id, item.category) || item) : openTitle(item)));
  card.addEventListener('keydown', (e) => { if (e.key === 'Enter') card.click(); });
  card.addEventListener('contextmenu', (e) => { e.preventDefault(); cardContextMenu(e, item); });
  return card;
}

export function cardContextMenu(e, item) {
  const lib = store.findItem(item.id, item.category);
  const items = [];
  if (lib) {
    items.push({ label: 'Continue watching', icon: 'play', onClick: () => resumeItem(lib) });
    items.push({ label: 'Open title page', icon: 'info', onClick: () => openTitle(lib) });
    items.push({ label: 'Link files…', icon: 'link', onClick: () => linkMultipleFiles(lib) });
    items.push({ label: 'Link folder…', icon: 'folder', onClick: () => linkFolder(lib) });
    items.push({ label: 'Refresh metadata', icon: 'refresh', onClick: () => refreshMetadata(lib) });
    items.push({ sep: true });
    items.push({ label: 'Mark all watched', icon: 'check', onClick: () => { lib.episodes.forEach(ep => store.setWatched(lib.id, ep.num, true)); store.removeProgress(lib.id); toast('Marked as watched'); } });
    items.push({ label: 'Remove from library', icon: 'trash', danger: true, onClick: () => removeFromLibrary(lib) });
  } else {
    items.push({ label: 'Add to library', icon: 'plus', onClick: () => addToLibrary(item) });
    items.push({ label: 'Details', icon: 'info', onClick: () => openTitle(item) });
  }
  contextMenu(e.clientX, e.clientY, items);
}

export function searchLibrary(query) {
  const q = String(query || '').toLowerCase().trim();
  if (!q) return store.allItems();
  return store.allItems().filter(i => [i.title, ...(i.all_titles || [])].some(t => String(t || '').toLowerCase().includes(q)));
}
