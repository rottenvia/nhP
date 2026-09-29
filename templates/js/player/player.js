// The player. One instance, lives in #player as an overlay above the app so
// navigating around never interrupts playback (it docks into a mini player).

import { h, icon, $, fmtTime, stripExt, baseName, clear, renderList, throttle } from '../core/dom.js';
import { mediaUrl, rpc, rpcSafe, pickFiles } from '../core/api.js';
import { store } from '../core/store.js';
import { toast, modal, taskOverlay, hideTask, prompt as promptDialog } from '../core/ui.js';
import { parseSubtitles, cueAt } from './subtitles.js';
import { Sidecar } from './sidecar.js';

const SPEEDS = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
const VINYL_SVG = '<svg viewBox="0 0 24 24"><path d="M12.1 2.3 C17.3 2.1, 21.8 6.5, 21.9 11.9 C22.0 17.3, 17.1 21.9, 11.8 21.7 C6.4 21.5, 2.2 16.8, 2.3 11.4 C2.4 6.1, 6.9 2.5, 12.1 2.3"/><path d="M8.5 9.5 A 0.8 1 0 1 1 8.5 9.4" fill="currentColor"/><path d="M15.2 10.2 A 1 0.8 0 1 1 15.2 10.1" fill="currentColor"/><path d="M7.5 14.5 C9.2 17.2, 14.8 16.8, 16.5 13.8"/></svg>';

class Player extends EventTarget {
  constructor() {
    super();
    this.root = $('#player');
    this.playlist = [];
    this.index = -1;
    this.track = null;
    this.item = null;       // library item, when playing an episode
    this.epNum = null;
    this.mode = 'closed';   // closed | full | mini
    this.mpegts = null;
    this.duration = 0;      // authoritative duration (PTS scan for .ts)
    this.cues = null;
    this.subsOn = false;
    this.skipDismissed = false;
    this.nextTimer = null;
    this.lastSave = 0;
    this.uiTimer = null;
    this.loadToken = 0;
    this.blobUrl = null;
    this.build();
    this.sidecar = new Sidecar(this.video);
    this.bind();
  }

  // ───────────────────────── DOM ─────────────────────────
  build() {
    const r = this.root;
    r.innerHTML = '';
    this.video = h('video', { playsinline: true, preload: 'auto' });
    this.audioArt = h('.audio-art', { hidden: true }, h('.vinyl', { html: VINYL_SVG }), h('h2'), h('p'));
    this.subsEl = h('.subs', { hidden: true }, h('span'));
    this.hud = h('.hud');
    this.loading = h('.loading', h('.spinner'));
    this.skipPill = h('.skip-pill', h('button.btn', { onClick: () => this.skip() }, h('span.skip-label', 'Skip Intro'), h('kbd', 'S')), h('button.x', { onClick: () => { this.skipDismissed = true; this.updateSkip(); } }, icon('x', 14)));
    this.nextEp = h('.next-ep', h('.ring', h('i', '5')), h('small', 'Up next'), h('b'), h('.actions', h('button.btn.primary.sm', { onClick: () => this.playNextEpisode() }, 'Play now'), h('button.btn.ghost.sm', { onClick: () => this.cancelNext() }, 'Cancel')));
    this.badges = h('.badge-row');

    this.topBar = h('.top-bar',
      h('button.icon-btn', { title: 'Back to browse (Esc)', onClick: () => this.minimize() }, icon('back')),
      h('.grow', h('.title'), h('.sub')),
      h('button.icon-btn', { title: 'Playlist', onClick: () => this.togglePlaylist() }, icon('list')),
      h('button.icon-btn', { title: 'Close', onClick: () => this.close() }, icon('x')),
    );

    // seek bar
    this.seek = h('.seek', h('.track', h('.buffered'), h('.played'), h('.marks'), h('.thumb')), h('.tip', '00:00'));
    this.playBtn = h('button.ctl-btn.play', { title: 'Play / Pause (Space)', onClick: () => this.toggle() }, icon('play'));
    this.timeEl = h('span.time', '00:00 / 00:00');
    this.volSlider = h('input', { type: 'range', min: 0, max: 100, value: 80 });
    this.volBtn = h('button.ctl-btn', { title: 'Mute (M)', onClick: () => this.toggleMute() }, icon('volume'));
    this.speedBtn = h('button.ctl-btn.text', { title: 'Speed', onClick: (e) => this.toggleMenu('speed', e) }, '1.0×');
    this.ccBtn = h('button.ctl-btn', { title: 'Subtitles (C)', onClick: (e) => this.toggleMenu('subs', e) }, icon('cc'));
    this.moreBtn = h('button.ctl-btn', { title: 'More', onClick: (e) => this.toggleMenu('more', e) }, icon('more'));
    this.fsBtn = h('button.ctl-btn', { title: 'Fullscreen (F)', onClick: () => this.toggleFullscreen() }, icon('fullscreen'));
    this.miniBtn = h('button.ctl-btn.hide-mini', { title: 'Mini player', onClick: () => this.minimize() }, icon('minimize'));
    this.menus = { speed: h('.menu'), subs: h('.menu'), more: h('.menu') };
    const menuWrap = h('.hstack', { style: { position: 'relative' } }, this.speedBtn, this.ccBtn, this.moreBtn, this.menus.speed, this.menus.subs, this.menus.more);

    this.controls = h('.controls', this.seek,
      h('.ctl-row',
        h('button.ctl-btn', { title: 'Previous (Shift+←)', onClick: () => this.prev() }, icon('prev')),
        this.playBtn,
        h('button.ctl-btn', { title: 'Next (Shift+→)', onClick: () => this.next() }, icon('next')),
        this.timeEl,
        h('.spacer'),
        h('.volume', this.volBtn, this.volSlider),
        menuWrap,
        this.miniBtn,
        this.fsBtn,
      ));

    this.playlistDrawer = h('.playlist-drawer', h('.head', h('b', 'Playlist'), h('.hstack', h('button.btn.sm.ghost', { onClick: () => this.addFilesDialog() }, icon('plus', 14), 'Add'), h('button.icon-btn', { onClick: () => this.togglePlaylist(false) }, icon('x')))), h('.items'));
    this.stallEl = h('.stall', { hidden: true }, 'Buffering…');

    r.append(h('.stage-video', this.video, this.audioArt, this.loading, this.subsEl, this.hud, this.skipPill, this.nextEp, this.badges, this.stallEl, this.topBar, this.controls, this.playlistDrawer));
    this.buildMenus();
  }

  buildMenus() {
    const sp = this.menus.speed; clear(sp);
    sp.appendChild(h('label', 'Speed'));
    for (const s of SPEEDS) sp.appendChild(h('button', { dataset: { speed: s }, onClick: () => { this.setSpeed(s); this.closeMenus(); } }, `${s}×`, s === 1 ? h('kbd', 'normal') : null));
    const sb = this.menus.subs; clear(sb);
    sb.append(h('label', 'Subtitles'),
      h('button', { onClick: () => { this.loadSubtitleDialog(); this.closeMenus(); } }, 'Load file…', h('kbd', 'C')),
      h('button', { onClick: () => { this.toggleSubs(); this.closeMenus(); } }, this.subsOn ? 'Hide subtitles' : 'Show subtitles'),
      h('.sep'), h('label', 'Size'),
      h('button', { onClick: () => this.setSubSize(-10) }, 'Smaller'), h('button', { onClick: () => this.setSubSize(10) }, 'Larger'));
    const mo = this.menus.more; clear(mo);
    mo.append(h('label', 'Video'),
      h('button', { onClick: () => { this.cycleAspect(); } }, 'Aspect ratio', h('kbd', 'A')),
      h('button', { onClick: () => { this.addBookmark(); this.closeMenus(); } }, 'Add bookmark', h('kbd', 'B')),
      h('button', { onClick: () => { this.skipMarkersDialog(); this.closeMenus(); } }, 'Skip markers…'),
      h('button', { onClick: () => { this.compatDialog(); this.closeMenus(); } }, 'Playback fix…'),
      h('.sep'), h('label', 'Share'),
      h('button', { onClick: () => { this.closeMenus(); document.dispatchEvent(new CustomEvent('share:open')); } }, 'Watch together / TV…'),
      h('.sep'), h('button', { onClick: () => { this.closeMenus(); this.showHotkeys(); } }, 'Hotkeys', h('kbd', '?')));
  }

  toggleMenu(name, e) {
    e?.stopPropagation();
    const open = this.menus[name].classList.contains('is-open');
    this.closeMenus();
    if (!open) { if (name === 'subs') this.buildMenus(); this.menus[name].classList.add('is-open'); this.menus[name].querySelectorAll('[data-speed]').forEach(b => b.classList.toggle('is-active', Number(b.dataset.speed) === this.video.playbackRate)); }
  }
  closeMenus() { Object.values(this.menus).forEach(m => m.classList.remove('is-open')); }

  // ───────────────────────── events ─────────────────────────
  bind() {
    const v = this.video;
    v.addEventListener('play', () => { this.root.classList.remove('paused'); this.playBtn.replaceChildren(icon('pause')); this.sidecar.start(true); this.scheduleHide(); this.emit('state'); });
    v.addEventListener('pause', () => { this.root.classList.add('paused'); this.playBtn.replaceChildren(icon('play')); this.sidecar.pause(); this.showUi(); this.emit('state'); this.saveProgress(true); });
    v.addEventListener('timeupdate', () => this.onTime());
    v.addEventListener('progress', () => this.updateBuffered());
    v.addEventListener('durationchange', () => { if (!this.track?.isTS && isFinite(v.duration) && v.duration > 0) this.duration = v.duration; this.renderTime(); this.renderMarks(); });
    v.addEventListener('loadedmetadata', () => { this.loading.classList.remove('show'); });
    v.addEventListener('waiting', () => { this.loading.classList.add('show'); });
    v.addEventListener('playing', () => { this.loading.classList.remove('show'); this.stallEl.hidden = true; });
    v.addEventListener('canplay', () => { this.loading.classList.remove('show'); });
    v.addEventListener('seeking', () => this.sidecar.hold(700));
    v.addEventListener('ended', () => this.onEnded());
    v.addEventListener('error', () => this.onError());
    v.addEventListener('ratechange', () => { this.speedBtn.textContent = `${v.playbackRate}×`; this.sidecar.setRate(0); });
    v.addEventListener('volumechange', () => { this.sidecar.applyVolume(v.volume, this.sidecar.active ? this.userMuted : v.muted); this.renderVolume(); });
    v.addEventListener('click', () => this.toggle());
    v.addEventListener('dblclick', (e) => { const r = v.getBoundingClientRect(); const x = (e.clientX - r.left) / r.width; if (x < 0.3) this.seekBy(-10); else if (x > 0.7) this.seekBy(10); else this.toggleFullscreen(); });

    // seek bar
    let dragging = false;
    const pos = (e) => { const r = this.seek.getBoundingClientRect(); return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)); };
    this.seek.addEventListener('pointerdown', (e) => { dragging = true; this.seek.classList.add('is-dragging'); this.seek.setPointerCapture(e.pointerId); this.previewSeek(pos(e)); });
    this.seek.addEventListener('pointermove', (e) => { const p = pos(e); this.seek.querySelector('.tip').style.left = `${p * 100}%`; this.seek.querySelector('.tip').textContent = fmtTime(p * this.getDuration()); if (dragging) this.previewSeek(p); });
    this.seek.addEventListener('pointerup', (e) => { if (!dragging) return; dragging = false; this.seek.classList.remove('is-dragging'); this.seekTo(pos(e) * this.getDuration(), 'seekbar'); });
    this.seek.addEventListener('pointercancel', () => { dragging = false; this.seek.classList.remove('is-dragging'); });
    this.volSlider.addEventListener('input', () => this.setVolume(Number(this.volSlider.value) / 100));
    this.root.addEventListener('wheel', (e) => { if (this.mode !== 'full' || e.target.closest('.playlist-drawer')) return; e.preventDefault(); this.setVolume(this.video.volume + (e.deltaY < 0 ? 0.05 : -0.05)); this.flash(icon('volume'), `${Math.round(this.video.volume * 100)}%`); }, { passive: false });
    this.root.addEventListener('pointermove', () => this.showUi());
    this.root.addEventListener('pointerdown', (e) => { if (!e.target.closest('.menu') && !e.target.closest('.ctl-btn')) this.closeMenus(); });
    this.controls.addEventListener('pointerenter', () => { this.hoverControls = true; this.showUi(); });
    this.controls.addEventListener('pointerleave', () => { this.hoverControls = false; this.scheduleHide(); });
    document.addEventListener('keydown', (e) => this.onKey(e));
    document.addEventListener('fullscreenchange', () => this.fsBtn.replaceChildren(icon(document.fullscreenElement ? 'minimize' : 'fullscreen')));
  }

  emit(name, detail) { this.dispatchEvent(new CustomEvent(name, { detail })); }

  onKey(e) {
    if (this.mode !== 'full') return;
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
    if (document.querySelector('.modal-backdrop')) return;
    const step = store.prefs.seekStep || 5;
    const map = {
      Space: () => this.toggle(), KeyK: () => this.toggle(),
      ArrowRight: () => e.shiftKey ? this.next() : this.seekBy(step), ArrowLeft: () => e.shiftKey ? this.prev() : this.seekBy(-step),
      KeyL: () => this.seekBy(10), KeyJ: () => this.seekBy(-10),
      ArrowUp: () => { this.setVolume(this.video.volume + 0.05); this.flash(icon('volume'), `${Math.round(this.video.volume * 100)}%`); },
      ArrowDown: () => { this.setVolume(this.video.volume - 0.05); this.flash(icon('volume'), `${Math.round(this.video.volume * 100)}%`); },
      KeyM: () => this.toggleMute(), KeyF: () => this.toggleFullscreen(), F11: () => this.toggleFullscreen(),
      KeyS: () => this.skip(), KeyA: () => this.cycleAspect(), KeyC: () => this.cues ? this.toggleSubs() : this.loadSubtitleDialog(),
      KeyB: () => this.addBookmark(), KeyN: () => this.next(), KeyP: () => this.togglePlaylist(),
      Comma: () => this.setSpeed(Math.max(0.25, +(this.video.playbackRate - 0.25).toFixed(2))), Period: () => this.setSpeed(Math.min(3, +(this.video.playbackRate + 0.25).toFixed(2))),
      Slash: () => this.showHotkeys(),
      Escape: () => { if (this.nextEp.classList.contains('show')) return this.cancelNext(); if (this.playlistDrawer.classList.contains('is-open')) return this.togglePlaylist(false); if (document.fullscreenElement) return document.exitFullscreen(); this.minimize(); },
    };
    if (/^Digit[0-9]$/.test(e.code)) { this.seekTo(this.getDuration() * (Number(e.code.slice(5)) / 10), 'keyboard'); e.preventDefault(); return; }
    const fn = map[e.code];
    if (fn) { e.preventDefault(); fn(); }
  }

  // ───────────────────────── open / load ─────────────────────────
  /**
   * open(tracks, { index, item, epNum, startTime })
   * track: { name, path, url?, file?, size?, isTS?, isVideo?, audioSidecarPath?, audioCompatMode?, libraryId?, category?, epNum? }
   */
  async open(tracks, { index = 0, item = null, epNum = null, startTime = 0, mode = 'full' } = {}) {
    const list = (Array.isArray(tracks) ? tracks : [tracks]).map(normalizeTrack).filter(Boolean);
    if (!list.length) return toast('Nothing to play', { kind: 'err' });
    this.playlist = list;
    this.item = item; this.epNum = epNum;
    this.show(mode);
    store.setPlaylist(list.map(stripRuntime), index);
    await this.play(index, startTime);
  }

  show(mode = 'full') {
    this.root.hidden = false;
    this.root.classList.toggle('mini', mode === 'mini');
    requestAnimationFrame(() => this.root.classList.add('is-open'));
    this.mode = mode;
    document.body.classList.toggle('player-full', mode === 'full');
    this.showUi();
    this.emit('mode', mode);
  }

  expand() { if (this.mode === 'closed') return; this.show('full'); }
  minimize() {
    if (this.mode === 'closed') return;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    if (this.video.paused && !store.prefs.miniPlayerOnBrowse) return this.close();
    this.show('mini');
    this.togglePlaylist(false);
  }

  close() {
    this.saveProgress(true);
    this.stopMedia();
    this.cancelNext();
    this.root.classList.remove('is-open');
    this.mode = 'closed';
    document.body.classList.remove('player-full');
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    setTimeout(() => { if (this.mode === 'closed') this.root.hidden = true; }, 320);
    this.track = null; this.item = null; this.epNum = null;
    this.emit('mode', 'closed');
    this.emit('state');
  }

  stopMedia() {
    this.sidecar.detach();
    if (this.mpegts) { try { this.mpegts.pause(); this.mpegts.unload(); this.mpegts.detachMediaElement(); this.mpegts.destroy(); } catch {} this.mpegts = null; }
    try { this.video.pause(); this.video.removeAttribute('src'); this.video.load(); } catch {}
    if (this.blobUrl) { URL.revokeObjectURL(this.blobUrl); this.blobUrl = null; }
    this.cues = null; this.subsEl.hidden = true; this.subsOn = false;
    clear(this.badges);
  }

  async play(index, startTime = 0) {
    if (index < 0 || index >= this.playlist.length) return;
    const token = ++this.loadToken;
    this.stopMedia();
    this.cancelNext();
    this.index = index;
    const track = this.track = this.playlist[index];
    this.duration = 0; this.skipDismissed = false; this.lastSave = 0;
    this.item = track.libraryId != null ? (store.findItem(track.libraryId, track.category) || this.item) : (this.item && this.item.id === track.libraryId ? this.item : null);
    this.epNum = track.epNum ?? this.epNum;
    store.setPlaylist(this.playlist.map(stripRuntime), index);
    this.renderHeader();
    this.renderPlaylist();
    this.loading.classList.add('show');
    this.audioArt.hidden = track.isVideo;
    if (!track.isVideo) { this.audioArt.querySelector('h2').textContent = stripExt(track.name); this.audioArt.querySelector('p').textContent = 'Audio'; }
    this.applyPrefs();

    // Resolve a URL (backend media route, or a blob for browser-picked files).
    let url = track.url;
    if (!url && track.file) { this.blobUrl = URL.createObjectURL(track.file); url = this.blobUrl; }
    if (!url && track.path) url = mediaUrl(track.path);
    if (!url) return toast('Cannot play: no file path', { kind: 'err' });

    // Duration for .ts comes from the backend PTS scanner (the browser can't know it via MSE).
    if (track.isTS && track.path) {
      const d = await rpcSafe('get_file_duration', track.path);
      if (token !== this.loadToken) return;
      if (d > 0) this.duration = Number(d);
    }

    // Compatibility (DTS/TrueHD audio, HEVC video) for local non-TS files.
    if (!track.isTS && track.isVideo && track.path && !track.file) {
      const ok = await this.ensureCompat(track, token);
      if (token !== this.loadToken) return;
      if (ok === false) return;
      if (track.url) url = track.url;
    }
    if (track.audioSidecarPath) this.sidecar.attach(mediaUrl(track.audioSidecarPath));

    if (track.isTS) await this.playTs(url, token);
    else await this.playNative(url, token);
    if (token !== this.loadToken) return;
    if (startTime > 5) this.seekTo(startTime, 'resume');
    this.renderMarks();
    this.autoLoadSubtitles(track);
    if (this.item && this.epNum) store.addHistory({ id: this.item.id, title: this.item.title, epNum: this.epNum, time: startTime || 0, timestamp: Date.now(), poster: this.item.poster, category: this.item.category });
    this.emit('track', track);
    this.emit('state');
  }

  async playNative(url, token) {
    const v = this.video;
    v.src = url;
    v.load();
    for (let attempt = 0; attempt < 4; attempt++) {
      if (token !== this.loadToken) return;
      try { await v.play(); return; } catch (e) {
        if (e && e.name === 'NotAllowedError') { toast('Click play to start'); this.loading.classList.remove('show'); return; }
        if (e && e.name === 'AbortError') return;
        await new Promise(r => setTimeout(r, 300 * (attempt + 1)));
      }
    }
  }

  async playTs(url, token) {
    if (!window.mpegts) {
      await new Promise((res, rej) => { const s = document.createElement('script'); s.src = '/static/mpegts.min.js?v=1.8.0'; s.onload = res; s.onerror = rej; document.head.appendChild(s); }).catch(() => null);
    }
    if (token !== this.loadToken) return;
    if (!window.mpegts || !mpegts.getFeatureList().mseLivePlayback) { toast('MPEG-TS playback is not supported here', { kind: 'err' }); return this.playNative(url, token); }
    const src = { type: 'mpegts', url, isLive: false };
    if (this.duration > 0) src.duration = this.duration * 1000;
    const p = this.mpegts = mpegts.createPlayer(src, { enableWorker: true, enableWorkerForMSE: true, lazyLoad: false, autoCleanupSourceBuffer: true, autoCleanupMaxBackwardBufferDelay: 120, autoCleanupMinBackwardBufferDelay: 40 });
    p.on(mpegts.Events.ERROR, (type, detail) => {
      console.error('[mpegts]', type, detail);
      if (type === mpegts.ErrorTypes.MEDIA_ERROR) { try { p.recoverMediaError(); } catch { const t = this.video.currentTime; this.play(this.index, t); } }
    });
    p.attachMediaElement(this.video);
    p.load();
    try { await this.video.play(); } catch (e) { console.warn('[ts] play', e); }
  }

  /** Checks codec compatibility; may swap track.url to a proxy or attach a sidecar. Returns false when the user cancelled. */
  async ensureCompat(track, token) {
    if (!store.state.app.ffmpeg) return true;
    if (track.audioCompatMode && track.audioCompatMode !== 'unknown') {
      if (track.audioCompatMode === 'audio_sidecar' && track.audioSidecarPath) return true;
      if (track.audioCompatMode === 'direct') return true;
    }
    const info = await rpcSafe('check_playback_fixes', track.path);
    if (token !== this.loadToken) return false;
    if (!info || info.status !== 'success') return true;
    if (info.video_proxy?.ready) return this.applyProxy(track, info.video_proxy.path, 'video_proxy', true);
    if (info.full_proxy?.ready) return this.applyProxy(track, info.full_proxy.path, 'full_proxy', true);
    if (info.sidecar?.ready) { track.audioSidecarPath = info.sidecar.path; track.audioCompatMode = 'audio_sidecar'; this.setBadge('AAC sidecar'); return true; }
    if (!info.needs_fix) { track.audioCompatMode = 'direct'; return true; }
    this.video.pause();
    const mode = await this.compatChoice(info);
    if (token !== this.loadToken) return false;
    if (!mode) return false;
    if (mode === 'original') { track.audioCompatMode = 'direct'; return true; }
    const prep = await rpcSafe('prepare_media_for_playback', track.path, mode);
    if (!prep) return true;
    return this.applyPrep(track, prep, token);
  }

  async applyPrep(track, prep, token) {
    if (prep.status === 'ready') {
      if ((prep.mode === 'video_proxy' || prep.mode === 'full_proxy') && prep.path) return this.applyProxy(track, prep.path, prep.mode, prep.cached);
      if (prep.mode === 'audio_sidecar' && prep.sidecar_path) { track.audioSidecarPath = prep.sidecar_path; track.audioCompatMode = 'audio_sidecar'; this.setBadge('AAC sidecar'); return true; }
      track.audioCompatMode = 'direct'; return true;
    }
    if (prep.status === 'processing' && prep.task_id) {
      const labels = { video_proxy: 'Creating H.264/AAC MP4 (fixes HEVC/AV1 video)', full_proxy: 'Creating compatible MKV copy', audio_sidecar: 'Creating a small AAC audio sidecar' };
      taskOverlay('Preparing playback…', labels[prep.mode] || prep.mode);
      for (let i = 0; i < 2000; i++) {
        await new Promise(r => setTimeout(r, 1500));
        if (token !== this.loadToken) { hideTask(); return false; }
        const st = await rpcSafe('media_task_status', prep.task_id);
        if (!st) continue;
        taskOverlay('Preparing playback…', st.message || '', Number(st.progress) || null);
        if (st.status === 'ready') {
          hideTask();
          if (st.sidecar_path) { track.audioSidecarPath = st.sidecar_path; track.audioCompatMode = 'audio_sidecar'; this.setBadge('AAC sidecar'); toast('AAC sidecar ready', { kind: 'ok' }); return true; }
          if (st.path) return this.applyProxy(track, st.path, prep.mode, false);
          return true;
        }
        if (st.status === 'error' || st.status === 'missing') { hideTask(); toast('Playback fix failed: ' + (st.message || 'unknown'), { kind: 'err' }); return true; }
      }
      hideTask();
    }
    return true;
  }

  applyProxy(track, path, mode, cached) {
    track.path = path; track.url = mediaUrl(path); track.audioCompatMode = mode; track.name = track.name || baseName(path);
    this.setBadge(mode === 'video_proxy' ? 'H.264 proxy' : 'Compatible copy');
    if (!cached) toast('Using compatible copy', { kind: 'ok' });
    if (this.item && this.epNum) { const ep = this.item.episodes.find(e => Number(e.num) === Number(this.epNum)); if (ep) { ep.path = path; ep.compatible_copy = true; store.updateItem(this.item); } }
    return true;
  }

  compatChoice(info) {
    const a = info.analysis || {};
    const audio = (a.playback_audio || {}).codec || '?';
    const video = (a.video_codecs || []).join(', ') || '?';
    const opts = [];
    if (a.needs_audio_sidecar) opts.push(['sidecar', 'AAC audio sidecar (recommended)', `Converts only the audio (${audio}) into a small AAC file. Video is not copied. Fast, no extra disk.`]);
    if (a.needs_video_transcode) opts.push(['video', 'Browser-compatible MP4', `Re-encodes ${video} video to H.264. Slow, but fixes video that shows a black screen.`]);
    opts.push(['full', 'Full compatible MKV copy', 'Copies video, converts audio to AAC. Uses disk space equal to the file.']);
    opts.push(['original', 'Play original anyway', 'Try as-is. You may get picture without sound.']);
    const closeRef = { fn: () => {} };
    return modal({
      title: 'This file needs a playback fix',
      body: h('div', h('p.muted.small', { style: { marginBottom: '12px' } }, `Audio: ${audio} · Video: ${video} · ${info.size_gb || 0} GB`), ...opts.map(([v, t, d]) => h('button.option-card', { onClick: () => { closeRef.fn(v); } }, h('div', h('b', t), h('small', d)), icon('chevron')))),
      actions: [{ label: 'Cancel', value: null, kind: 'ghost' }],
      onOpen: (box, close) => { closeRef.fn = close; },
    });
  }

  async compatDialog() {
    if (!this.track?.path) return toast('No local file');
    const info = await rpcSafe('check_playback_fixes', this.track.path);
    if (!info || info.status !== 'success') return toast('Cannot analyze this file', { kind: 'err' });
    const mode = await this.compatChoice(info);
    if (!mode) return;
    const t = this.video.currentTime;
    const prep = await rpcSafe('prepare_media_for_playback', this.track.path, mode);
    if (prep) { const ok = await this.applyPrep(this.track, prep, this.loadToken); if (ok) this.play(this.index, t); }
  }

  setBadge(text) { clear(this.badges); this.badges.appendChild(h('span.badge', text)); }

  // ───────────────────────── playback controls ─────────────────────────
  toggle() { if (this.video.paused) this.video.play().catch(() => {}); else this.video.pause(); this.flash(icon(this.video.paused ? 'pause' : 'play')); }
  getDuration() { return this.duration > 0 ? this.duration : (isFinite(this.video.duration) ? this.video.duration : 0); }
  seekTo(t, reason = 'seek') {
    const d = this.getDuration();
    let target = Math.max(0, Number(t) || 0);
    if (d > 0) target = Math.min(target, Math.max(0, d - (this.track?.isTS ? 5 : 0.5)));
    this.sidecar.hold(reason.startsWith('keyboard') ? 1100 : 800);
    try { this.video.currentTime = target; } catch (e) { console.warn('[seek]', e); }
    this.renderTime();
  }
  seekBy(delta) { this.seekTo((this.video.currentTime || 0) + delta, 'keyboard'); this.flash(icon(delta > 0 ? 'next' : 'prev'), `${delta > 0 ? '+' : ''}${delta}s`); }
  previewSeek(p) { const d = this.getDuration(); this.seek.querySelector('.played').style.width = `${p * 100}%`; this.seek.querySelector('.thumb').style.left = `${p * 100}%`; this.timeEl.textContent = `${fmtTime(p * d)} / ${fmtTime(d)}`; }
  setVolume(v) {
    v = Math.max(0, Math.min(1, v));
    this.video.volume = v;
    if (v > 0) { this.userMuted = false; if (!this.sidecar.active) this.video.muted = false; }
    store.setPrefs({ volume: v, muted: this.userMuted });
    this.renderVolume();
  }
  toggleMute() {
    this.userMuted = !this.userMuted;
    if (this.sidecar.active) this.sidecar.applyVolume(this.video.volume, this.userMuted); else this.video.muted = this.userMuted;
    store.setPref('muted', this.userMuted);
    this.flash(icon(this.userMuted ? 'mute' : 'volume'));
    this.renderVolume();
  }
  setSpeed(s) { this.video.playbackRate = s; store.setPref('speed', s); this.flash(null, `${s}×`); }
  cycleAspect() {
    const order = ['contain', 'cover', 'fill'];
    const cur = store.prefs.aspect; const nxt = order[(order.indexOf(cur) + 1) % order.length];
    store.setPref('aspect', nxt); this.applyAspect(); this.flash(null, nxt === 'contain' ? 'Fit' : nxt === 'cover' ? 'Fill (crop)' : 'Stretch');
  }
  applyAspect() { const a = store.prefs.aspect; this.video.classList.toggle('fit-cover', a === 'cover'); this.video.classList.toggle('fit-fill', a === 'fill'); }
  applyPrefs() {
    const p = store.prefs;
    this.video.volume = p.volume ?? 0.8;
    this.userMuted = !!p.muted;
    this.video.muted = this.userMuted && !this.sidecar.active;
    this.video.playbackRate = p.speed || 1;
    this.applyAspect();
    this.subsEl.querySelector('span').style.fontSize = `${(p.subtitleSize || 100) / 100 * 1.4}em`;
    this.renderVolume();
  }
  toggleFullscreen() {
    if (this.mode !== 'full') this.expand();
    if (window.__hasWindow) { rpcSafe('toggle_native_fullscreen'); }
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); else this.root.requestFullscreen?.().catch(() => {});
  }
  next() { if (this.index < this.playlist.length - 1) this.play(this.index + 1); else if (this.item && this.epNum) this.playNextEpisode(); else this.flash(null, 'End of playlist'); }
  prev() { if (this.video.currentTime > 5) return this.seekTo(0); if (this.index > 0) this.play(this.index - 1); }
  skip() {
    const d = this.getDuration(); if (!d) return;
    const m = this.markers(); const t = this.video.currentTime;
    if (t >= m.introStart && t < m.introEnd) { this.seekTo(m.introEnd); this.flash(icon('skip'), 'Intro skipped'); }
    else if (t >= d - m.outroStartOffset) { this.seekTo(d - m.outroSkipToEndOffset); this.flash(icon('skip'), 'Outro skipped'); }
    else this.seekBy(85);
  }
  markers() { return this.item ? store.getSkipMarkers(this.item.id, this.epNum) : store.getSkipMarkers('_', null); }

  // ───────────────────────── time loop ─────────────────────────
  onTime() {
    const t = this.video.currentTime || 0;
    const d = this.getDuration();
    if (this.track?.isTS && t > this.duration - 0.5) this.duration = t + 30;
    this.renderTime();
    if (this.cues && this.subsOn) { const txt = cueAt(this.cues, t); const span = this.subsEl.querySelector('span'); if (span.textContent !== txt) span.textContent = txt; this.subsEl.hidden = !txt; }
    this.updateSkip();
    const now = Date.now();
    if (now - this.lastSave > 5000) { this.lastSave = now; this.saveProgress(false); }
    if (this.item && this.epNum && d > 0 && store.prefs.autoNext && d - t <= 12 && d - t > 0 && !this.nextEp.classList.contains('show') && !this.nextDismissed && this.findNextEpisode()) this.showNext();
    this.emit('time', { t, d });
  }
  renderTime() { const d = this.getDuration(); this.timeEl.textContent = `${fmtTime(this.video.currentTime)} / ${fmtTime(d)}`; const p = d ? Math.min(1, this.video.currentTime / d) : 0; this.seek.querySelector('.played').style.width = `${p * 100}%`; this.seek.querySelector('.thumb').style.left = `${p * 100}%`; }
  updateBuffered() { const v = this.video, d = this.getDuration(); if (!d || !v.buffered.length) return; let end = 0; for (let i = 0; i < v.buffered.length; i++) if (v.buffered.start(i) <= v.currentTime + 0.5) end = Math.max(end, v.buffered.end(i)); this.seek.querySelector('.buffered').style.width = `${Math.min(100, end / d * 100)}%`; }
  renderVolume() { const muted = this.userMuted || (this.video.muted && !this.sidecar.active); this.volBtn.replaceChildren(icon(muted || this.video.volume === 0 ? 'mute' : 'volume')); this.volSlider.value = Math.round(this.video.volume * 100); }
  renderHeader() {
    const t = this.track; if (!t) return;
    const title = this.item ? this.item.title : stripExt(t.name);
    const sub = this.item && this.epNum ? `Episode ${this.epNum}${t.name ? ' · ' + t.name : ''}` : (t.path || '');
    this.topBar.querySelector('.title').textContent = title;
    this.topBar.querySelector('.sub').textContent = sub;
    document.title = `${title} — Modern Player`;
  }
  renderMarks() {
    const wrap = this.seek.querySelector('.marks'); clear(wrap);
    const d = this.getDuration(); if (!d || !this.item) return;
    for (const b of store.getBookmarks(this.item.id, this.epNum)) wrap.appendChild(h('.mark', { title: b.label || fmtTime(b.time), style: { left: `${b.time / d * 100}%` } }));
  }
  updateSkip() {
    const d = this.getDuration();
    if (!d || this.skipDismissed || !this.track?.isVideo) return this.skipPill.classList.remove('show');
    const t = this.video.currentTime, m = this.markers();
    if (d < m.introEnd + 60) return this.skipPill.classList.remove('show');
    const intro = t >= m.introStart && t < m.introEnd && m.introEnd > 1;
    const outro = t >= d - m.outroStartOffset && t < d - m.outroSkipToEndOffset;
    this.skipPill.querySelector('.skip-label').textContent = intro ? 'Skip Intro' : 'Skip Outro';
    this.skipPill.classList.toggle('show', intro || outro);
  }
  flash(iconEl, text) {
    clear(this.hud);
    if (iconEl) this.hud.appendChild(iconEl);
    if (text) this.hud.appendChild(h('span', text));
    this.hud.classList.add('show');
    clearTimeout(this._hudT); this._hudT = setTimeout(() => this.hud.classList.remove('show'), 650);
  }
  showUi() { this.root.classList.remove('hide-ui'); this.scheduleHide(); }
  scheduleHide() {
    clearTimeout(this.uiTimer);
    if (this.video.paused || this.hoverControls || this.mode !== 'full') return;
    this.uiTimer = setTimeout(() => { if (!this.video.paused && !this.hoverControls && !Object.values(this.menus).some(m => m.classList.contains('is-open'))) this.root.classList.add('hide-ui'); }, 2600);
  }

  // ───────────────────────── progress / episodes ─────────────────────────
  saveProgress(force) {
    if (!this.item || !this.epNum) return;
    const t = this.video.currentTime || 0, d = this.getDuration();
    if (t < 10) return;
    if (d > 0 && t / d >= 0.92) {
      if (!store.isWatched(this.item.id, this.epNum)) store.setWatched(this.item.id, this.epNum, true);
      store.removeProgress(this.item.id);
      return;
    }
    const existing = store.getProgress(this.item.id);
    if (!force && existing && Number(existing.epNum) === Number(this.epNum) && Number(existing.time) - t > 90) return;
    store.setProgress({ id: this.item.id, title: this.item.title, poster: this.item.poster, category: this.item.category, epNum: Number(this.epNum), episodesCount: this.item.episodes_count || this.item.episodes.length || 1, time: t, duration: d || 1400, timestamp: Date.now() });
  }
  findNextEpisode() {
    if (!this.item || !this.epNum) return null;
    return this.item.episodes.find(e => Number(e.num) > Number(this.epNum) && e.path) || null;
  }
  showNext() {
    const nxt = this.findNextEpisode(); if (!nxt) return;
    this.nextEp.querySelector('b').textContent = `Episode ${nxt.num}${nxt.title ? ' · ' + nxt.title : ''}`;
    this.nextEp.classList.add('show');
    let left = 8; const ring = this.nextEp.querySelector('.ring');
    const tick = () => { ring.style.setProperty('--p', `${(8 - left) / 8 * 100}%`); ring.querySelector('i').textContent = left; if (left <= 0) { this.playNextEpisode(); return; } left--; this.nextTimer = setTimeout(tick, 1000); };
    clearTimeout(this.nextTimer); tick();
  }
  cancelNext() { clearTimeout(this.nextTimer); this.nextTimer = null; this.nextEp.classList.remove('show'); this.nextDismissed = true; }
  onEnded() {
    this.saveProgress(true);
    if (this.item && this.epNum) { store.setWatched(this.item.id, this.epNum, true); store.removeProgress(this.item.id); if (store.prefs.autoNext && this.findNextEpisode()) return this.playNextEpisode(); }
    else if (this.index < this.playlist.length - 1) return this.play(this.index + 1);
    this.showUi();
  }
  playNextEpisode() {
    const nxt = this.findNextEpisode(); if (!nxt) return;
    clearTimeout(this.nextTimer); this.nextEp.classList.remove('show'); this.nextDismissed = false;
    document.dispatchEvent(new CustomEvent('player:play-episode', { detail: { item: this.item, epNum: nxt.num } }));
  }
  onError() {
    const err = this.video.error;
    if (!err || !this.track) return;
    this.loading.classList.remove('show');
    console.error('[video] error', err.code, err.message);
    if (err.code === 4 && this.track.path && !this.track.isTS && store.state.app.ffmpeg && !this.track._compatPrompted) {
      this.track._compatPrompted = true;
      toast('This format is not supported directly. Choose a playback fix.', { kind: 'err', ms: 4000 });
      this.compatDialog();
    } else if (err.code !== 1) toast('Playback error: ' + (err.message || `code ${err.code}`), { kind: 'err' });
  }

  // ───────────────────────── subtitles / bookmarks ─────────────────────────
  async loadSubtitleDialog() {
    const files = await pickFiles({ kind: 'subtitle', multiple: false });
    if (!files.length) return;
    const f = files[0];
    let text = '';
    if (f.file) text = await f.file.text();
    else { const r = await rpcSafe('read_text_file', f.path); text = r?.text || ''; }
    if (!text) return toast('Could not read subtitle file', { kind: 'err' });
    this.setSubtitles(text, f.name);
  }
  setSubtitles(text, name) {
    this.cues = parseSubtitles(text, name);
    this.subsOn = true; this.ccBtn.classList.add('is-active');
    toast(`Subtitles: ${name} (${this.cues.length} cues)`, { kind: 'ok' });
  }
  toggleSubs() { this.subsOn = !this.subsOn; this.ccBtn.classList.toggle('is-active', this.subsOn); if (!this.subsOn) this.subsEl.hidden = true; this.flash(icon('cc'), this.subsOn ? 'Subtitles on' : 'Subtitles off'); }
  setSubSize(delta) { const v = Math.max(50, Math.min(200, (store.prefs.subtitleSize || 100) + delta)); store.setPref('subtitleSize', v); this.subsEl.querySelector('span').style.fontSize = `${v / 100 * 1.4}em`; }
  async autoLoadSubtitles(track) {
    // Same-name .srt next to the file: load it silently.
    if (!track.path || track.file) return;
    const base = track.path.replace(/\.[^.\\/]+$/, '');
    for (const ext of ['.srt', '.vtt', '.ass']) {
      const r = await rpcSafe('read_text_file', base + ext);
      if (r && r.status === 'success' && r.text) { this.cues = parseSubtitles(r.text, base + ext); this.subsOn = false; this.ccBtn.classList.add('is-active'); this.setBadge('Subtitles found (C)'); return; }
    }
  }
  async addBookmark() {
    if (!this.item) return toast('Bookmarks need a library episode');
    const t = this.video.currentTime;
    const label = await promptDialog('Bookmark label', { placeholder: fmtTime(t), okLabel: 'Save' });
    if (label === null) return;
    const list = store.getBookmarks(this.item.id, this.epNum).concat([{ time: t, label: label || fmtTime(t) }]).sort((a, b) => a.time - b.time);
    store.setBookmarks(this.item.id, this.epNum, list); this.renderMarks(); toast('Bookmark added', { kind: 'ok' });
  }
  async skipMarkersDialog() {
    if (!this.item) return toast('Skip markers are per title');
    const m = this.markers();
    const f = (label, key, val) => h('.field', h('label', label), h('input.input', { type: 'number', min: 0, value: val, dataset: { key } }));
    const body = h('.form-grid', f('Intro start (s)', 'introStart', m.introStart), f('Intro end (s)', 'introEnd', m.introEnd), f('Outro starts before end (s)', 'outroStartOffset', m.outroStartOffset), f('Skip outro to end − (s)', 'outroSkipToEndOffset', m.outroSkipToEndOffset),
      h('button.btn.sm.ghost.full', { onClick: () => { body.querySelector('[data-key=introStart]').value = Math.floor(this.video.currentTime); } }, 'Intro starts now'),
      h('button.btn.sm.ghost.full', { onClick: () => { body.querySelector('[data-key=introEnd]').value = Math.floor(this.video.currentTime); } }, 'Intro ends now'));
    const scope = h('label.switch', h('input', { type: 'checkbox' }), h('span', 'Only this episode'));
    const res = await modal({ title: `Skip markers · ${this.item.title}`, body: h('div', body, h('div', { style: { marginTop: '12px' } }, scope)), actions: [{ label: 'Cancel', value: null, kind: 'ghost' }, { label: 'Save', value: true, kind: 'primary' }] });
    if (!res) return;
    const out = {}; body.querySelectorAll('[data-key]').forEach(i => out[i.dataset.key] = Number(i.value) || 0);
    store.setSkipMarkers(this.item.id, out, scope.querySelector('input').checked ? this.epNum : null);
    this.skipDismissed = false; toast('Skip markers saved', { kind: 'ok' });
  }
  showHotkeys() {
    const keys = [['Space / K', 'Play / pause'], ['← / →', 'Seek 5 s'], ['J / L', 'Seek 10 s'], ['Shift + ← / →', 'Previous / next'], ['↑ / ↓', 'Volume'], ['M', 'Mute'], ['F', 'Fullscreen'], ['S', 'Skip intro / outro'], ['A', 'Aspect ratio'], ['C', 'Subtitles'], ['B', 'Bookmark'], ['P', 'Playlist'], [', / .', 'Slower / faster'], ['0-9', 'Jump to %'], ['Esc', 'Mini player / back'], ['?', 'This help']];
    modal({ title: 'Player hotkeys', body: h('.hotkeys', ...keys.map(([k, v]) => h('.hotkey', h('span', v), h('kbd', k)))), wide: true });
  }

  // ───────────────────────── playlist ─────────────────────────
  togglePlaylist(force) { const open = force ?? !this.playlistDrawer.classList.contains('is-open'); this.playlistDrawer.classList.toggle('is-open', open); if (open) this.renderPlaylist(); }
  renderPlaylist() {
    const items = this.playlistDrawer.querySelector('.items');
    renderList(items, this.playlist.map((t, i) => ({ t, i })), {
      key: x => x.i + ':' + (x.t.path || x.t.name),
      create: ({ t, i }) => h('.pl-item', { onClick: () => this.play(i) }, h('span.n', String(i + 1)), h('span.name', { title: t.path || '' }, t.name), h('button.x', { onClick: (e) => { e.stopPropagation(); this.removeTrack(i); } }, icon('x', 14))),
      update: (el, { i }) => { el.classList.toggle('is-active', i === this.index); },
    });
    items.querySelectorAll('.pl-item').forEach((el, i) => el.classList.toggle('is-active', i === this.index));
  }
  removeTrack(i) {
    this.playlist.splice(i, 1);
    if (i === this.index) { if (this.playlist.length) this.play(Math.min(i, this.playlist.length - 1)); else this.close(); }
    else { if (i < this.index) this.index--; store.setPlaylist(this.playlist.map(stripRuntime), this.index); this.renderPlaylist(); }
  }
  async addFilesDialog() {
    const files = await pickFiles({ kind: 'media', multiple: true });
    if (!files.length) return;
    const start = this.playlist.length;
    this.playlist.push(...files.map(normalizeTrack));
    store.setPlaylist(this.playlist.map(stripRuntime), this.index);
    this.renderPlaylist();
    if (this.mode === 'closed' || this.index < 0) { this.show('full'); this.play(start); }
    else toast(`${files.length} file(s) added to playlist`, { kind: 'ok' });
  }

  getState() {
    return { open: this.mode !== 'closed', mode: this.mode, paused: this.video.paused, time: this.video.currentTime || 0, duration: this.getDuration(), rate: this.video.playbackRate || 1, track: this.track, item: this.item, epNum: this.epNum };
  }
}

export function normalizeTrack(t) {
  if (!t) return null;
  const name = t.name || baseName(t.path) || 'Unknown';
  const lower = name.toLowerCase();
  const isTS = t.isTS ?? lower.endsWith('.ts');
  const isAudio = /\.(mp3|m4a|aac|flac|wav|ogg|opus)$/.test(lower) || t.kind === 'audio';
  return { ...t, name, isTS, isVideo: t.isVideo ?? !isAudio, url: t.url || (t.path && !t.file ? mediaUrl(t.path) : undefined) };
}
function stripRuntime(t) { const { file, _compatPrompted, ...rest } = t; if (rest.url && rest.url.startsWith('blob:')) delete rest.url; return rest; }

export const player = new Player();
window.__player = player;
