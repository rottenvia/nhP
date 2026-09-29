// :3 assistant drawer. Streams agent events and executes UI commands the agent queues.
import { h, icon, $, clear } from '../core/dom.js';
import { getJSON, postJSON, streamJSON } from '../core/api.js';
import { store } from '../core/store.js';
import { router } from '../core/router.js';
import { toast } from '../core/ui.js';
import { player } from '../player/player.js';
import { playEpisode, openTitle, addToLibrary } from './libraryOps.js';

const root = $('#assistant');
let open = false;
let busy = false;
let msgs, input, chips, headSub;

const CHIPS = ['What should I watch next?', 'Continue my last episode', 'Find RAW for the newest episode in my library', 'Scan raw/ and dub/ and merge everything', 'Recommend something like what I watch'];

export function initAssistant() {
  build();
  document.addEventListener('assistant:toggle', (e) => toggle(e.detail));
  document.addEventListener('assistant:reload', () => loadHistory());
  document.addEventListener('assistant:ask', (e) => { toggle(true); send(e.detail); });
  $('#rail-assistant').addEventListener('click', () => toggle());
  document.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); toggle(); } });
  loadHistory();
}

function build() {
  msgs = h('.a-msgs');
  chips = h('.a-chips');
  input = h('textarea.input', { placeholder: 'Ask :3 to play, find, download or merge something…', rows: 1 });
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input.value); } });
  input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(140, input.scrollHeight) + 'px'; });
  headSub = h('small', 'Loading…');
  root.append(
    h('.a-head', h('.face', ':3'), h('.grow', h('b', 'Assistant'), headSub), h('button.icon-btn', { title: 'Settings', onClick: () => router.go('settings', { section: 'ai' }) }, icon('settings', 16)), h('button.icon-btn', { title: 'Close', onClick: () => toggle(false) }, icon('x', 16))),
    msgs, chips,
    h('.a-input', input, h('button.btn.primary.icon', { title: 'Send', onClick: () => send(input.value) }, icon('chevron', 18))),
  );
  for (const c of CHIPS) chips.appendChild(h('button.chip', { onClick: () => send(c) }, c));
}

export function toggle(force) {
  open = force ?? !open;
  root.hidden = !open;
  $('#rail-assistant').classList.toggle('is-active', open);
  if (open) setTimeout(() => input.focus(), 60);
}

async function loadHistory() {
  const r = await getJSON('/api/assistant/history').catch(() => null);
  clear(msgs);
  const cfg = r?.config || {};
  headSub.textContent = cfg.has_key || cfg.provider === 'custom' ? `${cfg.provider} · ${cfg.model}` : 'Not configured';
  if (!cfg.has_key && cfg.provider !== 'custom') {
    msgs.appendChild(h('.a-setup', 'No AI provider yet. ', h('a', { href: '#', onClick: (e) => { e.preventDefault(); router.go('settings', { section: 'ai' }); } }, 'Open Settings → AI'), ' and add an OpenAI, DeepSeek, OpenRouter, Groq or local endpoint key.'));
  }
  const list = r?.messages || [];
  if (!list.length) addMsg('bot', 'Hi. I can play things from your library, search the catalog, find and download RAW releases, run the merger, and remember your preferences. What do you want?');
  for (const m of list.slice(-30)) addMsg(m.role === 'user' ? 'user' : 'bot', m.content);
  scroll();
}

function addMsg(kind, text) { const el = h('.msg', { class: kind }, text); msgs.appendChild(el); scroll(); return el; }
function scroll() { msgs.scrollTop = msgs.scrollHeight; }

function context() {
  const st = player.getState();
  return {
    view: router.current,
    now_playing: st.open ? { title: st.item?.title || st.track?.name, episode: st.epNum, time: Math.round(st.time), duration: Math.round(st.duration), paused: st.paused } : null,
    current_title: window.__currentTitle || null,
    platform: navigator.platform,
    language: navigator.language,
  };
}

async function send(text) {
  text = String(text || '').trim();
  if (!text || busy) return;
  busy = true;
  input.value = ''; input.style.height = 'auto';
  addMsg('user', text);
  const thinking = h('.msg.thinking', h('i'), h('i'), h('i'));
  msgs.appendChild(thinking); scroll();
  const toolEls = new Map();
  try {
    await streamJSON('/api/assistant/chat?stream=1', { message: text, context: context() }, (ev) => {
      if (ev.type === 'tool_call') { const el = h('.msg.tool', h('.spinner'), h('span', describeTool(ev.name, ev.args))); msgs.insertBefore(el, thinking); toolEls.set(ev.name + JSON.stringify(ev.args), el); scroll(); }
      else if (ev.type === 'tool_result') { const el = [...toolEls.values()].reverse().find(e => !e.dataset.done); if (el) { el.dataset.done = 1; el.classList.add(ev.ok ? 'ok' : 'err'); el.querySelector('.spinner')?.replaceWith(icon(ev.ok ? 'check' : 'x', 12)); } }
      else if (ev.type === 'ui') { for (const c of ev.commands || []) runCommand(c); }
      else if (ev.type === 'answer') { thinking.remove(); addMsg('bot', ev.text); }
      else if (ev.type === 'error') { thinking.remove(); addMsg('error', ev.text); }
    });
  } catch (e) {
    thinking.remove();
    addMsg('error', 'Request failed: ' + e.message);
  } finally {
    thinking.remove();
    busy = false;
    input.focus();
  }
}

function describeTool(name, args = {}) {
  const map = {
    get_app_state: 'checking app state', search_library: `searching library for "${args.query}"`, get_library_item: 'reading title', search_catalog: `searching ${args.category} catalog for "${args.query}"`,
    add_to_library: 'adding to library', play: `starting playback${args.episode ? ' · episode ' + args.episode : ''}`, player_control: `player: ${args.action}`, navigate: `opening ${args.view}`, open_title_page: 'opening title page',
    get_watching_progress: 'reading watch progress', search_torrents: `searching torrents for "${args.query}"`, download_torrent: 'adding torrent', torrent_status: 'checking downloads',
    merger_scan: 'scanning raw/ and dub/', merger_merge_all: 'merging all pairs', merger_import_downloads: 'importing downloads', open_dub_browser: 'opening DUB browser', dub_provider: `dub provider: ${args.action}`, web_search: `searching the web for "${args.query}"`, open_folder: 'opening folder', remember: 'remembering that',
  };
  return map[name] || name;
}

/** UI commands queued by the agent's tools. */
async function runCommand(c) {
  try {
    switch (c.type) {
      case 'navigate': router.go(c.view, c.section ? { section: c.section } : {}); break;
      case 'library.add': { const added = await addToLibrary({ ...c.item, _detailed: true }); router.refresh('library'); break; }
      case 'open_title': { const item = store.findItem(c.id); if (item) openTitle(item); break; }
      case 'player.play_library': {
        const item = store.findItem(c.id); if (!item) { toast('Title not in library'); break; }
        const prog = store.getProgress(item.id);
        const ep = c.episode || (c.resume && prog ? prog.epNum : null) || item.episodes.find(e => e.path && !store.isWatched(item.id, e.num))?.num || 1;
        await playEpisode(item, ep, { startTime: c.episode ? null : (prog && prog.epNum === ep ? prog.time : null) });
        break;
      }
      case 'player.control': {
        const v = player.video; const st = player.getState();
        if (!st.open && ['play', 'toggle'].includes(c.action)) { const p = store.state.progress[0]; const item = p && store.findItem(p.id); if (item) playEpisode(item, p.epNum, { startTime: p.time }); break; }
        const actions = { play: () => v.play(), pause: () => v.pause(), toggle: () => player.toggle(), next: () => player.next(), prev: () => player.prev(), seek: () => player.seekTo(Number(c.value) || 0), volume: () => player.setVolume((Number(c.value) || 0) / 100), speed: () => player.setSpeed(Number(c.value) || 1), fullscreen: () => player.toggleFullscreen(), subtitles_toggle: () => player.toggleSubs() };
        actions[c.action]?.(); break;
      }
      case 'downloads.refresh': router.refresh('downloads'); break;
      default: console.warn('[assistant] unknown ui command', c);
    }
  } catch (e) { console.error('[assistant] command failed', c, e); }
}
