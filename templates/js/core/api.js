// Thin client for the local backend. Everything goes over HTTP, so the UI never
// depends on pywebview's JS bridge being ready.

const ORIGIN = (location.origin && location.origin.startsWith('http')) ? location.origin : 'http://127.0.0.1:8765';

export function mediaUrl(path) {
  return `${ORIGIN}/media?path=${encodeURIComponent(path)}`;
}

export async function getJSON(url, { signal, timeout = 20000 } = {}) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  if (signal) signal.addEventListener('abort', () => ctrl.abort(), { once: true });
  try {
    const r = await fetch(url, { cache: 'no-store', signal: ctrl.signal });
    const data = await r.json().catch(() => ({}));
    if (!r.ok && !data.status) throw new Error(`HTTP ${r.status}`);
    return data;
  } finally {
    clearTimeout(t);
  }
}

export async function postJSON(url, body, { timeout = 0 } = {}) {
  const ctrl = new AbortController();
  const t = timeout ? setTimeout(() => ctrl.abort(), timeout) : null;
  try {
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}), signal: ctrl.signal });
    const data = await r.json().catch(() => ({}));
    if (!r.ok && !data.status) throw new Error(`HTTP ${r.status}`);
    return data;
  } finally {
    if (t) clearTimeout(t);
  }
}

/** Call any public PlayerAPI method. Returns the (JSON-parsed) result or throws. */
export async function rpc(method, ...args) {
  const data = await postJSON('/api/rpc', { method, args });
  if (data.status !== 'success') throw new Error(data.message || `${method} failed`);
  return data.result;
}

/** Same as rpc but never throws; returns null on failure. */
export async function rpcSafe(method, ...args) {
  try { return await rpc(method, ...args); } catch (e) { console.warn('[rpc]', method, e.message); return null; }
}

export const meta = {
  search: (category, q, signal) => getJSON(`/api/meta/search?category=${encodeURIComponent(category)}&q=${encodeURIComponent(q)}`, { signal }),
  details: (category, id) => getJSON(`/api/meta/details?category=${encodeURIComponent(category)}&id=${encodeURIComponent(id)}`),
  trending: (category) => getJSON(`/api/meta/trending?category=${encodeURIComponent(category)}`),
  relations: (id) => getJSON(`/api/meta/relations?id=${encodeURIComponent(id)}`),
  episodes: (id, page = 1) => getJSON(`/api/meta/episodes?id=${encodeURIComponent(id)}&page=${page}`),
  season: (id, season) => getJSON(`/api/meta/season?id=${encodeURIComponent(id)}&season=${season}`),
  franchise: (id) => getJSON(`/api/meta/franchise?id=${encodeURIComponent(id)}`, { timeout: 60000 }),
};

/** Server-sent events over a POST body (the assistant stream). */
export async function streamJSON(url, body, onEvent) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!r.ok || !r.body) throw new Error(`HTTP ${r.status}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
      const line = chunk.split('\n').find(l => l.startsWith('data: '));
      if (!line) continue;
      try { onEvent(JSON.parse(line.slice(6))); } catch (e) { console.warn('[sse] bad event', e); }
    }
  }
}

/** Native dialogs through the backend; falls back to browser pickers when no desktop window exists. */
export async function pickFiles({ kind = 'media', multiple = true } = {}) {
  let res = null;
  try { res = await rpc('dialog_open_files', kind, multiple); } catch (e) { res = null; }
  if (Array.isArray(res) && res.length) return res;
  if (Array.isArray(res) && window.__hasWindow) return [];
  return browserPick({ kind, multiple });
}

export async function pickFolder() {
  try {
    const r = await rpc('dialog_open_folder');
    return r && r.path ? r.path : '';
  } catch (e) { return ''; }
}

function browserPick({ kind, multiple }) {
  return new Promise(resolve => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = !!multiple;
    input.accept = kind === 'subtitle' ? '.srt,.vtt,.ass' : (kind === 'video' ? 'video/*,.mkv,.ts' : 'video/*,audio/*,.mkv,.ts');
    input.style.display = 'none';
    document.body.appendChild(input);
    input.onchange = () => {
      const files = [...input.files].map(f => ({ path: f.path || '', name: f.name, size: f.size, file: f, kind: f.type.startsWith('audio') ? 'audio' : (kind === 'subtitle' ? 'subtitle' : 'video'), isTS: f.name.toLowerCase().endsWith('.ts') }));
      input.remove();
      resolve(files);
    };
    input.oncancel = () => { input.remove(); resolve([]); };
    input.click();
  });
}
