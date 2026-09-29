// External AAC audio synced to a muted <video>. Used when the file's audio track
// (DTS / TrueHD / FLAC …) cannot be decoded by the WebView. The backend builds a
// small .m4a sidecar and we keep it locked to the video's clock.

export class Sidecar {
  constructor(video) {
    this.video = video;
    this.audio = null;
    this.timer = null;
    this.holdUntil = 0;
    this.lastHardSync = 0;
    this.lastObserved = 0;
    this.lastAdvanced = 0;
    this.recovering = false;
  }

  get active() { return !!this.audio; }

  attach(url) {
    this.detach();
    const a = new Audio();
    a.preload = 'auto';
    a.crossOrigin = 'anonymous';
    a.src = url;
    this.audio = a;
    this.video.muted = true;
    a.load();
    this.timer = setInterval(() => this.tick(), 500);
    if (!this.video.paused) this.start(true);
  }

  detach() {
    clearInterval(this.timer); this.timer = null;
    if (this.audio) {
      try { this.audio.pause(); this.audio.src = ''; this.audio.load(); } catch {}
      this.audio = null;
    }
  }

  applyVolume(volume, muted) {
    if (!this.audio) return;
    this.audio.volume = Math.max(0, Math.min(1, volume));
    this.audio.muted = !!muted;
  }

  setRate(nudge = 0) {
    if (!this.audio) return;
    const base = this.video.playbackRate || 1;
    this.audio.playbackRate = Math.max(0.5, Math.min(2.5, base + nudge));
  }

  sync(force = false) {
    const a = this.audio; if (!a) return;
    const drift = (this.video.currentTime || 0) - (a.currentTime || 0);
    const abs = Math.abs(drift);
    const now = Date.now();
    if ((force && abs > 0.05) || (abs > 1.25 && now - this.lastHardSync > 1500)) {
      a.currentTime = this.video.currentTime || 0;
      this.lastHardSync = now;
      this.setRate(0);
    } else if (abs > 0.18) {
      this.setRate((drift > 0 ? 1 : -1) * (abs > 0.7 ? 0.045 : 0.018));
    } else {
      this.setRate(0);
    }
  }

  start(forceSync = false) {
    const a = this.audio; if (!a || this.video.paused) return;
    if (Date.now() < this.holdUntil) { setTimeout(() => this.start(true), this.holdUntil - Date.now() + 60); return; }
    if (forceSync) this.sync(true);
    a.play().then(() => { this.lastObserved = a.currentTime; this.lastAdvanced = Date.now(); }).catch(() => this.recover());
  }

  pause() { try { this.audio?.pause(); } catch {} }

  /** Pause briefly around seeks so the audio element doesn't stutter while the video rebuffers. */
  hold(ms = 700) {
    this.holdUntil = Math.max(this.holdUntil, Date.now() + ms);
    this.pause();
    setTimeout(() => { if (!this.video.paused) this.start(true); }, ms + 60);
  }

  async recover() {
    const a = this.audio; if (!a || this.recovering || this.video.paused) return;
    this.recovering = true;
    try {
      this.sync(true);
      await a.play();
      this.lastObserved = a.currentTime; this.lastAdvanced = Date.now();
    } catch {
      try { a.muted = true; await a.play(); setTimeout(() => { if (this.audio) this.audio.muted = false; }, 80); } catch {}
    } finally {
      setTimeout(() => { this.recovering = false; }, 300);
    }
  }

  tick() {
    const a = this.audio; if (!a) return;
    if (this.video.paused) { if (!a.paused) a.pause(); return; }
    if (Date.now() < this.holdUntil) return;
    this.sync(false);
    const now = Date.now();
    if (Math.abs(a.currentTime - this.lastObserved) > 0.035) { this.lastObserved = a.currentTime; this.lastAdvanced = now; }
    if (!this.lastAdvanced) this.lastAdvanced = now;
    if (a.paused || now - this.lastAdvanced > 1800) this.recover();
  }
}
