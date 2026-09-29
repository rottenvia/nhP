#!/usr/bin/env python3
"""
Align an existing translated SRT to WhisperX JSON timings while preserving the translated text.

Best use case:
  1) Make a rough synced SRT first (global offset / rough timing).
  2) Run WhisperX on the video and get JSON with accurate English segments/words.
  3) This script snaps each translated subtitle line to nearby WhisperX speech segments.

It does NOT translate. It only retimes.

Example:
  python subtitle_whisperx_align.py ^
    --srt "The Mentalist - 1x01 - Pilot.HDTV.0TV.ru.synced.6.69.srt" ^
    --json "whisperx_out_medium_cuda\The Mentalist (2008) - S01E01 - Pilot [WEBDL-1080p][Opus 5.1][AV1]-Castiel.json" ^
    --out "The Mentalist - 1x01 - Pilot.ru.whisperx-aligned.srt"
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TIME_RE = re.compile(r"(\d{1,2}:\d{2}:\d{1,2},\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{1,2},\d{1,3})")


@dataclass
class Entry:
    num: str
    start: float
    end: float
    text: str
    raw: str = ""


@dataclass
class Segment:
    idx: int
    start: float
    end: float
    text: str


def parse_time(t: str) -> float:
    h, m, rest = t.strip().split(":")
    s, ms = rest.split(",")
    ms = (ms + "000")[:3]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def fmt_time(sec: float) -> str:
    ms_total = max(0, int(round(sec * 1000)))
    h = ms_total // 3_600_000
    ms_total %= 3_600_000
    m = ms_total // 60_000
    ms_total %= 60_000
    s = ms_total // 1000
    ms = ms_total % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def parse_srt(path: Path) -> list[Entry]:
    text = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    out: list[Entry] = []
    for block in blocks:
        lines = block.splitlines()
        if not lines:
            continue
        num = lines[0].strip()
        time_line_idx = None
        match = None
        for i, line in enumerate(lines[:3]):
            match = TIME_RE.search(line)
            if match:
                time_line_idx = i
                break
        if match is None or time_line_idx is None:
            continue
        body = "\n".join(lines[time_line_idx + 1:]).strip()
        out.append(Entry(num=num, start=parse_time(match.group(1)), end=parse_time(match.group(2)), text=body, raw=block))
    return out


def load_whisperx(path: Path) -> list[Segment]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    segs = []
    for i, s in enumerate(data.get("segments", [])):
        try:
            start = float(s.get("start"))
            end = float(s.get("end"))
        except Exception:
            continue
        text = str(s.get("text") or "").strip()
        if end <= start:
            continue
        # Ignore suspicious huge hallucination segments if any.
        if end - start > 30 and len(text) < 20:
            continue
        segs.append(Segment(i, start, end, text))
    segs.sort(key=lambda x: (x.start, x.end))
    return segs


def is_non_dialogue(entry: Entry) -> bool:
    t = entry.text.lower()
    needles = [
        "перевод", "специально", "tvsubtitles", "season01", "episode01", "www.", "http", "subtitle", "субтит",
    ]
    return any(n in t for n in needles)


def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def align_entries(entries: list[Entry], segs: list[Segment], window: float, pad: float, min_duration: float, max_expand: float):
    aligned: list[Entry] = []
    report = {"aligned": 0, "kept": 0, "non_dialogue_kept": 0, "low_confidence_kept": 0}
    cursor = 0

    for e in entries:
        if is_non_dialogue(e):
            aligned.append(e)
            report["non_dialogue_kept"] += 1
            continue

        e_mid = (e.start + e.end) / 2.0
        expanded_start = e.start - pad
        expanded_end = e.end + pad

        # Candidate speech segments near current subtitle timing. We keep this time-window based because
        # the Russian SRT should already be roughly offset-synced before this step.
        candidates = []
        for j in range(max(0, cursor - 3), len(segs)):
            sg = segs[j]
            if sg.start > e.end + window:
                break
            if sg.end < e.start - window:
                continue
            ov = overlap(expanded_start, expanded_end, sg.start, sg.end)
            dist = abs(((sg.start + sg.end) / 2.0) - e_mid)
            if ov > 0 or dist <= window:
                candidates.append((j, sg, ov, dist))

        if not candidates:
            aligned.append(e)
            report["kept"] += 1
            continue

        # Prefer actual overlap. If no overlap, nearest segment within window.
        candidates.sort(key=lambda x: (0 if x[2] > 0 else 1, -x[2], x[3]))
        best_j, best, best_ov, best_dist = candidates[0]

        # If nearest is too far, keep original to avoid snapping credits/noise to dialogue.
        if best_ov <= 0 and best_dist > max_expand:
            aligned.append(e)
            report["low_confidence_kept"] += 1
            continue

        # Include adjacent WhisperX segments that overlap the subtitle block. This handles translated lines
        # that correspond to several short English segments.
        chosen = [best]
        for j, sg, ov, dist in candidates:
            if sg is best:
                continue
            # Only merge close contiguous segments, not random dialogue around it.
            if ov > 0 and abs(j - best_j) <= 3:
                chosen.append(sg)
        chosen.sort(key=lambda x: x.start)

        new_start = min(sg.start for sg in chosen)
        new_end = max(sg.end for sg in chosen)
        if new_end - new_start < min_duration:
            center = (new_start + new_end) / 2
            new_start = max(0, center - min_duration / 2)
            new_end = center + min_duration / 2

        # Preserve monotonic order with previous subtitle.
        if aligned and new_start < aligned[-1].end + 0.03:
            shift = aligned[-1].end + 0.03 - new_start
            new_start += shift
            new_end += shift

        aligned.append(Entry(num=e.num, start=new_start, end=new_end, text=e.text, raw=e.raw))
        report["aligned"] += 1
        cursor = max(cursor, max(sg.idx for sg in chosen))

    return aligned, report


def write_srt(entries: list[Entry], path: Path) -> None:
    blocks = []
    for n, e in enumerate(entries, 1):
        num = e.num if str(e.num).strip().isdigit() else str(n)
        blocks.append(f"{num}\n{fmt_time(e.start)} --> {fmt_time(e.end)}\n{e.text}".rstrip())
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--srt", required=True, help="Rough-synced translated SRT")
    ap.add_argument("--json", required=True, help="WhisperX JSON")
    ap.add_argument("--out", required=True, help="Output aligned SRT")
    ap.add_argument("--window", type=float, default=8.0, help="Search window around current SRT line, seconds")
    ap.add_argument("--pad", type=float, default=0.45, help="Overlap padding around SRT line, seconds")
    ap.add_argument("--min-duration", type=float, default=0.65)
    ap.add_argument("--max-expand", type=float, default=5.0, help="Max distance for non-overlap snap")
    args = ap.parse_args()

    entries = parse_srt(Path(args.srt))
    segs = load_whisperx(Path(args.json))
    aligned, report = align_entries(entries, segs, args.window, args.pad, args.min_duration, args.max_expand)
    write_srt(aligned, Path(args.out))
    print(f"Loaded SRT entries: {len(entries)}")
    print(f"Loaded WhisperX segments: {len(segs)}")
    print(f"Saved: {args.out}")
    print("Report:", report)


if __name__ == "__main__":
    main()
