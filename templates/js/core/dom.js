// Tiny DOM toolkit: hyperscript, keyed list reconciliation, formatting helpers.

const SVG_NS = 'http://www.w3.org/2000/svg';
export const SMILEY_SVG = '<svg viewBox="0 0 24 24"><path d="M12.1 2.3 C17.3 2.1, 21.8 6.5, 21.9 11.9 C22.0 17.3, 17.1 21.9, 11.8 21.7 C6.4 21.5, 2.2 16.8, 2.3 11.4 C2.4 6.1, 6.9 2.5, 12.1 2.3"/><g class="eyes"><path d="M8.5 9.5 A 0.8 1 0 1 1 8.5 9.4" fill="currentColor"/><path d="M15.2 10.2 A 1 0.8 0 1 1 15.2 10.1" fill="currentColor"/></g><path d="M7.5 14.5 C9.2 17.2, 14.8 16.8, 16.5 13.8"/></svg>';
/** The smiley mark. cls: 'logo' (gradient tile) or 'smile' (plain stroke). */
export function smile(cls = 'smile', size = null) { const el = h('span', { class: cls, html: SMILEY_SVG }); if (size) { el.style.width = el.style.height = size + 'px'; } return el; }

/** h('div.cls#id', {attrs}, ...children) */
export function h(tag, attrs, ...children) {
  if (attrs && (attrs instanceof Node || typeof attrs !== 'object' || Array.isArray(attrs))) { children.unshift(attrs); attrs = null; }
  const m = /^([a-z0-9-]+)?((?:[.#][\w-]+)*)$/i.exec(tag) || [];
  const name = m[1] || 'div';
  const isSvg = name === 'svg' || name === 'path' || name === 'circle';
  const el = isSvg ? document.createElementNS(SVG_NS, name) : document.createElement(name);
  (m[2] || '').split(/(?=[.#])/).forEach(p => { if (p[0] === '.') el.classList.add(p.slice(1)); else if (p[0] === '#') el.id = p.slice(1); });
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === 'class' || k === 'className') { String(v).split(/\s+/).filter(Boolean).forEach(c => el.classList.add(c)); }
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'html') el.innerHTML = v;
    else if (k in el && !isSvg && k !== 'list' && k !== 'form') { try { el[k] = v; } catch { el.setAttribute(k, v); } }
    else el.setAttribute(k, v === true ? '' : v);
  }
  append(el, children);
  return el;
}

export function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

export function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function icon(name, size = 18) {
  const paths = ICONS[name] || ICONS.dot;
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', size); svg.setAttribute('height', size);
  svg.innerHTML = paths;
  return svg;
}

export const ICONS = {
  home: '<path d="M3 11l9-8 9 8v9a2 2 0 0 1-2 2h-4v-7H9v7H5a2 2 0 0 1-2-2z"/>',
  library: '<rect x="3" y="4" width="4" height="16" rx="1"/><rect x="10" y="4" width="4" height="16" rx="1"/><path d="M17 5l4 15-3 .8-4-15z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  play: '<path d="M7 4l13 8-13 8z"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  next: '<path d="M5 4l10 8-10 8z"/><rect x="17" y="4" width="2.5" height="16" rx="1"/>',
  prev: '<path d="M19 4L9 12l10 8z"/><rect x="4.5" y="4" width="2.5" height="16" rx="1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  download: '<path d="M12 3v12M6 11l6 6 6-6M4 21h16"/>',
  merge: '<path d="M6 3v6a6 6 0 0 0 6 6 6 6 0 0 0 6-6V3M12 15v6"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  check: '<path d="M5 12l5 5L20 7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  back: '<path d="M15 18l-6-6 6-6"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  more: '<circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/>',
  volume: '<path d="M4 10v4h4l5 4V6L8 10z"/><path d="M16 9a4 4 0 0 1 0 6M19 6.5a8 8 0 0 1 0 11"/>',
  mute: '<path d="M4 10v4h4l5 4V6L8 10z"/><path d="M17 9l4 6M21 9l-4 6"/>',
  fullscreen: '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>',
  minimize: '<path d="M9 4v5H4M20 9h-5V4M15 20v-5h5M4 15h5v5"/>',
  cc: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 10a2 2 0 1 0 0 4M16 10a2 2 0 1 0 0 4"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
  chat: '<path d="M12 3c4.97 0 9 3.58 9 8s-4.03 8-9 8c-.9 0-1.77-.12-2.6-.34L5 21l.9-3.6C4.1 15.9 3 13.6 3 11c0-4.42 4.03-8 9-8z"/>',
  bookmark: '<path d="M6 3h12v18l-6-4-6 4z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/>',
  tv: '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 21h8M12 17v4"/>',
  refresh: '<path d="M4 12a8 8 0 0 1 14-5.3L20 9M20 4v5h-5M20 12a8 8 0 0 1-14 5.3L4 15M4 20v-5h5"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="M3 3l18 18M10.6 10.6A2 2 0 0 0 13.4 13.4M9.9 5.1A10 10 0 0 1 22 12a17 17 0 0 1-3.2 3.9M6.4 6.4A17 17 0 0 0 2 12s4 7 10 7a9.7 9.7 0 0 0 4.3-1"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
  skip: '<path d="M5 4l10 8-10 8zM19 4v16"/>',
  star: '<path d="M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z"/>',
  sparkles: '<path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  dot: '<circle cx="12" cy="12" r="3"/>',
};

/**
 * Keyed reconciliation: reuses existing children by key, creates new ones,
 * removes stale ones, and keeps DOM order in sync. Avoids full innerHTML rebuilds.
 */
export function renderList(container, items, { key, create, update }) {
  const existing = new Map();
  for (const child of container.children) if (child.dataset.key != null) existing.set(child.dataset.key, child);
  const frag = document.createDocumentFragment();
  const next = [];
  for (const item of items) {
    const k = String(key(item));
    let el = existing.get(k);
    if (el) { existing.delete(k); if (update) update(el, item); }
    else { el = create(item); el.dataset.key = k; }
    next.push(el);
  }
  for (const stale of existing.values()) stale.remove();
  // Only touch the DOM where order differs.
  let i = 0;
  for (const el of next) {
    if (container.children[i] !== el) container.insertBefore(el, container.children[i] || null);
    i++;
  }
  return next;
}

export function fmtTime(sec, forceHours = false) {
  sec = Math.max(0, Math.floor(Number(sec) || 0));
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  const mm = String(m).padStart(2, '0'), ss = String(s).padStart(2, '0');
  return (h > 0 || forceHours) ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function fmtBytes(n) {
  n = Number(n) || 0;
  if (n < 1024) return `${n} B`;
  const u = ['KB', 'MB', 'GB', 'TB']; let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < u.length - 1);
  return `${n.toFixed(n >= 100 ? 0 : 1)} ${u[i]}`;
}

export function fmtAgo(ts) {
  const d = Date.now() - Number(ts || 0);
  if (!ts || d < 0) return '';
  const m = Math.floor(d / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const hrs = Math.floor(m / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(Number(ts)).toLocaleDateString();
}

export function debounce(fn, ms = 250) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export function throttle(fn, ms = 100) {
  let last = 0, timer = null, args = null;
  return (...a) => {
    args = a; const now = Date.now();
    if (now - last >= ms) { last = now; fn(...args); }
    else if (!timer) timer = setTimeout(() => { timer = null; last = Date.now(); fn(...args); }, ms - (now - last));
  };
}

export const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export function stripExt(name) {
  const s = String(name || '');
  const i = s.lastIndexOf('.');
  return i > 0 ? s.slice(0, i) : s;
}

export function baseName(path) {
  return String(path || '').split(/[\\/]/).pop();
}

/** Poster image with skeleton, lazy loading and graceful fallback. */
export function posterImg(src, alt = '') {
  const wrap = h('.poster');
  const fb = h('.fallback', { html: SMILEY_SVG });
  wrap.appendChild(fb);
  if (src) {
    const img = h('img', { alt, loading: 'lazy', decoding: 'async', referrerPolicy: 'no-referrer' });
    img.addEventListener('load', () => { img.classList.add('is-loaded'); fb.remove(); }, { once: true });
    img.addEventListener('error', () => { img.remove(); }, { once: true });
    img.src = src;
    wrap.appendChild(img);
  }
  return wrap;
}

export function guessEpisode(name) {
  const n = String(name || '');
  const pats = [/[sS]\d{1,2}[eE](\d{1,3})/, /(?:[eE][pP]?|[eE]pisode|серия|Серия)\s*[._-]?\s*(\d{1,3})/, /\s-\s(\d{1,3})\b/, /\[(\d{1,3})\]/, /\b(\d{1,3})\b(?!\d*p)/];
  for (const p of pats) { const m = n.match(p); if (m) { const v = parseInt(m[1], 10); if (v > 0 && v < 1000) return v; } }
  return null;
}
