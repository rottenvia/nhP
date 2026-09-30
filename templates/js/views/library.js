import { h, icon, clear, renderList, debounce, append, smile } from '../core/dom.js';
import { store } from '../core/store.js';
import { router } from '../core/router.js';
import { mediaCard, searchLibrary } from '../features/libraryOps.js';

const CATS = [['all', 'All'], ['anime', 'Anime'], ['show', 'Shows'], ['movie', 'Movies']];
const SORTS = [['added', 'Recently added'], ['title', 'Title'], ['progress', 'In progress first'], ['year', 'Year']];

export const libraryView = {
  id: 'library', title: 'Library', icon: 'library', rail: true,
  async mount(el) {
    let cat = store.prefs.libraryCategory || 'all';
    let sort = store.prefs.librarySort || 'added';
    let query = '';
    const chips = h('.chips');
    const search = h('.search', icon('search'), h('input.input', { placeholder: 'Filter library…', onInput: debounce((e) => { query = e.target.value; render(); }, 120) }));
    const sortSel = h('select.select', { style: { width: '180px' }, onChange: (e) => { sort = e.target.value; store.setPref('librarySort', sort); render(); } }, ...SORTS.map(([v, l]) => h('option', { value: v, selected: v === sort }, l)));
    const grid = h('.grid');
    const empty = h('.empty', { hidden: true });
    el.append(h('.view-inner', h('.toolbar', chips, h('.spacer'), search, sortSel), grid, empty));

    const renderChips = () => {
      clear(chips);
      for (const [v, l] of CATS) {
        const n = v === 'all' ? store.allItems().length : (store.state.library[v] || []).length;
        chips.appendChild(h('button.chip', { class: v === cat ? 'is-active' : '', onClick: () => { cat = v; store.setPref('libraryCategory', v); render(); } }, l, h('span.count', String(n))));
      }
    };
    const render = () => {
      renderChips();
      let items = searchLibrary(query).filter(i => cat === 'all' || i.category === cat);
      const prog = new Map(store.state.progress.map(p => [String(p.id), p.timestamp]));
      items = items.slice().sort((a, b) => {
        if (sort === 'title') return a.title.localeCompare(b.title);
        if (sort === 'year') return (b.year || 0) - (a.year || 0);
        if (sort === 'progress') return (prog.get(String(b.id)) || 0) - (prog.get(String(a.id)) || 0) || (b.added_at || 0) - (a.added_at || 0);
        return (b.added_at || 0) - (a.added_at || 0);
      });
      renderList(grid, items, { key: i => `${i.category}:${i.id}`, create: i => mediaCard(i), update: (el, i) => { const fresh = mediaCard(i); el.replaceChildren(...fresh.childNodes); } });
      empty.hidden = items.length > 0;
      if (!items.length) { clear(empty); append(empty, [smile(), h('h3', query ? 'Nothing matches' : 'Library is empty'), h('p', query ? 'Try another name.' : 'Add titles from the catalog.'), query ? null : h('button.btn.primary', { onClick: () => router.go('catalog') }, 'Browse catalog')]); }
    };
    render();
    store.on('library', render); store.on('progress', render);
    return { show: (p) => { if (p?.query != null) { search.querySelector('input').value = p.query; query = p.query; } render(); }, refresh: render };
  },
};
