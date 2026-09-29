import { h, icon, clear, renderList, fmtTime, fmtAgo } from '../core/dom.js';
import { store } from '../core/store.js';
import { playEpisode, openTitle } from '../features/libraryOps.js';
import { contextMenu, toast } from '../core/ui.js';

export const watchingView = {
  id: 'watching', title: 'Watching', icon: 'clock', rail: true,
  async mount(el) {
    const cont = h('.list');
    const sched = h('.list');
    const hist = h('.list');
    el.append(h('.view-inner', h('.cols-3',
      h('.panel', h('h3', 'Continue watching'), cont),
      h('.panel', h('h3', 'Release schedule'), sched),
      h('.panel', h('h3', 'History'), hist))));
    let timer = null;

    const renderContinue = () => {
      const list = store.state.progress.map(p => ({ p, item: store.findItem(p.id, p.category) })).filter(x => x.item);
      renderList(cont, list, {
        key: x => x.p.id,
        create: ({ p, item }) => {
          const pct = p.duration ? Math.min(100, p.time / p.duration * 100) : 0;
          const card = h('.continue-card', { onClick: () => playEpisode(item, p.epNum, { startTime: p.time }) },
            h('img', { src: item.poster, loading: 'lazy', alt: '' }),
            h('.body', h('b', item.title), h('small.muted', `Episode ${p.epNum} of ${item.episodes_count || p.episodesCount || '?'}`), h('.progress-bar', h('i', { style: { width: pct + '%' } })), h('.foot', h('span', `${fmtTime(p.time)} / ${fmtTime(p.duration)}`), h('span', fmtAgo(p.timestamp)))));
          card.addEventListener('contextmenu', (e) => { e.preventDefault(); contextMenu(e.clientX, e.clientY, [
            { label: 'Resume', icon: 'play', onClick: () => playEpisode(item, p.epNum, { startTime: p.time }) },
            { label: 'Start episode over', icon: 'refresh', onClick: () => playEpisode(item, p.epNum, { startTime: 0 }) },
            { label: 'Title page', icon: 'info', onClick: () => openTitle(item) },
            { sep: true }, { label: 'Remove from list', icon: 'x', danger: true, onClick: () => store.removeProgress(p.id) }]); });
          return card;
        },
      });
      if (!list.length) { clear(cont); cont.appendChild(h('.empty', h('h3', 'Nothing in progress'), h('p', 'Episodes you start will show up here.'))); }
    };

    const renderSchedule = () => {
      const now = Date.now();
      const items = store.allItems().filter(i => i.status === 'airing' || i.next_episode?.air_date).map(i => ({ i, next: nextAir(i) })).filter(x => x.next).sort((a, b) => a.next - b.next);
      renderList(sched, items, {
        key: x => x.i.id,
        create: ({ i, next }) => h('.list-row', { onClick: () => openTitle(i) }, h('img.thumb', { src: i.poster, loading: 'lazy', alt: '' }), h('.main', h('b', i.title), h('small', i.next_episode?.episode_number ? `Episode ${i.next_episode.episode_number}` : (i.broadcast || 'Weekly'))), h('span.countdown', countdown(next - now))),
        update: (el, { next }) => { el.querySelector('.countdown').textContent = countdown(next - now); },
      });
      if (!items.length) { clear(sched); sched.appendChild(h('.empty', h('h3', 'No airing titles'), h('p', 'Airing anime and returning shows in your library appear here with a countdown.'))); }
    };

    const renderHistory = () => {
      const list = store.state.history.slice(0, 60);
      renderList(hist, list, {
        key: x => `${x.id}:${x.epNum}:${x.timestamp}`,
        create: (x) => { const item = store.findItem(x.id, x.category); return h('.list-row', { onClick: () => item ? playEpisode(item, x.epNum, { startTime: x.time }) : toast('Title no longer in library') }, h('img.thumb', { src: item?.poster || x.poster || '', loading: 'lazy', alt: '' }), h('.main', h('b', x.title), h('small', `Episode ${x.epNum} · ${fmtTime(x.time)} · ${fmtAgo(x.timestamp)}`)), h('button.icon-btn', { title: 'Remove', onClick: (e) => { e.stopPropagation(); const idx = store.state.history.indexOf(x); if (idx >= 0) store.removeHistory(idx); } }, icon('x', 16))); },
      });
      if (!list.length) { clear(hist); hist.appendChild(h('.empty', h('h3', 'No history yet'))); }
    };

    const render = () => { renderContinue(); renderSchedule(); renderHistory(); };
    store.on('progress', renderContinue); store.on('history', renderHistory); store.on('library', render);
    return {
      show() { render(); clearInterval(timer); timer = setInterval(renderSchedule, 30000); },
      hide() { clearInterval(timer); timer = null; },
      refresh: render,
    };
  },
};

function nextAir(item) {
  if (item.next_episode?.air_date) { const t = new Date(item.next_episode.air_date).getTime(); if (t > Date.now() - 86400000) return t; }
  // Weekly anime: derive from broadcast string like "Sundays at 17:00 (JST)".
  const m = /(Mondays|Tuesdays|Wednesdays|Thursdays|Fridays|Saturdays|Sundays)(?: at (\d{2}):(\d{2}))?/i.exec(item.broadcast || '');
  if (!m) return item.status === 'airing' ? null : null;
  const days = ['sundays', 'mondays', 'tuesdays', 'wednesdays', 'thursdays', 'fridays', 'saturdays'];
  const target = days.indexOf(m[1].toLowerCase());
  const hh = Number(m[2] || 0), mm = Number(m[3] || 0);
  // JST -> local
  const now = new Date();
  const jst = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60000);
  const d = new Date(jst); d.setHours(hh, mm, 0, 0);
  let diff = (target - jst.getDay() + 7) % 7;
  if (diff === 0 && d.getTime() < jst.getTime()) diff = 7;
  d.setDate(d.getDate() + diff);
  return d.getTime() - (9 * 60 + now.getTimezoneOffset()) * 60000;
}

function countdown(ms) {
  if (ms <= 0) return 'now';
  const d = Math.floor(ms / 86400000), hh = Math.floor(ms % 86400000 / 3600000), m = Math.floor(ms % 3600000 / 60000);
  return d > 0 ? `${d}d ${hh}h` : `${hh}h ${m}m`;
}
