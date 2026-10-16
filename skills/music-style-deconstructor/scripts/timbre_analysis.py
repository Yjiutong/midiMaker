#!/usr/bin/env python3
"""timbre_analysis.py - 基于 features.json 生成音色分析报告。

CLI:
  python scripts/timbre_analysis.py features.json --out TIMBRE_REPORT.md

读取 extract_features.py 已写入的 timbre / stem_timbre，输出：
  TIMBRE_REPORT.md
  TIMBRE_REPORT.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()


def _fmt_tags(tags):
    return "、".join(tags or ["中性"])


def _report_rows(stem_timbre):
    rows = []
    labels = {
        "vocals": "人声",
        "drums": "鼓组",
        "bass": "贝斯",
        "other": "其他/和声层",
    }
    if not stem_timbre:
        return rows
    for name, vals in stem_timbre.items():
        rows.append({
            "stem": name,
            "label": labels.get(name, name),
            "tags": vals.get("tags", []),
            "brightness": vals.get("brightness"),
            "spectral_centroid": vals.get("spectral_centroid"),
            "spectral_bandwidth": vals.get("spectral_bandwidth"),
            "spectral_flatness": vals.get("spectral_flatness"),
            "spectral_rolloff": vals.get("spectral_rolloff"),
            "zero_crossing_rate": vals.get("zero_crossing_rate"),
            "low_energy_ratio": vals.get("low_energy_ratio"),
            "mfcc_mean": vals.get("mfcc_mean"),
            "mfcc_std": vals.get("mfcc_std"),
        })
    return rows


def _markdown(features):
    timbre = features.get("timbre", {})
    stem_timbre = features.get("stem_timbre", {})
    lines = ["# 音色分析报告", ""]
    if not timbre:
        lines += ["- features.json 中没有 timbre 字段，请先运行更新后的 extract_features.py。", ""]
        return lines
    lines += [f"- 全曲音色标签：{_fmt_tags(timbre.get('tags'))}", ""]
    lines += ["## 全曲音色特征", "",
              "| 维度 | 数值 |", "|---|---|"]
    for key, label in [
        ("brightness", "亮度"),
        ("spectral_centroid", "频谱质心"),
        ("spectral_bandwidth", "频谱带宽"),
        ("spectral_flatness", "频谱平坦度"),
        ("spectral_rolloff", "能量滚降点"),
        ("zero_crossing_rate", "过零率"),
        ("low_energy_ratio", "低频能量占比"),
    ]:
        lines.append(f"| {label} | {timbre.get(key, '')} |")
    lines += ["", "## 分轨音色摘要", "",
              "| Stem | 音色 | 亮度 | 频谱质心 | 平坦度 | 低频占比 | 过零率 |",
              "|---|---|---|---|---|---|---|"]
    rows = _report_rows(stem_timbre)
    if not rows:
        lines.append("| （未提供 stem_timbre） | | | | | | |")
    for r in rows:
        lines.append(f"| {r['label']} | {_fmt_tags(r['tags'])} "
                     f"| {r['brightness']} | {r['spectral_centroid']} "
                     f"| {r['spectral_flatness']} | {r['low_energy_ratio']} "
                     f"| {r['zero_crossing_rate']} |")
    lines += ["", "## 说明", "",
              "- 音色标签是规则化描述，最终可结合听感人工修正。",
              "- MFCC 向量和频谱对比值已写入 TIMBRE_REPORT.json，供模型或下游任务使用。", ""]
    return lines


def main():
    ap = argparse.ArgumentParser(description="生成音色分析报告")
    ap.add_argument("features_json")
    ap.add_argument("--out", default="TIMBRE_REPORT.md")
    args = ap.parse_args()

    fp = Path(args.features_json)
    if not fp.exists():
        print(f"缺少 features.json: {fp}", file=sys.stderr)
        sys.exit(1)
    with open(fp, "r", encoding="utf-8") as f:
        features = json.load(f)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    out.write_text("\n".join(_markdown(features)), encoding="utf-8")
    json_out = out.with_suffix(".json")
    json_out.write_text(json.dumps({
        "timbre": features.get("timbre", {}),
        "stems": _report_rows(features.get("stem_timbre", {})),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[timbre_analysis] 输出: {out}, {json_out}")


if __name__ == "__main__":
    main()
