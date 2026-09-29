// Watch Together (LAN sync room), TV mode (TV browser syncs to host) and live desktop stream.
import { h, icon, $, clear } from '../core/dom.js';
import { postJSON, getJSON, rpcSafe } from '../core/api.js';
import { toast, modal } from '../core/ui.js';
import { player } from '../player/player.js';

const state = { room: null, roomTimer: null, clients: 0, tvPin: null, tvTimer: null, live: null, liveTimer: null };

export function initShare() {
  $('#btn-share').addEventListener('click', openPanel);
  document.addEventListener('share:open', openPanel);
  player.addEventListener('state', () => { pushRoom('event'); pushTv(); });
}

function payload() {
  const st = player.getState();
  const has = st.open && st.track;
  return { title: has ? (st.item ? `${st.item.title} · Ep ${st.epNum || ''}` : st.track.name) : 'Waiting for host media', path: has ? (st.track.path || '') : '', duration: has ? st.duration : 0, time: has ? st.time : 0, paused: has ? st.paused : true, rate: has ? st.rate : 1 };
}

function pickUrl(data, prefer) {
  const urls = data.urls || [];
  const by = (re) => urls.find(u => re.test(String(u.ip || '')));
  if (prefer === 'lan') return (by(/^192\.168\./) || by(/^10\./) || by(/^172\./) || {}).url || data.lan_url || data.local_url;
  return (by(/^26\./) || by(/^100\./) || by(/^192\.168\./) || {}).url || data.lan_url || data.local_url;
}

async function createRoom() {
  const r = await postJSON('/api/watch/create', payload()).catch(e => ({ status: 'error', message: e.message }));
  if (r.status !== 'success') return toast('Room failed: ' + r.message, { kind: 'err' });
  state.room = r; state.clients = 0;
  const link = pickUrl(r, 'vpn');
  try { await navigator.clipboard.writeText(link); } catch {}
  toast('Room link copied', { kind: 'ok' });
  clearInterval(state.roomTimer);
  state.roomTimer = setInterval(async () => { pushRoom('tick'); const s = await getJSON(`/api/watch/state/${r.room}`).catch(() => null); const n = s?.room?.clients ? Object.keys(s.room.clients).length : 0; if (n !== state.clients) { state.clients = n; toast(`Watch Together: ${n} viewer(s)`); } }, 1000);
}
let lastPush = 0;
async function pushRoom(reason) { if (!state.room) return; const now = Date.now(); if (reason === 'event' && now - lastPush < 150) return; lastPush = now; postJSON(`/api/watch/update/${state.room.room}`, { ...payload(), reason }).catch(() => {}); }
function stopRoom() { clearInterval(state.roomTimer); state.roomTimer = null; state.room = null; }

async function createTv() {
  const st = player.getState();
  if (!st.open || !st.track?.path) return toast('Play a local file first');
  const r = await postJSON('/api/tv/create', payload()).catch(e => ({ status: 'error', message: e.message }));
  if (r.status !== 'success') return toast('TV mode failed: ' + r.message, { kind: 'err' });
  state.tvPin = r.pin; state.tv = r;
  try { await navigator.clipboard.writeText(pickUrl(r, 'lan')); } catch {}
  clearInterval(state.tvTimer); state.tvTimer = setInterval(pushTv, 500);
  toast(`TV PIN ${r.pin} · link copied`, { kind: 'ok' });
}
function pushTv() { if (!state.tvPin) return; postJSON(`/api/tv/update/${state.tvPin}`, payload()).catch(() => {}); }
function stopTv() { clearInterval(state.tvTimer); state.tvTimer = null; state.tvPin = null; state.tv = null; }

async function createLive() {
  const r = await postJSON('/api/live_stream/create', { title: 'Modern Player live' }).catch(e => ({ status: 'error', message: e.message }));
  if (r.status !== 'success') return toast('Live stream failed: ' + r.message, { kind: 'err' });
  state.live = r; toast('Live stream starting…');
}
async function stopLive() { if (state.live) await postJSON(`/api/live_stream/stop/${state.live.code}`).catch(() => {}); state.live = null; }

function openPanel() {
  const body = h('.stack');
  const render = () => {
    clear(body);
    body.append(section('Watch Together', 'Friends open a link (LAN, Radmin or Tailscale) and stay in sync with your playback. They need the same file locally, or download it from you.',
      state.room ? [row('Room ' + state.room.room, pickUrl(state.room, 'vpn')), h('.hstack', h('button.btn.sm', { onClick: () => copy(pickUrl(state.room, 'vpn')) }, 'Copy VPN link'), h('button.btn.sm', { onClick: () => copy(pickUrl(state.room, 'lan')) }, 'Copy LAN link'), h('button.btn.sm.danger', { onClick: () => { stopRoom(); render(); } }, 'Stop'))]
        : [h('button.btn.primary', { onClick: async () => { await createRoom(); render(); } }, icon('share', 16), 'Create room')]));
    body.append(section('TV mode', 'Open the link on a TV browser (same Wi-Fi). The TV plays the file directly and follows your play/pause/seek.',
      state.tvPin ? [row('PIN ' + state.tvPin, pickUrl(state.tv, 'lan')), h('.hstack', h('button.btn.sm', { onClick: () => copy(pickUrl(state.tv, 'lan')) }, 'Copy link'), h('button.btn.sm.danger', { onClick: () => { stopTv(); render(); } }, 'Stop'))]
        : [h('button.btn.primary', { onClick: async () => { await createTv(); render(); } }, icon('tv', 16), 'Start TV mode')]));
    body.append(section('Live desktop stream', 'Captures the screen into an HLS stream (Windows: gdigrab, needs ffmpeg). For casting or Chromecast.',
      state.live ? [row('Live', state.live.lan_url || state.live.local_url), h('.hstack', h('button.btn.sm', { onClick: () => copy(state.live.lan_url || state.live.local_url) }, 'Copy link'), h('button.btn.sm', { onClick: () => castDialog(state.live) }, 'Chromecast'), h('button.btn.sm.danger', { onClick: async () => { await stopLive(); render(); } }, 'Stop'))]
        : [h('button.btn', { onClick: async () => { await createLive(); render(); } }, icon('external', 16), 'Start live stream')]));
  };
  render();
  modal({ title: 'Share playback', body, wide: true, actions: [{ label: 'Close', value: null }] });
}

function section(title, text, children) { return h('.panel', h('h3', title), h('p.muted.small', { style: { marginBottom: '10px' } }, text), h('.stack', ...children)); }
function row(label, url) { return h('.list-row', h('b', label), h('span.small.ellipsis', { title: url }, url), h('span')); }
async function copy(text) { try { await navigator.clipboard.writeText(text); toast('Copied', { kind: 'ok' }); } catch { toast(text); } }

async function castDialog(live) {
  toast('Looking for Chromecast devices…');
  const r = await rpcSafe('chromecast_list_devices', 6);
  const devices = r?.devices || [];
  if (!devices.length) return toast('No devices found (pychromecast needed)', { kind: 'err' });
  const list = h('.stack', ...devices.map(d => h('button.option-card', { onClick: async () => { const url = (live.urls || []).find(u => /^192\.168\./.test(u.ip || ''))?.url || live.lan_url; const hls = url.replace('/live/', '/live_hls/') + '/index.m3u8'; const res = await rpcSafe('chromecast_play_url', d.id || d.uuid || d.name, hls, 'Modern Player'); toast(res?.status === 'success' ? 'Casting' : 'Cast failed', { kind: res?.status === 'success' ? 'ok' : 'err' }); } }, h('div', h('b', d.name || d.friendly_name), h('small', d.model || d.host || '')), icon('chevron'))));
  modal({ title: 'Cast to', body: list, actions: [{ label: 'Close', value: null }] });
}
