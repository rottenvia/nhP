// SRT / VTT / (basic) ASS parsing and cue lookup with binary search.

export function parseSubtitles(text, filename = '') {
  const t = String(text || '').replace(/\r/g, '');
  const lower = filename.toLowerCase();
  if (lower.endsWith('.ass') || lower.endsWith('.ssa') || /^\[Script Info\]/m.test(t)) return parseAss(t);
  if (lower.endsWith('.vtt') || /^WEBVTT/.test(t)) return parseVtt(t);
  return parseSrt(t);
}

function tc(s) {
  const m = /(\d+):(\d{2}):(\d{2})[.,](\d{1,3})/.exec(s) || /(\d{1,2}):(\d{2})[.,](\d{1,3})/.exec(s);
  if (!m) return 0;
  if (m.length === 5) return (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + (+m[4].padEnd(3, '0')) / 1000;
  return (+m[1]) * 60 + (+m[2]) + (+m[3].padEnd(3, '0')) / 1000;
}

function cleanText(s) {
  return s.replace(/<\/?(?:b|i|u|font|c)[^>]*>/gi, '').replace(/\{\\[^}]*\}/g, '').replace(/&nbsp;/g, ' ').trim();
}

function parseSrt(t) {
  const cues = [];
  for (const block of t.split(/\n{2,}/)) {
    const lines = block.split('\n').filter(Boolean);
    if (lines.length < 2) continue;
    let i = /^\d+$/.test(lines[0]) ? 1 : 0;
    const m = /(\S+)\s*-->\s*(\S+)/.exec(lines[i] || '');
    if (!m) continue;
    const text = cleanText(lines.slice(i + 1).join('\n'));
    if (text) cues.push({ start: tc(m[1]), end: tc(m[2]), text });
  }
  return finish(cues);
}

function parseVtt(t) {
  const cues = [];
  for (const block of t.split(/\n{2,}/)) {
    const lines = block.split('\n').filter(Boolean);
    const idx = lines.findIndex(l => l.includes('-->'));
    if (idx < 0) continue;
    const m = /(\S+)\s*-->\s*(\S+)/.exec(lines[idx]);
    const text = cleanText(lines.slice(idx + 1).join('\n'));
    if (m && text) cues.push({ start: tc(m[1]), end: tc(m[2]), text });
  }
  return finish(cues);
}

function parseAss(t) {
  const cues = [];
  let fmt = null;
  for (const line of t.split('\n')) {
    if (/^Format:/i.test(line) && /Start/i.test(line) && /Text/i.test(line)) { fmt = line.slice(7).split(',').map(s => s.trim().toLowerCase()); continue; }
    if (!/^Dialogue:/i.test(line) || !fmt) continue;
    const parts = line.slice(9).split(',');
    const textIdx = fmt.indexOf('text');
    const start = tc(parts[fmt.indexOf('start')] || '');
    const end = tc(parts[fmt.indexOf('end')] || '');
    const text = cleanText(parts.slice(textIdx).join(',').replace(/\\N/g, '\n'));
    if (text) cues.push({ start, end, text });
  }
  return finish(cues);
}

function finish(cues) {
  cues.sort((a, b) => a.start - b.start);
  return cues;
}

/** Returns the active cue text at time t (or ''), using binary search over start times. */
export function cueAt(cues, t) {
  if (!cues || !cues.length) return '';
  let lo = 0, hi = cues.length - 1, idx = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (cues[mid].start <= t) { idx = mid; lo = mid + 1; } else hi = mid - 1;
  }
  const out = [];
  for (let i = Math.max(0, idx - 3); i <= idx && i < cues.length; i++) if (cues[i].start <= t && t <= cues[i].end) out.push(cues[i].text);
  return out.join('\n');
}
