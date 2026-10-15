#!/usr/bin/env python3
"""perceptual_filter.py - 符号域旋律/伴奏分层与音符清洗。

这个文件被 transcribe_stems.py 和 split_arrangement.py 复用。
纯 Python 实现，不依赖 numpy / librosa，方便符号域快速处理。
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Dict, List


def _ensure_notes(notes):
    """复制输入并补全必要字段，避免修改调用方数据。"""
    out = []
    for n in notes:
        nn = dict(n)
        nn["start"] = float(nn.get("start", 0.0))
        nn["end"] = float(nn.get("end", nn["start"] + 0.1))
        nn["pitch"] = int(nn.get("pitch", 0))
        nn["velocity"] = int(nn.get("velocity", 80))
        if nn["end"] <= nn["start"]:
            nn["end"] = nn["start"] + 0.1
        out.append(nn)
    return out


def merge_notes(notes, gap=0.05):
    """按音高合并相邻/重叠音符。"""
    notes = _ensure_notes(notes)
    by_pitch = defaultdict(list)
    for n in notes:
        if n["pitch"] > 0:
            by_pitch[n["pitch"]].append(n)

    merged = []
    for pitch, lst in by_pitch.items():
        lst.sort(key=lambda n: (n["start"], n["end"]))
        cur = dict(lst[0])
        for n in lst[1:]:
            if n["start"] - cur["end"] <= gap:
                cur["end"] = max(cur["end"], n["end"])
                cur["velocity"] = max(cur["velocity"], n["velocity"])
            else:
                merged.append(cur)
                cur = dict(n)
        merged.append(cur)
    merged.sort(key=lambda n: n["start"])
    return merged


def clean_notes(notes, min_duration=0.04, merge_gap=0.06, outlier_semitones=10):
    """清洗音符：去碎音、合并、去明显离群音。"""
    notes = _ensure_notes(notes)
    notes = [n for n in notes if n["pitch"] > 0 and n["end"] - n["start"] >= min_duration]
    if not notes:
        return []

    seen = set()
    deduped = []
    for n in notes:
        key = (round(n["start"], 3), n["pitch"])
        if key not in seen:
            seen.add(key)
            deduped.append(n)
    notes = deduped
    notes.sort(key=lambda n: n["start"])

    med = median([n["pitch"] for n in notes])
    filtered = [n for n in notes if abs(n["pitch"] - med) <= outlier_semitones * 12]
    if filtered:
        notes = filtered
    return merge_notes(notes, gap=merge_gap)


def _overlap(a, b):
    s = max(a["start"], b["start"])
    e = min(a["end"], b["end"])
    return e > s


def separate_arrangement_layers(notes, melody_low=48, pad_low=36,
                                overlap_threshold=1):
    """把符号域音符粗略分成 melody / pad / bass 三层。"""
    notes = clean_notes(notes)
    if not notes:
        return {"melody": [], "pad": [], "bass": []}

    overlap_count = {i: 0 for i in range(len(notes))}
    for i in range(len(notes)):
        for j in range(len(notes)):
            if i == j:
                continue
            if _overlap(notes[i], notes[j]):
                overlap_count[i] += 1

    melody = []
    pad = []
    bass = []
    for i, n in enumerate(notes):
        if n["pitch"] < pad_low:
            bass.append(n)
        elif n["pitch"] < melody_low:
            pad.append(n)
        elif overlap_count[i] <= max(1, overlap_threshold):
            melody.append(n)
        else:
            pad.append(n)

    if not melody and pad:
        candidates = sorted([n for n in pad if n["pitch"] >= melody_low],
                            key=lambda n: -n["velocity"])
        chosen = []
        window_start = None
        for n in candidates:
            if window_start is None or n["start"] - window_start >= 4.0:
                chosen.append(id(n))
                window_start = n["start"]
        if chosen:
            chosen_ids = set(chosen)
            melody = [n for n in pad if id(n) in chosen_ids]
            pad = [n for n in pad if id(n) not in chosen_ids]

    return {
        "melody": merge_notes(melody, gap=0.04),
        "pad": merge_notes(pad, gap=0.06),
        "bass": merge_notes(bass, gap=0.04),
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if sys.argv[1:] == ["--help"] else 1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)
    melody_low = int(sys.argv[2]) if len(sys.argv) > 2 else 48
    result = separate_arrangement_layers(data, melody_low=melody_low)
    print(json.dumps(result, ensure_ascii=False, indent=2))
