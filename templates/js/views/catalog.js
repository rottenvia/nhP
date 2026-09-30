import { h, icon, clear, renderList, debounce, smile } from '../core/dom.js';
import { meta } from '../core/api.js';
import { store } from '../core/store.js';
import { mediaCard, addToLibrary, openTitle } from '../features/libraryOps.js';
import { toast } from '../core/ui.js';

const CATS = [['anime', 'Anime'], ['movie', 'Movies'], ['show', 'Shows']];

export const catalogView = {
  id: 'catalog', title: 'Catalog', icon: 'search', rail: true,
  async mount(el) {
    let cat = store.prefs.catalogCategory || 'anime';
    let query = '';
    let seq = 0;
    let abort = null;
    const chips = h('.chips');
    const input = h('input.input', { placeholder: 'Search titles…', autofocus: true });
    const search = h('.search', icon('search'), input);
    const status = h('span.muted.small');
    const grid = h('.grid');
    const trendingSec = h('.section');
    const resultsSec = h('.section', { hidden: true }, h('.section-head', h('h2', 'Results'), status), grid);
    el.append(h('.view-inner', h('.toolbar', chips, h('.spacer'), search), resultsSec, trendingSec));

    const renderChips = () => { clear(chips); for (const [v, l] of CATS) chips.appendChild(h('button.chip', { class: v === cat ? 'is-active' : '', onClick: () => { cat = v; store.setPref('catalogCategory', v); renderChips(); query ? run() : loadTrending(); } }, l)); };

    const card = (item) => mediaCard(item, { showProgress: false, onClick: () => openTitle(store.findItem(item.id, item.category) || item) });

    const run = async () => {
      const q = query.trim();
      if (!q) { resultsSec.hidden = true; trendingSec.hidden = false; return; }
      const my = ++seq;
      abort?.abort(); abort = new AbortController();
      resultsSec.hidden = false; trendingSec.hidden = true;
      status.textContent = 'Searching…';
      let r;
      try { r = await meta.search(cat, q, abort.signal); } catch (e) { if (e.name === 'AbortError') return; r = { status: 'error', message: e.message, items: [] }; }
      if (my !== seq) return;
      const items = r.items || [];
      status.textContent = r.status === 'error' ? `Search failed: ${r.message}` : `${items.length} result${items.length === 1 ? '' : 's'}${r.cached ? ' · cached' : ''}`;
      renderList(grid, items, { key: i => `${i.category}:${i.id}`, create: card });
      if (!items.length && r.status !== 'error') { clear(grid); grid.appendChild(h('.empty', { style: { gridColumn: '1 / -1' } }, smile(), h('h3', 'No results'), h('p', 'Try the original title or another category.'))); }
    };
    input.addEventListener('input', debounce(() => { query = input.value; run(); }, 320));
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { query = input.value; run(); } });

    const trendingCache = new Map();
    const loadTrending = async () => {
      clear(trendingSec);
      trendingSec.append(h('.section-head', h('h2', cat === 'anime' ? 'Airing now' : 'Trending this week'), h('span.sub', cat === 'anime' ? 'MyAnimeList' : 'TMDB')));
      const g = h('.grid'); trendingSec.appendChild(g);
      if (!trendingCache.has(cat)) {
        for (let i = 0; i < 12; i++) g.appendChild(h('.skeleton', { style: { aspectRatio: '2/3' } }));
        const r = await meta.trending(cat).catch(() => ({ items: [] }));
        trendingCache.set(cat, r.items || []);
        if (r.status === 'error') toast('Trending unavailable: ' + r.message, { kind: 'err' });
      }
      const items = trendingCache.get(cat);
      clear(g);
      items.forEach(i => g.appendChild(card(i)));
      if (!items.length) g.appendChild(h('.empty', { style: { gridColumn: '1 / -1' } }, h('h3', 'Nothing to show'), h('p', 'Check your internet connection.')));
    };

    renderChips();
    loadTrending();
    return {
      show(p) { if (p?.query) { input.value = p.query; query = p.query; if (p.category) { cat = p.category; renderChips(); } run(); } setTimeout(() => input.focus(), 50); },
      refresh() { if (query) run(); else loadTrending(); },
    };
  },
};
