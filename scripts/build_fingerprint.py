#!/usr/bin/env python3
"""build_fingerprint.py - 多首 features.json 聚合成作者风格指纹。

CLI:
  python scripts/build_fingerprint.py f1.json f2.json f3.json --out AUTHOR_FINGERPRINT.json

输出 JSON 结构见 references/fingerprint_framework.md。
"""

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _bounds(values):
    vals = sorted(float(v) for v in values)
    if len(vals) == 1:
        return [vals[0], vals[0]]
    lo = vals[max(0, int(round(len(vals) * 0.05)))]
    hi = vals[min(len(vals) - 1, int(round(len(vals) * 0.95)))]
    return [round(lo, 2), round(hi, 2)]


def _top_keys(values, top=3):
    count = Counter(values)
    return [item for item, _ in count.most_common(top)]


def _top_progressions(all_chords, top=5):
    counter = Counter()
    for chords in all_chords:
        for n in range(2, 5):
            for i in range(len(chords) - n + 1):
                counter[tuple(chords[i:i + n])] += 1
    return [list(g) for g, _ in counter.most_common(top)]


def _section_ratio(features):
    total = sum(s.get("duration", 0.0) for s in features.get("sections", []))
    if total <= 0:
        return {}
    ratio = defaultdict(float)
    for s in features.get("sections", []):
        ratio[s.get("label", "?")] += s.get("duration", 0.0) / total
    return dict(ratio)


def main():
    ap = argparse.ArgumentParser(description="聚合作者风格指纹")
    ap.add_argument("features", nargs="+", help="至少一个 features.json")
    ap.add_argument("--out", default="AUTHOR_FINGERPRINT.json")
    ap.add_argument("--author", default="未知作者")
    args = ap.parse_args()

    features_list = []
    for p in args.features:
        path = Path(p)
        if not path.exists():
            print(f"缺少 features.json: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            features_list.append(json.load(f))

    if not features_list:
        print("没有有效的 features.json", file=sys.stderr)
        sys.exit(1)

    keys = _top_keys([f.get("key") for f in features_list if f.get("key")])
    scales = _top_keys([f.get("scale") for f in features_list if f.get("scale")], top=1)
    bpms = [f["bpm"] for f in features_list if "bpm" in f]
    brightness = [f["spectral_centroid"] for f in features_list if "spectral_centroid" in f]
    densities = [f["onset_density"] for f in features_list if "onset_density" in f]
    all_chords = [f.get("chord_sequence", []) for f in features_list]

    layer_counter = defaultdict(set)
    for f in features_list:
        se = f.get("stem_energy", {})
        if se.get("vocals") is not None:
            layer_counter["vocal"].add("人声")
        if se.get("drums") is not None:
            layer_counter["drums"].add("鼓组")
        if se.get("bass") is not None:
            layer_counter["bass"].add("贝斯")
        if se.get("other") is not None:
            layer_counter["other"].add("其它织体")

    section_ratios = [_section_ratio(f) for f in features_list]
    merged_sections = {}
    for ratio in section_ratios:
        for k, v in ratio.items():
            merged_sections.setdefault(k, []).append(v)
    avg_sections = {k: round(sum(v) / len(v), 4) for k, v in merged_sections.items()}

    fingerprint = {
        "author": args.author,
        "num_reference_tracks": len(features_list),
        "key": {"mode": scales, "common_keys": keys},
        "progressions_top": _top_progressions(all_chords) if all_chords else [],
        "bpm": {},
        "layers": {k: {"frequency": round(len(v) / len(features_list), 2), "types": sorted(v)}
                   for k, v in layer_counter.items()},
        "section_ratio": avg_sections,
    }
    if bpms:
        fingerprint["bpm"] = {
            "mean": round(statistics.mean(bpms), 2),
            "std": round(statistics.stdev(bpms), 2) if len(bpms) > 1 else 0.0,
            "range": _bounds(bpms),
        }
    if brightness:
        fingerprint["brightness"] = {
            "mean": round(statistics.mean(brightness), 2),
            "range": _bounds(brightness),
        }
    if densities:
        fingerprint["groove_density"] = {
            "mean": round(statistics.mean(densities), 3),
            "range": _bounds(densities),
        }
    if len(features_list) < 3:
        fingerprint["warning"] = "参考曲 < 3 首，统计不稳定，指纹较宽泛。"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    with open(out, "w", encoding="utf-8") as f:
        json.dump(fingerprint, f, ensure_ascii=False, indent=2)
    print(f"[build_fingerprint] 输出: {out}（{len(features_list)} 首参考曲）")


if __name__ == "__main__":
    main()
