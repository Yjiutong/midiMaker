#!/usr/bin/env python3
"""style_report.py - 生成基于数值特征的风格拆析报告。

CLI:
  python scripts/style_report.py features.json --out STYLE_REPORT.md
  python scripts/style_report.py features.json --fingerprint AUTHOR_FINGERPRINT.json

如果提供了 --fingerprint，会在各维度追加“符合作者惯例 / 偏离”说明。
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()


def _fmt_sec(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def _section_label(sections):
    if not sections:
        return "未分段"
    parts = []
    for s in sections:
        parts.append(f"{s.get('label', '?')} {_fmt_sec(s['start'])}-{_fmt_sec(s['end'])}"
                     f"({s.get('duration', 0.0):.1f}s)")
    return " → ".join(parts)


def _ngrams(seq, n):
    return [tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)]


def _top_progressions(chords, top=5):
    counter = Counter()
    for n in range(2, 5):
        for gram in _ngrams(chords, n):
            counter[gram] += 1
    items = counter.most_common(top)
    return ["-".join(g) for g, _ in items]


def _drum_stats(drums_path):
    if not drums_path:
        return None
    try:
        import pretty_midi
    except ImportError:
        return None
    if not drums_path.exists():
        return None
    pm = pretty_midi.PrettyMIDI(str(drums_path))
    notes = [n for inst in pm.instruments for n in inst.notes]
    if not notes:
        return {"note_count": 0, "density": 0.0}
    end = max(n.end for n in notes)
    return {"note_count": len(notes), "density": round(len(notes) / max(end, 1e-6), 2)}


def _fingerprint_compare(fp, features):
    lines = []
    if not fp:
        return lines
    fp_key = fp.get("key") or {}
    if fp_key.get("common_keys"):
        if features.get("key") not in fp_key["common_keys"]:
            lines.append(f"- 调性偏离：本曲 {features.get('key')}，"
                         f"作者常用 {', '.join(fp_key['common_keys'])}")
    fp_bpm = fp.get("bpm") or {}
    rng = fp_bpm.get("range") or fp_bpm.get("p5_p95")
    if rng and not (rng[0] <= features.get("bpm", 0) <= rng[1]):
        lines.append(f"- BPM 偏离：本曲 {features.get('bpm')}，作者惯用 {rng[0]}-{rng[1]}")
    fp_bright = fp.get("brightness") or {}
    bright_rng = fp_bright.get("range")
    if bright_rng:
        sc = features.get("spectral_centroid", 0)
        if not (bright_rng[0] <= sc <= bright_rng[1]):
            lines.append(f"- 音色亮度偏离：本曲 centroid {sc}，作者惯用区间 {bright_rng}")
    fp_groove = fp.get("groove_density") or {}
    grove_rng = fp_groove.get("range")
    if grove_rng:
        od = features.get("onset_density", 0)
        if not (grove_rng[0] <= od <= grove_rng[1]):
            lines.append(f"- 节奏密度偏离：本曲 onset_density {od}，"
                         f"作者惯用区间 {grove_rng}")
    return lines or ["- 各维度均落在作者指纹常见区间，判为符合作者惯例。"]


def main():
    ap = argparse.ArgumentParser(description="生成风格拆析数值报告")
    ap.add_argument("features_json")
    ap.add_argument("--out", default="STYLE_REPORT.md")
    ap.add_argument("--drums", default=None, help="可选 drums.mid")
    ap.add_argument("--fingerprint", default=None, help="可选 AUTHOR_FINGERPRINT.json")
    ap.add_argument("--virtual-singer", action="store_true",
                    help="虚拟歌姬歌曲特化：增加合成人声特征分析小节")
    args = ap.parse_args()

    features_path = Path(args.features_json)
    if not features_path.exists():
        print(f"缺少 features.json: {features_path}", file=sys.stderr)
        sys.exit(1)
    with open(features_path, "r", encoding="utf-8") as f:
        features = json.load(f)

    fp = {}
    if args.fingerprint and Path(args.fingerprint).exists():
        with open(args.fingerprint, "r", encoding="utf-8") as f:
            fp = json.load(f)

    chords = features.get("chord_sequence", [])
    prog = _top_progressions(chords)
    sections = features.get("sections", [])
    stem_energy = features.get("stem_energy", {})
    drum = _drum_stats(Path(args.drums) if args.drums else None)
    compare = _fingerprint_compare(fp, features)

    lines = ["# 风格拆析报告", ""]
    lines += ["> 本报告由 style_report.py 基于 features.json 自动生成，供编曲参考。", ""]
    lines += [f"- 时长：{features.get('duration_sec', 0)}s",
              f"- BPM：{features.get('bpm', '?')}",
              f"- 调性：{features.get('key', '?')} · {features.get('scale', '?')}",
              f"- 频谱质心（brightness）：{features.get('spectral_centroid', '?')}",
              f"- RMS：{features.get('rms', '?')}",
              f"- Onset 密度：{features.get('onset_density', '?')} / s", ""]

    lines += ["## 一、曲式结构", ""]
    lines += [_section_label(sections), ""]
    counts = {}
    for s in sections:
        counts[s.get("label", "?")] = counts.get(s.get("label", "?"), 0) + s.get("duration", 0)
    if counts:
        lines += ["段落时长占比：", ""]
        lines += [f"- {k}: {v:.1f}s" for k, v in counts.items() if v > 0]
        lines += [""]

    lines += ["## 二、调性与和声", ""]
    lines += [f"- 主调：{features.get('key', '?')}  {features.get('scale', '?')}",
              f"- 和弦片段 Top 进行：{', '.join(prog) if prog else '无'}",
              f"- 色彩/转调：暂按特征自动标注；如需人工确认请结合和弦序列。", ""]

    lines += ["## 三、节奏律动", ""]
    lines += [f"- 最近拍点数量：{len(features.get('beats', []))}",
              f"- 起音帧数：{features.get('onset_frames', 0)}",
              f"- Onset 密度：{features.get('onset_density', 0)} / s"]
    if drum:
        lines += [f"- 鼓轨：{drum['note_count']} 个鼓点，密度 {drum['density']} / s"]
    lines += [""]

    lines += ["## 四、配器层次", ""]
    if stem_energy:
        for name in ("vocals", "drums", "bass", "other"):
            if name in stem_energy:
                lines += [f"- {name} stem RMS 能量：{stem_energy[name]}"]
    else:
        lines += ["- 未提供 stem_energy，跳过配器能量对比。"]
    lines += [""]

    lines += ["## 五、音色取向", ""]
    timbre = features.get("timbre")
    if timbre:
        tags = ", ".join(timbre.get("tags", []))
        lines += [f"- 音色标签：{tags}",
                  f"- MFCC 亮度：{timbre.get('brightness', '?')}",
                  f"- 频谱平坦度：{timbre.get('spectral_flatness', '?')}",
                  f"- 低频能量占比：{timbre.get('low_energy_ratio', '?')}"]
    stem_timbre = features.get("stem_timbre", {})
    if stem_timbre:
        lines += ["- 分轨音色：", ""]
        for name, vals in stem_timbre.items():
            tags = ", ".join(vals.get("tags", []))
            lines += [f"  - {name}: {tags}（centroid {vals.get('spectral_centroid', '?')} Hz，" +
                      f"flatness {vals.get('spectral_flatness', '?')}）"]
    lines += [f"- 频谱质心：{features.get('spectral_centroid', '?')}",
              f"- 频谱带宽：{features.get('spectral_bandwidth', '?')}",
              "- 说明：数字越大通常越亮；失真/饱和程度需结合音频主观听感。", ""]

    lines += ["## 六、动态与混音", ""]
    lines += [f"- RMS：{features.get('rms', '?')}",
              "- 说明：需对比段落 RMS 与各 stem 能量判断人声/鼓是否突出。", ""]

    if args.virtual_singer or features.get("virtual_singer"):
        lines += ["## 七、虚拟歌姬特化", ""]
        lines += ["- 该曲按虚拟歌姬歌曲处理：合成人声通常干净、音高稳定、音节密度高。",
                  f"- syllabic_density：{features.get('syllabic_density', '未提供')}",
                  f"- formant_stability：{features.get('formant_stability', '未提供')}",
                  "- 人声 MIDI 仅锚定节奏与音高；滑音/转音在 Synthesizer V 中手动处理。", ""]

    if args.fingerprint and fp:
        lines += ["## 与作者指纹对比", ""]
        lines += compare + [""]

    lines += ["## 编曲要点总结", ""]
    lines += ["- 先核对主调与和弦进行的判断是否与听感一致。",
              "- 自动转录只作为参考，最终编曲仍以耳朵为准。", ""]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[style_report] 输出: {out}")


if __name__ == "__main__":
    main()
