#!/usr/bin/env python3
"""section_summary.py - 输出每段落和弦/鼓型/织体摘要，并生成音频叙事。

CLI:
  python scripts/section_summary.py features.json --midi midi/
  python scripts/section_summary.py features.json --midi midi_raw/ --out SECTION_SUMMARY.md

输出：
  SECTION_SUMMARY.md
  SECTION_SUMMARY.json
  AUDIO_NARRATIVE.md
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()


def _fmt(t):
    m = int(t // 60)
    s = int(t % 60)
    return f"{m}:{s:02d}"


def _load_json(path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_midi_notes(midi_dirs):
    if not midi_dirs:
        return {}
    tracks = {}
    for midi_dir in midi_dirs:
        if not midi_dir.exists():
            continue
        notes_json = midi_dir / "notes.json"
        if notes_json.exists():
            data = _load_json(notes_json)
            for tr in data.get("tracks", []):
                tracks[tr["track"]] = tr.get("notes", [])
            continue
        try:
            import pretty_midi
        except ImportError:
            return tracks
        for p in sorted(midi_dir.rglob("*.mid")):
            pm = pretty_midi.PrettyMIDI(str(p))
            notes = [{"start": n.start, "end": n.end, "pitch": n.pitch,
                      "velocity": n.velocity}
                     for inst in pm.instruments for n in inst.notes]
            tracks[p.stem] = notes
    return tracks


def _chords_for_section(sections, chord_times, chord_seq):
    """取落在段落时间窗内/跨界的和弦标签。"""
    if not chord_times or not chord_seq:
        return []
    result = []
    for i, t in enumerate(chord_times):
        if i + 1 < len(chord_times):
            if t < sections[1] - 1e-6 and chord_times[i + 1] > sections[0]:
                result.append(chord_seq[i])
        elif t < sections[1] - 1e-6:
            result.append(chord_seq[i])
    return list(dict.fromkeys(result))


def _drum_pattern(notes, start=None, end=None):
    if not notes:
        return {"text": "无鼓", "counts": {}}
    counts = {"kick": 0, "snare": 0, "hat": 0, "cymbal": 0, "tom": 0}
    total = 0
    for n in notes:
        if start is not None and end is not None:
            if n["start"] >= end or n["end"] <= start:
                continue
        total += 1
        p = int(n.get("pitch", 0))
        if p in (35, 36):
            counts["kick"] += 1
        elif p in (38, 39, 40):
            counts["snare"] += 1
        elif p in (42, 44, 46):
            counts["hat"] += 1
        elif p in (49, 51, 52, 55, 57, 59):
            counts["cymbal"] += 1
        elif 41 <= p <= 48:
            counts["tom"] += 1
    parts = []
    if counts["kick"]:
        parts.append(f"kick {counts['kick']}")
    if counts["snare"]:
        parts.append(f"snare {counts['snare']}")
    if counts["hat"]:
        parts.append(f"hat {counts['hat']}")
    if counts["cymbal"]:
        parts.append(f"cymbal {counts['cymbal']}")
    text = " + ".join(parts) if parts else "无鼓"
    if total and start is not None and end is not None:
        density = total / max(end - start, 1e-6)
        if total <= 0:
            text = "无鼓"
        elif density < 0.4:
            text = f"稀疏鼓点（{text}，密度 {density:.2f}/s）"
        elif density < 2.0:
            text = f"鼓点进入（{text}，密度 {density:.2f}/s）"
        elif density > 8.0:
            text = f"鼓点密集（{text}，密度 {density:.2f}/s）"
    return {"text": text, "counts": counts}


def _texture_for_section(section, tracks, stem_spectral):
    bits = []
    start, end = section["start"], section["end"]
    for name in ("vocals_melody", "vocals", "melody", "other", "pad", "bass"):
        notes = tracks.get(name)
        if not notes:
            continue
        count = sum(1 for n in notes if n["start"] < end and n["end"] > start)
        duration = max(end - start, 1e-6)
        density = count / duration
        label = {"vocals_melody": "人声", "vocals": "人声", "melody": "主旋律",
                 "other": "other", "pad": "pad", "bass": "bass"}.get(name, name)
        if density > 1.5:
            bits.append(f"{label}密集")
        elif density > 0.2:
            bits.append(f"{label}进入")
        else:
            bits.append(f"{label}少")
    return bits


def _summary_sections(features, tracks):
    sections = features.get("sections", [])
    chord_times = features.get("chord_times", [])
    chords = features.get("chord_sequence", [])
    stem_spectral = features.get("stem_spectral", {})
    sections_out = []
    for s in sections:
        start, end = s.get("start", 0), s.get("end", 0.0)
        sec_chords = _chords_for_section((start, end), chord_times, chords)
        drums = _drum_pattern(tracks.get("drums", []), start, end)
        texture = _texture_for_section({"start": start, "end": end}, tracks, stem_spectral)
        sections_out.append({
            "id": s.get("id"),
            "label": s.get("label"),
            "start": round(start, 2),
            "end": round(end, 2),
            "chords": sec_chords or ["未识别"],
            "drum_pattern": drums["text"],
            "drum_counts": drums["counts"],
            "texture": texture,
        })
    return sections_out


def _markdown(sections, features):
    lines = ["# 段落摘要", ""]
    lines += [f"- BPM: {features.get('bpm')}  Key: {features.get('key')} {features.get('scale')}", ""]
    lines += ["| 段落 | 时间 | 和弦 | 鼓型 | 织体 |", "|---|---|---|---|---|"]
    for s in sections:
        time = f"{_fmt(s['start'])}-{_fmt(s['end'])}"
        texture = "; ".join(s["texture"]) if s["texture"] else "无"
        lines.append(f"| {s['label']} | {time} | {', '.join(s['chords'])} | "
                     f"{s['drum_pattern']} | {texture} |")
    lines += ["", "## Stem 频谱摘要", "",
              "| Stem | spectral_centroid | spectral_bandwidth | roughness | onset_density | rms |",
              "|---|---|---|---|---|---|"]
    stem_spectral = features.get("stem_spectral", {})
    if stem_spectral:
        for name, vals in stem_spectral.items():
            lines.append(f"| {name} | {vals.get('spectral_centroid', '')} "
                         f"| {vals.get('spectral_bandwidth', '')} "
                         f"| {vals.get('roughness', '')} "
                         f"| {vals.get('onset_density', '')} "
                         f"| {vals.get('rms', '')} |")
    else:
        lines.append("| （未提供 stem_spectral，请确认已跑 extract_features 并保留 stems 目录） | | | | | |")
    lines += ["", "## Stem 音色摘要", "",
              "| Stem | 音色标签 | brightness | flatness | low_energy | tags |",
              "|---|---|---|---|---|"]
    stem_timbre = features.get("stem_timbre", {})
    if stem_timbre:
        for name, vals in stem_timbre.items():
            tags = ", ".join(vals.get("tags", []))
            lines.append(f"| {name} | {tags} | {vals.get('brightness', '')} "
                         f"| {vals.get('spectral_flatness', '')} "
                         f"| {vals.get('low_energy_ratio', '')} "
                         f"| {vals.get('spectral_centroid', '')} Hz |")
    else:
        lines.append("| （未提供 stem_timbre，请升级后重跑 extract_features） | | | | |")
    lines += [""]
    return lines


def _narrative(sections, features):
    lines = ["# 音频叙事", ""]
    if not sections:
        lines.append("- 暂无可分析段落。")
        return lines
    for s in sections[:5]:
        t = f"段落 {s['label']}（{_fmt(s['start'])}-{_fmt(s['end'])}）"
        parts = [t]
        if s["drum_pattern"] == "无鼓":
            parts.append("无鼓")
        else:
            parts.append(f"鼓组以 {s['drum_pattern']} 为主")
        if s["texture"]:
            parts.append("；".join(s["texture"]))
        if s["chords"]:
            parts.append(f"和弦 {', '.join(s['chords'][:3])}")
        lines.append(f"- {', '.join(parts)}。")
    if features.get("duration_sec", 0) > 0:
        lines.append("")
        timbre_tags = []
        timbre = features.get("timbre")
        if timbre and timbre.get("tags"):
            timbre_tags.append("音色：" + "、".join(timbre["tags"]))
        if features.get("virtual_singer"):
            timbre_tags.append("虚拟歌姬标记：是")
        extra = "，".join(timbre_tags)
        tail = f"，{extra}" if extra else ""
        lines.append(f"- 全曲 {features.get('duration_sec', 0)} 秒{tail}。")
    return lines


def main():
    ap = argparse.ArgumentParser(description="生成段落摘要和音频叙事")
    ap.add_argument("features_json")
    ap.add_argument("--midi", action="append", default=None,
                    help="midi 目录（可多次传入：midi_raw + midi）")
    ap.add_argument("--out", default="SECTION_SUMMARY.md")
    args = ap.parse_args()

    fp = Path(args.features_json)
    if not fp.exists():
        print(f"缺少 features.json: {fp}", file=sys.stderr)
        sys.exit(1)
    features = _load_json(fp)
    midi_dirs = [Path(p) for p in args.midi] if args.midi else []
    tracks = _load_midi_notes(midi_dirs)
    sections = _summary_sections(features, tracks)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    (out).write_text("\n".join(_markdown(sections, features)), encoding="utf-8")
    (out.with_suffix(".json")).write_text(
        json.dumps({"sections": sections,
                    "stem_spectral": features.get("stem_spectral", {}),
                    "stem_timbre": features.get("stem_timbre", {}),
                    "timbre": features.get("timbre", {})},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    narrative_path = out.parent / "AUDIO_NARRATIVE.md"
    narrative_path.write_text("\n".join(_narrative(sections, features)), encoding="utf-8")
    print(f"[section_summary] 输出: {out}, {out.with_suffix('.json')}, {narrative_path}")


if __name__ == "__main__":
    main()
