// Application state + persistence.
// The backend keeps JSON databases on disk; we hold them in memory here and
// write back (debounced, atomic on the Python side) whenever they change.

import { postJSON } from './api.js';

const listeners = new Map();
const state = {
  app: {},                // /api/boot app info
  settings: {},           // masked keys + merger config
  library: { movie: [], show: [], anime: [] },
  progress: [],           // continue watching
  history: [],            // viewing history
  playlist: [],
  playlistIndex: -1,
  watched: {},            // "id:ep" -> timestamp
  bookmarks: {},          // "id:ep" -> [{time,label}]
  prefs: {},              // player/user preferences
  skipMarkers: {},        // id -> {introStart,introEnd,outroStartOffset,outroSkipToEndOffset, [ep]: {...}}
  ready: false,
};

const DEFAULT_PREFS = {
  volume: 0.8, muted: false, speed: 1, aspect: 'contain',
  autoNext: true, skipIntroDefault: 85, outroOffset: 120, seekStep: 5,
  subtitleSize: 100, theme: 'dark', catalogCategory: 'anime', libraryCategory: 'all',
  miniPlayerOnBrowse: true, autoplayResume: true,
};

export const store = {
  get state() { return state; },
  get prefs() { return { ...DEFAULT_PREFS, ...state.prefs }; },

  on(key, fn) {
    if (!listeners.has(key)) listeners.set(key, new Set());
    listeners.get(key).add(fn);
    return () => listeners.get(key).delete(fn);
  },
  emit(key, payload) {
    (listeners.get(key) || []).forEach(fn => { try { fn(payload); } catch (e) { console.error('[store]', key, e); } });
    (listeners.get('*') || []).forEach(fn => { try { fn(key, payload); } catch (e) { console.error(e); } });
  },

  hydrate(boot) {
    state.app = boot.app || {};
    state.settings = boot.settings || {};
    const db = boot.databases || {};
    state.library = normalizeLibrary(db.library);
    state.progress = Array.isArray(db.watching_progress) ? db.watching_progress : [];
    state.history = Array.isArray(db.viewing_history) ? db.viewing_history : [];
    state.playlist = Array.isArray(db.playlist) ? db.playlist.filter(t => t && t.path) : [];
    state.playlistIndex = Number.isInteger(db.playlist_index) ? db.playlist_index : -1;
    state.watched = isObj(db.watched) ? db.watched : {};
    state.bookmarks = isObj(db.bookmarks) ? db.bookmarks : {};
    state.prefs = isObj(db.prefs) ? db.prefs : {};
    state.skipMarkers = isObj(db.skip_markers) ? db.skip_markers : {};
    migrateLocalStorage();
    state.ready = true;
    this.emit('ready');
  },

  // ---- library ----
  allItems() { return ['anime', 'show', 'movie'].flatMap(c => state.library[c] || []); },
  findItem(id, category) {
    const sid = String(id);
    if (category && state.library[category]) { const f = state.library[category].find(i => String(i.id) === sid); if (f) return f; }
    return this.allItems().find(i => String(i.id) === sid) || null;
  },
  inLibrary(id, category) { return !!this.findItem(id, category); },
  addItem(item) {
    const cat = item.category || 'anime';
    if (!state.library[cat]) state.library[cat] = [];
    if (this.findItem(item.id, cat)) return this.findItem(item.id, cat);
    const clean = normalizeItem({ ...item, added_at: Date.now() }, cat);
    state.library[cat].unshift(clean);
    this.saveLibrary();
    return clean;
  },
  removeItem(id, category) {
    for (const cat of Object.keys(state.library)) {
      if (category && cat !== category) continue;
      const before = state.library[cat].length;
      state.library[cat] = state.library[cat].filter(i => String(i.id) !== String(id));
      if (state.library[cat].length !== before) { this.saveLibrary(); return true; }
    }
    return false;
  },
  updateItem(item) { this.saveLibrary(); this.emit('item', item); },
  saveLibrary: debounced(() => persist('library', state.library), 400, () => store.emit('library')),

  // ---- progress / history / watched ----
  setProgress(entry) {
    state.progress = state.progress.filter(p => String(p.id) !== String(entry.id));
    state.progress.unshift(entry);
    state.progress = state.progress.slice(0, 30);
    this.saveProgress();
  },
  removeProgress(id) {
    const before = state.progress.length;
    state.progress = state.progress.filter(p => String(p.id) !== String(id));
    if (before !== state.progress.length) this.saveProgress();
  },
  getProgress(id) { return state.progress.find(p => String(p.id) === String(id)) || null; },
  saveProgress: debounced(() => persist('watching_progress', state.progress), 600, () => store.emit('progress')),

  addHistory(entry) {
    state.history = state.history.filter(x => !(String(x.id) === String(entry.id) && Number(x.epNum) === Number(entry.epNum)));
    state.history.unshift(entry);
    state.history = state.history.slice(0, 80);
    this.saveHistory();
  },
  removeHistory(index) { state.history.splice(index, 1); this.saveHistory(); },
  saveHistory: debounced(() => persist('viewing_history', state.history), 800, () => store.emit('history')),

  isWatched(id, ep) { return !!state.watched[`${id}:${ep}`]; },
  setWatched(id, ep, value = true) {
    const k = `${id}:${ep}`;
    if (value) state.watched[k] = Date.now(); else delete state.watched[k];
    this.saveWatched();
  },
  saveWatched: debounced(() => persist('watched', state.watched), 600, () => store.emit('watched')),

  getBookmarks(id, ep) { return state.bookmarks[`${id}:${ep}`] || []; },
  setBookmarks(id, ep, list) { state.bookmarks[`${id}:${ep}`] = list; this.saveBookmarks(); },
  saveBookmarks: debounced(() => persist('bookmarks', state.bookmarks), 500),

  // ---- playlist ----
  setPlaylist(list, index) {
    state.playlist = list; state.playlistIndex = index;
    this.savePlaylist();
  },
  savePlaylist: debounced(() => { persist('playlist', state.playlist); persist('playlist_index', state.playlistIndex); }, 800, () => store.emit('playlist')),

  // ---- prefs ----
  setPref(key, value) { state.prefs[key] = value; this.savePrefs(); },
  setPrefs(obj) { Object.assign(state.prefs, obj); this.savePrefs(); },
  savePrefs: debounced(() => persist('prefs', state.prefs), 500, () => store.emit('prefs')),

  getSkipMarkers(id, ep) {
    const item = state.skipMarkers[String(id)] || {};
    const p = store.prefs;
    const epm = (ep != null && item[String(ep)]) || {};
    return {
      introStart: Number(epm.introStart ?? item.introStart ?? 0),
      introEnd: Number(epm.introEnd ?? item.introEnd ?? p.skipIntroDefault ?? 85),
      outroStartOffset: Number(epm.outroStartOffset ?? item.outroStartOffset ?? p.outroOffset ?? 120),
      outroSkipToEndOffset: Number(epm.outroSkipToEndOffset ?? item.outroSkipToEndOffset ?? 5),
    };
  },
  setSkipMarkers(id, markers, ep = null) {
    const key = String(id);
    state.skipMarkers[key] = state.skipMarkers[key] || {};
    if (ep != null) state.skipMarkers[key][String(ep)] = { ...(state.skipMarkers[key][String(ep)] || {}), ...markers };
    else Object.assign(state.skipMarkers[key], markers);
    this.saveSkipMarkers();
  },
  saveSkipMarkers: debounced(() => persist('skip_markers', state.skipMarkers), 500),
};

function isObj(v) { return v && typeof v === 'object' && !Array.isArray(v); }

function debounced(fn, ms, after) {
  let t;
  return () => { clearTimeout(t); t = setTimeout(() => { fn(); if (after) after(); }, ms); if (after) after(); };
}

async function persist(key, data) {
  try {
    await postJSON('/api/save_db_data', { key, data: JSON.stringify(data) });
  } catch (e) {
    console.warn('[store] persist failed', key, e.message);
  }
}

export function normalizeLibrary(lib) {
  const out = { movie: [], show: [], anime: [] };
  if (!isObj(lib)) return out;
  for (const cat of Object.keys(out)) {
    const arr = Array.isArray(lib[cat]) ? lib[cat] : [];
    const seen = new Set();
    for (const raw of arr) {
      if (!raw || raw.id == null) continue;
      const k = String(raw.id);
      if (seen.has(k)) continue;
      seen.add(k);
      out[cat].push(normalizeItem(raw, cat));
    }
  }
  return out;
}

export function normalizeItem(raw, cat) {
  const item = { ...raw };
  item.category = cat || item.category || 'anime';
  item.title = item.title || item.name || 'Untitled';
  item.all_titles = Array.isArray(item.all_titles) ? item.all_titles : [item.title];
  item.poster = item.poster || '';
  item.backdrop = item.backdrop || '';
  item.synopsis = /^(russian synopsis|synopsis of|описание)/i.test(String(item.synopsis || '').trim()) ? '' : (item.synopsis || '');
  item.status = normalizeStatus(item.status);
  item.genres = Array.isArray(item.genres) ? item.genres : (typeof item.genres_str === 'string' && item.genres_str && !/genre/i.test(item.genres_str) ? item.genres_str.split(/,\s*/) : []);
  item.studio = item.studio || (typeof item.studios_str === 'string' && !/studio \//i.test(item.studios_str) ? item.studios_str : '') || '';
  item.year = item.year || (item.aired_from ? Number(String(item.aired_from).slice(0, 4)) : null) || null;
  item.type = item.type || (item.category === 'movie' ? 'Movie' : 'TV');
  const eps = Array.isArray(item.episodes) ? item.episodes.filter(e => e && Number(e.num) > 0) : [];
  const count = Math.max(Number(item.episodes_count) || 0, eps.length, item.category === 'movie' ? 1 : 0);
  item.episodes_count = count;
  // Keep the episode list dense (1..count) so linking is always possible.
  const byNum = new Map(eps.map(e => [Number(e.num), e]));
  const dense = [];
  for (let n = 1; n <= count; n++) dense.push(byNum.get(n) || { num: n, path: '', name: '' });
  for (const [n, e] of byNum) if (n > count) dense.push(e);
  item.episodes = dense.sort((a, b) => Number(a.num) - Number(b.num));
  delete item.chronology; delete item.aiFranchisePlan; delete item.franchiseHub;
  return item;
}

function normalizeStatus(s) {
  const v = String(s || '').toLowerCase();
  if (!v) return 'unknown';
  if (v.includes('airing') && !v.includes('not') && !v.includes('finished')) return 'airing';
  if (v.includes('not yet') || v.includes('upcoming') || v.includes('planned')) return 'upcoming';
  if (v.includes('finished') || v.includes('released') || v.includes('ended') || v.includes('complete')) return 'finished';
  if (v === 'airing' || v === 'upcoming' || v === 'finished') return v;
  return v;
}

/** One-time import of the old UI's localStorage flags. */
function migrateLocalStorage() {
  try {
    if (localStorage.getItem('mp2_migrated')) return;
    let changed = false;
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      let m;
      if ((m = /^watched_(\d+)_(\d+)$/.exec(k))) { state.watched[`${m[1]}:${m[2]}`] = state.watched[`${m[1]}:${m[2]}`] || Date.now(); changed = true; }
      else if ((m = /^bookmarks_(\d+)_(\d+)$/.exec(k))) {
        try { const list = JSON.parse(localStorage.getItem(k)); if (Array.isArray(list) && !state.bookmarks[`${m[1]}:${m[2]}`]) { state.bookmarks[`${m[1]}:${m[2]}`] = list; changed = true; } } catch {}
      }
    }
    if (changed) { persist('watched', state.watched); persist('bookmarks', state.bookmarks); }
    localStorage.setItem('mp2_migrated', '1');
  } catch {}
}
