import re
import sys
from pathlib import Path

TIME_RE = re.compile(r'(\d{1,2}:\d{2}:\d{1,2},\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{1,2},\d{1,3})')

def parse_time(t: str) -> int:
    h, m, rest = t.split(':')
    s, ms = rest.split(',')
    ms = (ms + '000')[:3]
    return ((int(h) * 3600 + int(m) * 60 + int(s)) * 1000) + int(ms)

def fmt_time(total_ms: int) -> str:
    total_ms = max(0, int(round(total_ms)))
    h = total_ms // 3_600_000
    total_ms %= 3_600_000
    m = total_ms // 60_000
    total_ms %= 60_000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def shift_srt_text(text: str, offset_seconds: float) -> str:
    delta = int(round(offset_seconds * 1000))
    def repl(match):
        a = fmt_time(parse_time(match.group(1)) + delta)
        b = fmt_time(parse_time(match.group(2)) + delta)
        return f'{a} --> {b}'
    return TIME_RE.sub(repl, text)

def main():
    if len(sys.argv) < 4:
        print('Usage: python tools_shift_srt.py input.srt offset_seconds output.srt')
        print('Example: python tools_shift_srt.py mentalist.srt 8.22 mentalist_shifted.srt')
        raise SystemExit(2)
    inp = Path(sys.argv[1])
    offset = float(sys.argv[2].replace(',', '.'))
    out = Path(sys.argv[3])
    text = inp.read_text(encoding='utf-8-sig', errors='replace')
    out.write_text(shift_srt_text(text, offset), encoding='utf-8')
    print(f'Saved: {out} | offset: {offset:+.3f}s')

if __name__ == '__main__':
    main()
