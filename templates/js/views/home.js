import { h, icon, clear, renderList, fmtTime, fmtAgo } from '../core/dom.js';
import { store } from '../core/store.js';
import { router } from '../core/router.js';
import { pickFiles } from '../core/api.js';
import { mediaCard, resumeItem, playEpisode, openTitle } from '../features/libraryOps.js';
import { player } from '../player/player.js';

const VINYL = '<svg viewBox="0 0 24 24"><path d="M12.1 2.3 C17.3 2.1, 21.8 6.5, 21.9 11.9 C22.0 17.3, 17.1 21.9, 11.8 21.7 C6.4 21.5, 2.2 16.8, 2.3 11.4 C2.4 6.1, 6.9 2.5, 12.1 2.3"/><path d="M8.5 9.5 A 0.8 1 0 1 1 8.5 9.4" fill="currentColor"/><path d="M15.2 10.2 A 1 0.8 0 1 1 15.2 10.1" fill="currentColor"/><path d="M7.5 14.5 C9.2 17.2, 14.8 16.8, 16.5 13.8"/></svg>';

export const homeView = {
  id: 'home', title: 'Home', icon: 'home', rail: true,
  async mount(el) {
    const inner = h('.view-inner');
    el.appendChild(inner);
    const hero = h('.hero');
    const continueSec = h('.section');
    const recentSec = h('.section');
    const quick = h('.section', h('.section-head', h('h2', 'Quick actions')), h('.quick',
      qb('folder', 'Open files', 'Play any local video or audio', async () => { const f = await pickFiles({ multiple: true }); if (f.length) player.open(f, { index: 0 }); }),
      qb('search', 'Find a title', 'Search anime, movies and shows', () => router.go('catalog')),
      qb('download', 'Download RAW', 'Search torrents for an episode', () => router.go('downloads')),
      qb('merge', 'Merge a dub', 'Combine RAW video with a dub track', () => router.go('merger')),
      qb('chat', 'Ask :3', 'Let the assistant do it for you', () => document.dispatchEvent(new CustomEvent('assistant:toggle', { detail: true }))),
    ));
    inner.append(hero, continueSec, recentSec, quick);

    const render = () => {
      renderHero(hero);
      renderContinue(continueSec);
      renderRecent(recentSec);
    };
    render();
    store.on('library', render); store.on('progress', render); store.on('ready', render);
    player.addEventListener('state', () => hero.querySelector('.vinyl')?.classList.toggle('paused', player.video.paused));
    return { show: render, refresh: render };
  },
};

function qb(ic, title, sub, onClick) { return h('button.quick-btn', { onClick }, h('.ico', icon(ic, 20)), h('div', h('b', title), h('small', sub))); }

function renderHero(hero) {
  clear(hero);
  const prog = store.state.progress[0];
  const item = prog ? store.findItem(prog.id, prog.category) : null;
  const st = player.getState();
  if (st.open && st.track) {
    hero.append(h('.bg', { style: { backgroundImage: `url("${st.item?.backdrop || st.item?.poster || ''}")` } }),
      h('div', h('small.muted', 'Now playing'), h('h2', st.item ? st.item.title : st.track.name), h('p', st.item && st.epNum ? `Episode ${st.epNum} · ${fmtTime(st.time)} / ${fmtTime(st.duration)}` : fmtTime(st.time)),
        h('.actions', h('button.btn.primary', { onClick: () => player.expand() }, icon('fullscreen', 16), 'Open player'), h('button.btn.ghost', { onClick: () => player.toggle() }, icon(st.paused ? 'play' : 'pause', 16), st.paused ? 'Play' : 'Pause'))),
      h('.vinyl', { class: st.paused ? 'paused' : '', html: VINYL }));
    return;
  }
  if (item && prog) {
    const pct = prog.duration ? Math.round(prog.time / prog.duration * 100) : 0;
    hero.append(h('.bg', { style: { backgroundImage: `url("${item.backdrop || item.poster || ''}")` } }),
      h('div', h('small.muted', 'Continue watching'), h('h2', item.title), h('p', `Episode ${prog.epNum} · ${fmtTime(prog.time)} left off · ${pct}%`),
        h('.actions', h('button.btn.primary', { onClick: () => playEpisode(item, prog.epNum, { startTime: prog.time }) }, icon('play', 16), 'Resume'), h('button.btn.ghost', { onClick: () => openTitle(item) }, 'Title page'))),
      h('.vinyl.paused', { html: VINYL }));
    return;
  }
  hero.append(h('div', h('h2', 'Welcome back'), h('p', 'Open a file, search the catalog to build your library, or ask the assistant what to watch.'),
    h('.actions', h('button.btn.primary', { onClick: async () => { const f = await pickFiles({ multiple: true }); if (f.length) player.open(f, { index: 0 }); } }, icon('folder', 16), 'Open files'), h('button.btn.ghost', { onClick: () => router.go('catalog') }, icon('search', 16), 'Browse catalog'))),
    h('.vinyl.paused', { html: VINYL }));
}

function renderContinue(sec) {
  clear(sec);
  const list = store.state.progress.map(p => ({ p, item: store.findItem(p.id, p.category) })).filter(x => x.item).slice(0, 12);
  if (!list.length) return;
  sec.append(h('.section-head', h('h2', 'Continue watching'), h('button.btn.sm.ghost', { onClick: () => router.go('watching') }, 'See all')));
  const row = h('.row-scroll');
  for (const { p, item } of list) row.appendChild(mediaCard(item, { onClick: () => playEpisode(item, p.epNum, { startTime: p.time }), sub: `Ep ${p.epNum} · ${fmtTime(p.time)} · ${fmtAgo(p.timestamp)}` }));
  sec.appendChild(row);
}

function renderRecent(sec) {
  clear(sec);
  const items = store.allItems().sort((a, b) => (b.added_at || 0) - (a.added_at || 0)).slice(0, 14);
  sec.append(h('.section-head', h('h2', 'Library'), h('span.sub', `${store.allItems().length} titles`), h('button.btn.sm.ghost', { onClick: () => router.go('library') }, 'Open library')));
  if (!items.length) { sec.appendChild(h('.empty', h('.face', ':3'), h('h3', 'Your library is empty'), h('p', 'Search the catalog and add titles, then link your files.'), h('button.btn.primary', { onClick: () => router.go('catalog') }, 'Browse catalog'))); return; }
  const row = h('.row-scroll');
  items.forEach(i => row.appendChild(mediaCard(i)));
  sec.appendChild(row);
}
