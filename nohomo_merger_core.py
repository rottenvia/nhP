import os
import re
import json
import time
import shutil
import hashlib
import subprocess
import sys
from pathlib import Path

VIDEO_EXTS = {'.ts', '.mkv', '.mp4', '.avi', '.m4v', '.mov', '.webm'}
CONFIG_FILE = 'nohomo_config.json'

DEFAULT_CONFIG = {
    "raw_folder": "./raw",
    "dub_folder": "./dub",
    "output_folder": "./output",
    "test_folder": "./test",
    "ffmpeg_path": "ffmpeg",
    "ffprobe_path": "ffprobe",
    "dub_audio_track": 0,
    "delete_ts_after_remux": True,
    "cut_segments": "",
    "voice_isolation": "off",  # off | demucs
    "organize_after_merge": True,
    "library_root": ""
}


def load_config(base_dir=None):
    base = Path(base_dir or os.getcwd())
    cfg_path = base / CONFIG_FILE
    cfg = dict(DEFAULT_CONFIG)
    if cfg_path.exists():
        try:
            with cfg_path.open('r', encoding='utf-8') as f:
                user_cfg = json.load(f)
            if isinstance(user_cfg, dict):
                cfg.update(user_cfg)
        except Exception:
            pass
    else:
        try:
            with cfg_path.open('w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
    cfg['_base_dir'] = str(base)
    # Always create workflow folders next to app/config when paths are relative.
    for key in ('raw_folder', 'dub_folder', 'output_folder', 'test_folder'):
        try:
            Path(resolve_path(cfg.get(key), cfg)).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    return cfg


def resolve_path(path_value, cfg):
    path = Path(path_value or '.')
    if path.is_absolute():
        return str(path)
    base = Path(cfg.get('_base_dir') or os.getcwd())
    return str((base / path).resolve())


def parse_time_to_seconds(value):
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    if ':' in text:
        parts = [p.strip() for p in text.split(':')]
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except Exception:
            return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def parse_cut_segments(value):
    if not value:
        return []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                a = float(item[0]); b = float(item[1])
                if a < b:
                    out.append((a, b))
        return out
    out = []
    for part in re.split(r'[,;]', str(value)):
        part = part.strip()
        if not part:
            continue
        pieces = re.split(r'\s*-\s*|\s*/\s+', part)
        if len(pieces) == 2:
            a = parse_time_to_seconds(pieces[0])
            b = parse_time_to_seconds(pieces[1])
            if a < b:
                out.append((a, b))
    return out


def run_cmd(cmd, timeout=120):
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            startupinfo=startupinfo
        )
    except subprocess.TimeoutExpired as e:
        return subprocess.CompletedProcess(cmd, 124, '', f'Timeout after {timeout}s: {e}')


def ffprobe_json(path, cfg):
    cmd = [cfg.get('ffprobe_path') or 'ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(path)]
    res = run_cmd(cmd, timeout=30)
    if res.returncode != 0:
        return {}
    try:
        return json.loads(res.stdout or '{}')
    except Exception:
        return {}


def get_duration(path, cfg):
    data = ffprobe_json(path, cfg)
    try:
        if data.get('format', {}).get('duration'):
            return float(data['format']['duration'])
    except Exception:
        pass
    for stream in data.get('streams', []):
        try:
            if stream.get('duration'):
                return float(stream['duration'])
        except Exception:
            pass
    return None


def validate_video_file(path, cfg):
    """Fast sanity check before merge.
    Catches incomplete torrent files / broken MKV EBML headers before FFmpeg mux fails later.
    """
    try:
        p = Path(path)
        if not p.exists():
            return False, 'file missing'
        if p.stat().st_size < 1024 * 1024:
            return False, 'file too small / incomplete'
        data = ffprobe_json(str(p), cfg)
        if not data:
            return False, 'ffprobe could not read container; file is incomplete or corrupt'
        streams = data.get('streams') or []
        has_video = any(st.get('codec_type') == 'video' for st in streams)
        has_audio = any(st.get('codec_type') == 'audio' for st in streams)
        if not (has_video or has_audio):
            return False, 'no video/audio streams detected'
        # TS downloads often have no reliable duration; MKV/MP4 should usually have one.
        ext = p.suffix.lower()
        dur = None
        try:
            dur = float(data.get('format', {}).get('duration') or 0)
        except Exception:
            dur = 0
        if ext in ('.mkv', '.mp4', '.m4v', '.webm') and dur <= 0:
            return False, 'duration missing; likely still downloading or damaged'
        return True, ''
    except Exception as e:
        return False, str(e)


def get_audio_tracks(path, cfg):
    data = ffprobe_json(path, cfg)
    tracks = []
    rel = 0
    for s in data.get('streams', []):
        if s.get('codec_type') == 'audio':
            tracks.append({
                'index': s.get('index'),
                'rel_index': rel,
                'codec': s.get('codec_name', '?'),
                'channels': s.get('channels', '?'),
                'sample_rate': s.get('sample_rate', '?'),
                'language': s.get('tags', {}).get('language', 'und'),
                'title': s.get('tags', {}).get('title', '')
            })
            rel += 1
    return tracks


def extract_episode(filename):
    name = os.path.basename(filename)
    patterns = [
        r'[Ss]\d{1,2}[Ee](\d{1,3})',
        r'\b[Ee][Pp]?(\d{1,3})\b',
        r'(?:Episode|Ep|Серия|Серии)[\s._-]*(\d{1,3})',
        r'[._\-\s](\d{1,3})[._\-\s]*(?:v\d+)?(?:\.[a-z0-9]+)?$'
    ]
    for pat in patterns:
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 999:
                return n
    m = re.match(r'^(\d{1,3})[\s._\-]', name)
    if m:
        return int(m.group(1))
    return None


def title_key_from_name(filename):
    """Rough movie/title key for matching RAW movie releases with Russian DUB filenames.
    Not used for episode anime matching unless episode is missing.
    """
    name = Path(filename).stem.lower()
    # bilingual known aliases. Extend here as real-world cases appear.
    aliases = {
        'диктатор': 'dictator',
        'the dictator': 'dictator',
        'dictator': 'dictator',
        'с широко закрытыми глазами': 'eyeswideshut',
        'eyes wide shut': 'eyeswideshut',
        'зодиак': 'zodiac',
        'zodiac': 'zodiac',
    }
    for k, v in aliases.items():
        if k in name:
            return v
    # Drop codec/release noise and years/quality.
    noise = [
        '2160p','1080p','720p','480p','bluray','blu-ray','bdrip','brrip','web-dl','webrip','hdtv','remux',
        'x264','x265','h264','h265','hevc','avc','10bit','8bit','hdr','dv','dolby','vision','aac','ac3','ddp','dts',
        'truehd','atmos','multi','rus','russian','english','eng','ukr','sub','subs','esub','yify','yts','rarbg','rbg',
        'unrated','theatrical','extended','proper','repack','org','mp4','mkv','ts'
    ]
    text = re.sub(r'\b(19|20)\d{2}\b', ' ', name)
    for n in noise:
        text = re.sub(r'\b' + re.escape(n) + r'\b', ' ', text)
    # simple Cyrillic transliteration fallback
    table = str.maketrans({
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'i','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
    })
    text = text.translate(table)
    text = re.sub(r'[^a-z0-9а-яё]+', '', text)
    # remove leading articles after cleanup
    text = re.sub(r'^(the|a|an)', '', text)
    return text[:80]


def extract_season(filename):
    name = os.path.basename(filename)
    m = re.search(r'[Ss](\d{1,2})[Ee]\d{1,3}', name)
    if m:
        return int(m.group(1))
    m = re.search(r'(?:Season|Сезон)[\s._-]*(\d{1,2})', name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return 1


def find_videos(folder):
    root = Path(folder)
    if not root.exists():
        return []
    files = []
    for p in root.rglob('*'):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            files.append({
                'path': str(p),
                'name': p.name,
                'season': extract_season(p.name),
                'episode': extract_episode(p.name),
                'title_key': title_key_from_name(p.name),
                'size_mb': round(size / 1048576, 2)
            })
    files.sort(key=lambda x: (x['season'], x['episode'] or 9999, x['name'].lower()))
    return files


def match_files(raw_files, dub_files):
    matched = []
    used = set()

    # 1) Normal episode/season matching.
    for raw in raw_files:
        if raw.get('valid') is False:
            continue
        if raw.get('episode') is None:
            continue
        best_idx = None
        for i, dub in enumerate(dub_files):
            if i in used or dub.get('valid') is False or dub.get('episode') is None:
                continue
            if dub['episode'] == raw['episode'] and dub['season'] == raw['season']:
                best_idx = i
                break
        if best_idx is None:
            for i, dub in enumerate(dub_files):
                if i in used or dub.get('valid') is False or dub.get('episode') is None:
                    continue
                if dub['episode'] == raw['episode']:
                    best_idx = i
                    break
        if best_idx is not None:
            used.add(best_idx)
            matched.append({'raw': raw, 'dub': dub_files[best_idx]})

    # 2) Movie/special matching by title when no episode numbers exist.
    raw_no_ep = [r for r in raw_files if r.get('valid') is not False and r.get('episode') is None]
    dub_no_ep = [(i, d) for i, d in enumerate(dub_files) if i not in used and d.get('valid') is not False and d.get('episode') is None]
    for raw in raw_no_ep:
        rk = raw.get('title_key') or title_key_from_name(raw.get('name', ''))
        if not rk or len(rk) < 4:
            continue
        best_idx = None
        best_score = 0
        for i, dub in dub_no_ep:
            if i in used:
                continue
            dk = dub.get('title_key') or title_key_from_name(dub.get('name', ''))
            if not dk or len(dk) < 4:
                continue
            score = 0
            if rk == dk:
                score = 100
            elif rk in dk or dk in rk:
                score = 70
            else:
                # token overlap fallback
                rt = set(re.findall(r'[a-zа-яё0-9]{4,}', rk))
                dt = set(re.findall(r'[a-zа-яё0-9]{4,}', dk))
                if rt and dt:
                    score = int(100 * len(rt & dt) / max(len(rt | dt), 1))
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx is not None and best_score >= 60:
            used.add(best_idx)
            # Treat movies as S01E01 for downstream organizer/linker.
            raw2 = dict(raw); dub2 = dict(dub_files[best_idx])
            raw2['season'] = raw2.get('season') or 1; raw2['episode'] = 1
            dub2['season'] = dub2.get('season') or 1; dub2['episode'] = 1
            matched.append({'raw': raw2, 'dub': dub2, 'match_mode': 'movie_title', 'match_score': best_score})

    return matched


def remux_ts_files(folder, cfg):
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    count = 0
    for f in find_videos(folder):
        path = Path(f['path'])
        if path.suffix.lower() != '.ts':
            continue
        mkv = path.with_suffix('.mkv')
        if mkv.exists() and mkv.stat().st_size > 1024:
            continue
        cmd = [ffmpeg, '-y', '-i', str(path), '-c', 'copy', '-map', '0:v?', '-map', '0:a?', '-map', '0:s?', '-dn', str(mkv)]
        res = run_cmd(cmd, timeout=180)
        if res.returncode == 0 and mkv.exists() and mkv.stat().st_size > 1024:
            count += 1
            if cfg.get('delete_ts_after_remux', True):
                try:
                    path.unlink()
                except Exception:
                    pass
    return count


def ensure_numpy():
    try:
        import numpy as np
        return np
    except Exception:
        import sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'numpy'])
        import numpy as np
        return np


def autosync_music(raw_path, dub_path, cfg, dub_track=0, analyze_start=30, analyze_dur=300):
    np = ensure_numpy()
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    test_dir = Path(resolve_path(cfg.get('test_folder') or './test', cfg))
    test_dir.mkdir(parents=True, exist_ok=True)
    sr = 8000
    wav_raw = test_dir / '_sync_raw.wav'
    wav_dub = test_dir / '_sync_dub.wav'
    cmds = [
        [ffmpeg, '-y', '-ss', str(analyze_start), '-i', raw_path, '-t', str(analyze_dur), '-vn', '-ac', '1', '-ar', str(sr), '-af', 'lowpass=f=250,highpass=f=60', '-acodec', 'pcm_s16le', str(wav_raw)],
        [ffmpeg, '-y', '-ss', str(analyze_start), '-i', dub_path, '-t', str(analyze_dur), '-vn', '-map', f'0:a:{dub_track}', '-ac', '1', '-ar', str(sr), '-af', 'lowpass=f=250,highpass=f=60', '-acodec', 'pcm_s16le', str(wav_dub)]
    ]
    try:
        for cmd in cmds:
            res = run_cmd(cmd, timeout=90)
            if res.returncode != 0:
                return {'ok': False, 'method': 'music', 'error': res.stderr[-1200:]}

        def read_wav(path):
            with open(path, 'rb') as f:
                f.read(44)
                return np.frombuffer(f.read(), dtype=np.int16).astype(np.float64)

        raw = read_wav(wav_raw)
        dub = read_wav(wav_dub)
        if raw.size == 0 or dub.size == 0:
            return {'ok': False, 'method': 'music', 'error': 'empty audio data'}
        window = int(sr * 0.050)
        hop = int(sr * 0.010)

        def envelope(data):
            n = max(0, (len(data) - window) // hop)
            env = np.zeros(n)
            for i in range(n):
                chunk = data[i * hop:i * hop + window]
                env[i] = np.sqrt(np.mean(chunk ** 2))
            return env

        raw_env = envelope(raw)
        dub_env = envelope(dub)
        raw_env /= (np.max(raw_env) + 1e-10)
        dub_env /= (np.max(dub_env) + 1e-10)
        corr = np.correlate(raw_env, dub_env, mode='full')
        center = len(dub_env) - 1
        max_lag = int(20.0 / (hop / sr))
        start = max(0, center - max_lag)
        end = min(len(corr), center + max_lag)
        region = corr[start:end]
        if region.size == 0:
            return {'ok': False, 'method': 'music', 'error': 'empty correlation region'}
        peak = int(np.argmax(region) + start)
        lag = (peak - center) * (hop / sr)
        norm = np.sqrt(np.sum(raw_env ** 2) * np.sum(dub_env ** 2))
        confidence = float(corr[peak] / (norm + 1e-10)) if norm > 0 else 0.0
        return {'ok': confidence >= 0.30, 'method': 'music', 'offset': round(float(lag), 1), 'raw_offset': float(lag), 'confidence': confidence}
    finally:
        for p in (wav_raw, wav_dub):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass


def autosync(raw_path, dub_path, cfg, dub_track=0):
    return autosync_music(raw_path, dub_path, cfg, dub_track=dub_track)


def autosync_multipoint(raw_path, dub_path, cfg, dub_track=0, window_dur=120):
    """Safe Pro-sync wrapper.

    Earlier UI exposed Auto Pro / Multi-Point, but the function body was missing in this build,
    causing batch merge to fail with: name 'autosync_multipoint' is not defined.

    This implementation is intentionally conservative: it samples several windows, returns a
    recommended global offset when stable, and only reports true multipoint when drift is clear.
    If analysis cannot run, caller still falls back to normal global processing.
    """
    anchors = []
    try:
        raw_dur = get_duration(raw_path, cfg) or 0
        if raw_dur <= 0:
            base = autosync(raw_path, dub_path, cfg, dub_track=dub_track)
            return {
                'ok': bool(base.get('ok')),
                'mode': 'global',
                'recommended_offset': base.get('offset', 0),
                'drift': 0,
                'anchors': [],
                'base': base
            }
        starts = []
        for pct in (0.12, 0.35, 0.62, 0.82):
            st = max(15, min(max(15, raw_dur - window_dur - 10), raw_dur * pct))
            if all(abs(st - x) > 90 for x in starts):
                starts.append(st)
        for st in starts:
            try:
                res = autosync_music(raw_path, dub_path, cfg, dub_track=dub_track, analyze_start=st, analyze_dur=min(window_dur, max(45, raw_dur - st - 5)))
                if res.get('ok') and res.get('offset') is not None:
                    anchors.append({'time': round(float(st), 2), 'offset': float(res.get('offset') or 0), 'confidence': float(res.get('confidence') or 0)})
            except Exception:
                continue
        if not anchors:
            base = autosync(raw_path, dub_path, cfg, dub_track=dub_track)
            return {'ok': bool(base.get('ok')), 'mode': 'global', 'recommended_offset': base.get('offset', 0), 'drift': 0, 'anchors': [], 'base': base}
        # Weighted median-ish average, confidence-weighted but bounded.
        total_w = sum(max(0.1, a.get('confidence', 0.1)) for a in anchors)
        rec = sum(a['offset'] * max(0.1, a.get('confidence', 0.1)) for a in anchors) / max(total_w, 1e-6)
        drift = max(a['offset'] for a in anchors) - min(a['offset'] for a in anchors)
        mode = 'multipoint' if len(anchors) >= 3 and abs(drift) >= 0.35 else 'global'
        return {'ok': True, 'mode': mode, 'recommended_offset': round(rec, 2), 'drift': round(drift, 3), 'anchors': anchors}
    except Exception as e:
        return {'ok': False, 'mode': 'global', 'recommended_offset': 0, 'drift': 0, 'anchors': anchors, 'error': str(e)}


def atempo_filter_chain(ratio):
    """FFmpeg atempo supports 0.5..2.0 per filter. Return a comma chain."""
    try:
        ratio = float(ratio)
    except Exception:
        return []
    if ratio <= 0 or abs(ratio - 1.0) < 0.0008:
        return []
    parts = []
    while ratio < 0.5:
        parts.append('atempo=0.5')
        ratio /= 0.5
    while ratio > 2.0:
        parts.append('atempo=2.0')
        ratio /= 2.0
    parts.append(f'atempo={ratio:.8f}')
    return parts


def extract_multipoint_audio(dub_path, cfg, raw_dur, dub_dur, anchors, dub_track=0):
    """True segment-based multipoint retime.

    Anchor convention: offset > 0 means the DUB audio must be delayed to match RAW.
    Therefore the DUB source time corresponding to RAW time T is approximately T - offset(T).

    Pipeline:
      anchors -> piecewise raw/dub segments -> atempo per segment -> tiny fades -> concat -> AAC.

    This is intentionally conservative and transparent. If usable anchors are not available or
    segment retime fails, caller can fall back to weighted global offset.
    """
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    out_dir = Path(resolve_path(cfg.get('output_folder') or './output', cfg))
    work_dir = out_dir / '_multipoint'
    work_dir.mkdir(parents=True, exist_ok=True)
    final_aac = out_dir / '_temp_nohomo_rus_multipoint.aac'
    concat_list = work_dir / 'concat_segments.txt'
    segment_paths = []
    try:
        raw_dur = float(raw_dur or 0)
        dub_dur = float(dub_dur or 0)
        clean = []
        for a in anchors or []:
            try:
                t = float(a.get('time'))
                o = float(a.get('offset'))
                conf = float(a.get('confidence') or 0.3)
                if 0 <= t <= raw_dur and abs(o) < 60:
                    clean.append({'time': t, 'offset': o, 'confidence': conf})
            except Exception:
                continue
        clean.sort(key=lambda x: x['time'])
        # Deduplicate close anchors; keep stronger confidence.
        dedup = []
        for a in clean:
            if dedup and abs(a['time'] - dedup[-1]['time']) < 45:
                if a['confidence'] > dedup[-1].get('confidence', 0):
                    dedup[-1] = a
            else:
                dedup.append(a)
        clean = dedup
        if len(clean) < 2 or raw_dur <= 10:
            return None, 'not enough anchors for true multipoint retime'

        # Boundaries: start/end with nearest offsets, plus anchors.
        points = [{'time': 0.0, 'offset': clean[0]['offset'], 'confidence': clean[0].get('confidence', 0.3)}]
        points.extend(clean)
        if points[-1]['time'] < raw_dur:
            points.append({'time': raw_dur, 'offset': clean[-1]['offset'], 'confidence': clean[-1].get('confidence', 0.3)})

        # Convert adjacent anchor points to segments. Merge very short spans into neighbours implicitly by skipping.
        segments = []
        for i in range(len(points) - 1):
            r0, r1 = float(points[i]['time']), float(points[i + 1]['time'])
            o0, o1 = float(points[i]['offset']), float(points[i + 1]['offset'])
            target_dur = r1 - r0
            if target_dur < 8:
                continue
            d0 = r0 - o0
            d1 = r1 - o1
            # Clamp source times to available DUB. Preserve target duration with apad/atrim later.
            src_start = max(0.0, d0)
            src_end = max(src_start + 0.05, d1)
            if dub_dur:
                src_end = min(max(src_start + 0.05, src_end), dub_dur)
            src_dur = max(0.05, src_end - src_start)
            tempo = src_dur / max(target_dur, 0.05)
            # Avoid insane tempo from bad anchors; caller will fallback if this happens often.
            if tempo < 0.80 or tempo > 1.25:
                # Cap rather than explode. This still corrects moderate drift but avoids chipmunk/slow artifacts.
                tempo = max(0.80, min(1.25, tempo))
            segments.append({
                'raw_start': r0, 'raw_end': r1, 'target_dur': target_dur,
                'src_start': src_start, 'src_dur': src_dur, 'tempo': tempo,
                'offset0': o0, 'offset1': o1
            })

        if len(segments) < 2:
            return None, 'not enough valid multipoint segments after cleanup'

        # Build WAV segments. Tiny fades reduce clicks at concat boundaries.
        for i, seg in enumerate(segments):
            seg_path = work_dir / f'segment_{i:03d}.wav'
            filters = []
            filters.extend(atempo_filter_chain(seg['tempo']))
            fade_d = min(0.035, max(0.005, seg['target_dur'] / 500.0))
            if i > 0:
                filters.append(f'afade=t=in:st=0:d={fade_d:.4f}')
            if i < len(segments) - 1 and seg['target_dur'] > fade_d * 4:
                filters.append(f'afade=t=out:st={max(0, seg["target_dur"] - fade_d):.4f}:d={fade_d:.4f}')
            filters.append('apad')
            filters.append(f'atrim=duration={seg["target_dur"]:.6f}')
            filters.append('asetpts=PTS-STARTPTS')
            filters.append('aresample=48000')
            cmd = [
                ffmpeg, '-y', '-ss', f'{seg["src_start"]:.6f}', '-t', f'{seg["src_dur"]:.6f}',
                '-i', dub_path, '-map', f'0:a:{dub_track}', '-vn',
                '-af', ','.join(filters), '-ac', '2', '-ar', '48000', '-acodec', 'pcm_s16le', str(seg_path)
            ]
            res = run_cmd(cmd, timeout=180)
            if res.returncode != 0 or not seg_path.exists() or seg_path.stat().st_size < 1024:
                return None, f'multipoint segment {i} failed: {res.stderr[-1800:]}'
            segment_paths.append(seg_path)

        with concat_list.open('w', encoding='utf-8') as f:
            for sp in segment_paths:
                # ffmpeg concat demuxer wants forward slash or escaped paths.
                f.write("file '" + str(sp).replace("'", "'\\''") + "'\n")

        cmd = [ffmpeg, '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_list), '-c:a', 'aac', '-b:a', '192k']
        if raw_dur:
            cmd.extend(['-t', f'{raw_dur:.6f}'])
        cmd.append(str(final_aac))
        res = run_cmd(cmd, timeout=240)
        if res.returncode != 0 or not final_aac.exists() or final_aac.stat().st_size < 1024:
            return None, f'multipoint concat failed: {res.stderr[-2000:]}'
        return str(final_aac), ''
    except Exception as e:
        return None, str(e)
    finally:
        # Keep the final AAC, remove segment temp files/list.
        try:
            for sp in segment_paths:
                try:
                    sp.unlink(missing_ok=True)
                except Exception:
                    pass
            concat_list.unlink(missing_ok=True)
            try:
                work_dir.rmdir()
            except Exception:
                pass
        except Exception:
            pass


def extract_processed_audio(dub_path, cfg, raw_dur, dub_dur, offset=0.0, dub_track=0):
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    out_dir = Path(resolve_path(cfg.get('output_folder') or './output', cfg))
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_wav = out_dir / '_temp_nohomo_raw.wav'
    temp_aac = out_dir / '_temp_nohomo_rus.aac'
    cuts = parse_cut_segments(cfg.get('cut_segments'))
    cmd_wav = [ffmpeg, '-y', '-i', dub_path, '-map', f'0:a:{dub_track}', '-vn', '-ac', '2', '-ar', '48000', '-af', 'aresample=async=1', '-acodec', 'pcm_s16le']
    if dub_dur:
        cmd_wav.extend(['-t', str(dub_dur + 5)])
    cmd_wav.append(str(temp_wav))
    res = run_cmd(cmd_wav, timeout=120)
    if res.returncode != 0:
        return None, res.stderr[-2000:]

    actual = get_duration(str(temp_wav), cfg)
    if actual:
        dub_dur = actual

    filters = []
    if cuts:
        conds = [f"not(between(t,{a},{b}))" for a, b in cuts]
        filters.append("aselect='" + '*'.join(conds) + "'")
        filters.append('asetpts=N/SR/TB')
        dub_dur = max(0.1, (dub_dur or 0) - sum(b - a for a, b in cuts))
    if offset > 0:
        ms = int(offset * 1000)
        filters.append(f'adelay={ms}|{ms}')
    elif offset < 0:
        filters.append(f'atrim=start={abs(offset):.3f}')
        filters.append('asetpts=PTS-STARTPTS')
    if raw_dur and dub_dur:
        target = raw_dur - offset if offset > 0 else raw_dur
        effective = dub_dur if offset >= 0 else max(0.1, dub_dur - abs(offset))
        if target > 0 and effective > 0:
            ratio = effective / target
            if abs(ratio - 1.0) > 0.0001:
                if 0.5 <= ratio <= 2.0:
                    filters.append(f'atempo={ratio:.6f}')
                elif ratio < 0.5:
                    filters.append(f'atempo=0.5,atempo={ratio / 0.5:.6f}')
                else:
                    filters.append(f'atempo=2.0,atempo={ratio / 2.0:.6f}')
    cmd = [ffmpeg, '-y', '-i', str(temp_wav)]
    if filters:
        cmd.extend(['-af', ','.join(filters)])
    cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    if raw_dur:
        cmd.extend(['-t', str(raw_dur)])
    cmd.append(str(temp_aac))
    res = run_cmd(cmd, timeout=180)
    try:
        temp_wav.unlink(missing_ok=True)
    except Exception:
        pass
    if res.returncode != 0:
        return None, res.stderr[-2000:]
    return str(temp_aac), ''



def command_exists(cmd):
    try:
        res = run_cmd([cmd, '--help'], timeout=8)
        return res.returncode in (0, 1)
    except Exception:
        return False


def extract_raw_audio(raw_path, cfg, raw_dur=None):
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    out_dir = Path(resolve_path(cfg.get('output_folder') or './output', cfg))
    out_dir.mkdir(parents=True, exist_ok=True)
    temp = out_dir / '_temp_nohomo_raw_original.wav'
    cmd = [ffmpeg, '-y', '-i', raw_path, '-map', '0:a:0?', '-vn', '-ac', '2', '-ar', '48000', '-af', 'aresample=async=1', '-acodec', 'pcm_s16le']
    if raw_dur:
        cmd.extend(['-t', str(raw_dur)])
    cmd.append(str(temp))
    res = run_cmd(cmd, timeout=180)
    if res.returncode != 0 or not temp.exists():
        return None, res.stderr[-2000:]
    return str(temp), ''


def run_demucs_two_stems(audio_path, cfg, stem='vocals'):
    """Runs Demucs two-stem separation and returns paths to vocals/no_vocals.
    Requires user-installed demucs (`pip install demucs`). Fully optional; fallback is handled by caller.
    """
    out_dir = Path(resolve_path(cfg.get('output_folder') or './output', cfg)) / '_demucs'
    out_dir.mkdir(parents=True, exist_ok=True)
    demucs_path = str(cfg.get('demucs_path') or '').strip()
    # Windows user installs often place demucs.exe outside PATH. `python -m demucs` is more reliable.
    if demucs_path:
        cmd = [demucs_path, '--two-stems', 'vocals', '-n', 'htdemucs', '-o', str(out_dir), str(audio_path)]
    else:
        cmd = [sys.executable, '-m', 'demucs', '--two-stems', 'vocals', '-n', 'htdemucs', '-o', str(out_dir), str(audio_path)]
    res = run_cmd(cmd, timeout=1800)
    if res.returncode != 0:
        return None, None, res.stderr[-4000:]
    base = Path(audio_path).stem
    candidates = list(out_dir.rglob(base))
    if not candidates:
        # Demucs folder may be model_name/base
        candidates = [x for x in out_dir.rglob('*') if x.is_dir() and x.name == base]
    if not candidates:
        return None, None, 'Demucs output folder not found'
    folder = candidates[0]
    vocals = folder / 'vocals.wav'
    no_vocals = folder / 'no_vocals.wav'
    if not vocals.exists() or not no_vocals.exists():
        return None, None, 'Demucs stems missing'
    return str(vocals), str(no_vocals), ''


def build_voice_overlay_track(raw_path, processed_dub_audio, cfg, raw_dur=None):
    """Creates a Russian track with RAW music/SFX + isolated Russian voice.
    Pipeline:
      1. Extract RAW original audio.
      2. Demucs RAW -> no_vocals (music/SFX without Japanese speech as much as possible).
      3. Demucs processed DUB -> vocals (Russian voice as much as possible).
      4. Mix RAW no_vocals + DUB vocals into AAC.
    If Demucs is unavailable/fails, returns None and caller falls back to processed full DUB.
    """
    mode = str(cfg.get('voice_isolation') or 'off').lower()
    if mode not in ('demucs', 'on', 'true'):
        return None, 'voice isolation disabled'
    raw_wav, err = extract_raw_audio(raw_path, cfg, raw_dur)
    if not raw_wav:
        return None, err
    raw_vocals, raw_no_vocals, err1 = run_demucs_two_stems(raw_wav, cfg)
    dub_vocals, dub_no_vocals, err2 = run_demucs_two_stems(processed_dub_audio, cfg)
    if not raw_no_vocals or not dub_vocals:
        return None, (err1 or err2 or 'Demucs failed')
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    out_dir = Path(resolve_path(cfg.get('output_folder') or './output', cfg))
    mixed = out_dir / '_temp_nohomo_voice_overlay.aac'
    # Sidechain-ish stable mix: RAW accompaniment slightly reduced, Russian voice forward.
    filter_complex = '[0:a]volume=0.82[a0];[1:a]volume=1.25[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0,alimiter=limit=0.98'
    cmd = [ffmpeg, '-y', '-i', raw_no_vocals, '-i', dub_vocals, '-filter_complex', filter_complex, '-c:a', 'aac', '-b:a', '224k']
    if raw_dur:
        cmd.extend(['-t', str(raw_dur)])
    cmd.append(str(mixed))
    res = run_cmd(cmd, timeout=240)
    try:
        Path(raw_wav).unlink(missing_ok=True)
    except Exception:
        pass
    if res.returncode != 0 or not mixed.exists():
        return None, res.stderr[-2000:]
    return str(mixed), ''

def merge(raw_path, dub_path, output_path, cfg, offset=0.0, dub_track=0, voice_mode=None, sync_mode="global"):
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    raw_dur = get_duration(raw_path, cfg)
    dub_dur = get_duration(dub_path, cfg)
    # Hard guard: if movie/episode sources are different cuts (e.g. RAW Unrated 1:38 vs DUB Theatrical 1:23),
    # no sync algorithm can honestly fix it. Refuse early with a clear reason instead of producing a bad mux.
    if raw_dur and dub_dur:
        delta = abs(float(raw_dur) - float(dub_dur))
        rel = delta / max(float(raw_dur), float(dub_dur), 1.0)
        if delta > 480 and rel > 0.08:
            return {
                'ok': False,
                'error': f'duration mismatch: RAW {raw_dur/60:.1f} min vs DUB {dub_dur/60:.1f} min (delta {delta/60:.1f} min). These are different cuts/versions; choose matching RAW/DUB (theatrical with theatrical, unrated/extended with unrated/extended).',
                'sync_note': 'refused_duration_mismatch',
                'sync_analysis': {'raw_duration': raw_dur, 'dub_duration': dub_dur, 'delta': delta, 'relative_delta': rel}
            }
    sync_note = 'global'
    sync_analysis = None
    temp_audio = None
    err = ''
    requested_sync_mode = str(sync_mode or cfg.get('sync_mode') or 'global').lower()
    if requested_sync_mode in ('auto', 'multipoint', 'pro', 'drift') and raw_dur:
        sync_analysis = autosync_multipoint(raw_path, dub_path, cfg, dub_track=dub_track)
        anchors = sync_analysis.get('anchors', []) if sync_analysis else []
        if sync_analysis and sync_analysis.get('recommended_offset') is not None:
            offset = float(sync_analysis.get('recommended_offset') or offset)
        # User-facing Auto Pro should be REAL multipoint whenever anchors exist.
        # We no longer skip multipoint just because drift looks small: if 2+ reliable anchors are found,
        # build segment-based retime. Fallback to weighted/global only when anchors are missing or retime fails.
        use_multipoint = bool(sync_analysis and sync_analysis.get('ok') and len(anchors) >= 2)
        if use_multipoint:
            temp_audio, err = extract_multipoint_audio(dub_path, cfg, raw_dur, dub_dur, anchors, dub_track)
            if temp_audio:
                sync_note = f"true multipoint retime, {max(0, len(anchors) + 1)} segments, drift={sync_analysis.get('drift')}s, anchors={len(anchors)}"
            else:
                sync_note = f"multipoint failed -> weighted global from {len(anchors)} anchors, drift={sync_analysis.get('drift')}s, offset={offset}s, err={str(err)[:180]}"
        else:
            if anchors:
                sync_note = f"weighted global from {len(anchors)} anchors, drift={sync_analysis.get('drift')}s, offset={offset}s"
            else:
                sync_note = f"global, offset={offset}s"
    if not temp_audio:
        temp_audio, err = extract_processed_audio(dub_path, cfg, raw_dur, dub_dur, offset, dub_track)
    if not temp_audio:
        return {'ok': False, 'error': err or 'audio extraction failed', 'sync_note': sync_note, 'sync_analysis': sync_analysis}
    voice_note = ''
    voice_overlay_audio = None
    # Optional advanced mode: keep RAW music/SFX and overlay isolated Russian voice.
    # This helps when lip-sync is correct but gunshots/SFX differ between TV/DUB and RAW/BD timing.
    requested_voice_mode = (voice_mode or cfg.get('voice_isolation') or 'off')
    if str(requested_voice_mode).lower() in ('demucs', 'on', 'true'):
        voice_overlay_audio, voice_err = build_voice_overlay_track(raw_path, temp_audio, cfg, raw_dur)
        if voice_overlay_audio:
            voice_note = 'demucs_voice_overlay'
            try:
                Path(temp_audio).unlink(missing_ok=True)
            except Exception:
                pass
            temp_audio = voice_overlay_audio
        else:
            voice_note = 'voice_overlay_failed_fallback_full_dub: ' + (voice_err or '')[:500]
    output_path = str(output_path)
    if not output_path.lower().endswith('.mkv'):
        output_path = os.path.splitext(output_path)[0] + '.mkv'
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    raw_audio_count = 0
    try:
        raw_audio_count = len(get_audio_tracks(raw_path, cfg))
    except Exception:
        raw_audio_count = 0

    # Robust mux command. Do not set metadata/disposition for non-existent a:1;
    # FFmpeg can fail with "matches no streams" on RAW files with no original audio.
    cmd = [
        ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-fflags', '+genpts',
        '-i', raw_path, '-i', temp_audio,
        '-map', '0:v:0', '-map', '1:a:0'
    ]
    if raw_audio_count > 0:
        cmd += ['-map', '0:a:0?']
    cmd += ['-map', '0:s?', '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'copy', '-disposition:a:0', 'default']
    if raw_audio_count > 0:
        cmd += ['-disposition:a:1', '0']
    cmd += ['-metadata:s:a:0', 'language=rus', '-metadata:s:a:0', 'title=Russian Dub' + (' Voice Overlay' if voice_note == 'demucs_voice_overlay' else '')]
    if raw_audio_count > 0:
        cmd += ['-metadata:s:a:1', 'language=jpn', '-metadata:s:a:1', 'title=Original']
    cmd += [output_path]

    res = run_cmd(cmd, timeout=900)
    if res.returncode != 0:
        first_err = res.stderr[-3000:]
        # Last-resort mux: video + Russian audio only, no subtitles/original audio metadata.
        fallback_cmd = [
            ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-fflags', '+genpts',
            '-i', raw_path, '-i', temp_audio,
            '-map', '0:v:0', '-map', '1:a:0',
            '-map_metadata', '-1', '-map_chapters', '-1',
            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
            '-shortest', '-avoid_negative_ts', 'make_zero',
            '-disposition:a:0', 'default',
            '-metadata:s:a:0', 'language=rus', '-metadata:s:a:0', 'title=Russian Dub',
            output_path
        ]
        res2 = run_cmd(fallback_cmd, timeout=900)
        if res2.returncode != 0:
            # Last-resort compatibility path: remux through Matroska with generated timestamps and no metadata.
            fallback2_cmd = [
                ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-fflags', '+genpts',
                '-i', raw_path, '-i', temp_audio,
                '-map', '0:v:0', '-map', '1:a:0',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k',
                '-shortest', '-dn', '-sn', '-map_metadata', '-1', '-map_chapters', '-1',
                output_path
            ]
            res3 = run_cmd(fallback2_cmd, timeout=900)
            if res3.returncode != 0:
                try:
                    Path(temp_audio).unlink(missing_ok=True)
                except Exception:
                    pass
                return {'ok': False, 'error': 'primary mux failed:\n' + first_err[-1800:] + '\n\nfallback mux failed:\n' + res2.stderr[-1800:] + '\n\nlast resort mux failed:\n' + res3.stderr[-1800:], 'voice_note': voice_note, 'sync_note': sync_note, 'sync_analysis': sync_analysis}

    try:
        Path(temp_audio).unlink(missing_ok=True)
    except Exception:
        pass
    return {'ok': Path(output_path).exists(), 'output': output_path, 'size_mb': round(Path(output_path).stat().st_size / 1048576, 2) if Path(output_path).exists() else 0, 'voice_note': voice_note, 'sync_note': sync_note, 'sync_analysis': sync_analysis}


def make_test_clip(raw_path, dub_path, cfg, out_path, offset=0.0, dub_track=0, start=60, duration=20):
    ffmpeg = cfg.get('ffmpeg_path') or 'ffmpeg'
    test_dir = Path(resolve_path(cfg.get('test_folder') or './test', cfg))
    test_dir.mkdir(parents=True, exist_ok=True)
    temp_wav = test_dir / '_temp_clip.wav'
    temp_aac = test_dir / '_temp_clip.aac'
    cmd = [ffmpeg, '-y', '-ss', str(start), '-i', dub_path, '-t', str(duration + abs(offset) + 2), '-map', f'0:a:{dub_track}', '-vn', '-ac', '2', '-ar', '48000', '-acodec', 'pcm_s16le', str(temp_wav)]
    res = run_cmd(cmd, timeout=60)
    if res.returncode != 0:
        return {'ok': False, 'error': res.stderr[-1200:]}
    filters = []
    if offset > 0:
        ms = int(offset * 1000)
        filters.append(f'adelay={ms}|{ms}')
    elif offset < 0:
        filters += [f'atrim=start={abs(offset):.3f}', 'asetpts=PTS-STARTPTS']
    cmd = [ffmpeg, '-y', '-i', str(temp_wav)]
    if filters:
        cmd += ['-af', ','.join(filters)]
    cmd += ['-c:a', 'aac', '-b:a', '192k', '-t', str(duration), str(temp_aac)]
    res = run_cmd(cmd, timeout=60)
    try: temp_wav.unlink(missing_ok=True)
    except Exception: pass
    if res.returncode != 0:
        return {'ok': False, 'error': res.stderr[-1200:]}
    cmd = [ffmpeg, '-y', '-ss', str(start), '-i', raw_path, '-i', str(temp_aac), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'copy', '-t', str(duration), str(out_path)]
    res = run_cmd(cmd, timeout=80)
    try: temp_aac.unlink(missing_ok=True)
    except Exception: pass
    return {'ok': res.returncode == 0 and Path(out_path).exists(), 'output': str(out_path), 'error': res.stderr[-1200:] if res.returncode != 0 else ''}


def scan_project(cfg):
    raw_folder = resolve_path(cfg.get('raw_folder') or './raw', cfg)
    dub_folder = resolve_path(cfg.get('dub_folder') or './dub', cfg)
    remux_ts_files(dub_folder, cfg)
    raw = find_videos(raw_folder)
    dub = find_videos(dub_folder)

    invalid = []
    for group, label in ((raw, 'raw'), (dub, 'dub')):
        for f in group:
            ok, reason = validate_video_file(f.get('path'), cfg)
            f['valid'] = ok
            f['invalid_reason'] = reason
            if not ok:
                invalid.append({'folder': label, 'name': f.get('name'), 'path': f.get('path'), 'reason': reason})

    return {'raw': raw, 'dub': dub, 'matched': match_files(raw, dub), 'invalid': invalid}


def pretty_episode_name(season, episode):
    return f'S{int(season):02d}E{int(episode):02d}.mkv'


def organize_output(output_path, title, season=1, episode=1, library_root=None):
    src = Path(output_path)
    if not src.exists():
        return {'ok': False, 'error': 'output file missing'}
    clean_title = re.sub(r'[\\/*?:"<>|]', '', str(title or 'Unknown')).strip() or 'Unknown'
    root = Path(library_root or Path.home() / 'Videos' / 'MinimalMediaPlayer')
    target_dir = root / clean_title / f'Season {int(season):02d}'
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / pretty_episode_name(season, episode)
    if src.resolve() != target.resolve():
        shutil.copy2(src, target)
    return {'ok': True, 'path': str(target), 'name': target.name}
