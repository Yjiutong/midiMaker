#!/usr/bin/env python3
"""instrument_map.py - 按 genre 给分轨 MIDI 标推荐乐器类型。

CLI:
  python scripts/instrument_map.py features.json midi/ --out INSTRUMENT_MAP.md
  python scripts/instrument_map.py features.json midi/ --out INSTRUMENT_MAP.md --genre pop

只输出乐器类型，不推荐具体 VST / 硬件型号。
"""

import argparse
import json
import sys
from pathlib import Path


GENRE_MAP = {
    "pop": {
        "melody": "合成主音 Lead",
        "pad": "暖色 Pad + 弦乐铺底",
        "bass": "电贝斯 / 合成贝斯",
        "drums": "原声鼓组（或轻度电子）",
        "vocal": "SV 声库（参考唱线）",
        "note": "连奏，叠加人声同度",
    },
    "rnb": {
        "melody": "电钢琴旋律 / 弦乐独奏",
        "pad": "暖色 Pad + 电钢琴",
        "bass": "滑音贝斯 / 电贝斯",
        "drums": "原声鼓组 + 大量 ghost note",
        "vocal": "SV 声库（R&B/气声）",
        "note": "留白和 ghost note 是重点",
    },
    "hiphop": {
        "melody": "方波 Lead / 合成主音",
        "pad": "电子 Pad",
        "bass": "808 合成贝斯（滑音）",
        "drums": "电子鼓(808) + 碎拍 hi-hat",
        "vocal": "SV 声库（说唱/中性）",
        "note": "鼓与贝斯驱动，律动优先",
    },
    "edm": {
        "melody": "合成主音 Lead / 方波",
        "pad": "电子 Pad / 合成铺底",
        "bass": "合成贝斯 / 八度贝斯",
        "drums": "电子鼓 / 工业鼓",
        "vocal": "SV 声库（力量型）",
        "note": "侧链感和层次推进重要",
    },
    "rock": {
        "melody": "电吉他（失真）/ 人声同度",
        "pad": "电吉他扫弦 / 风琴",
        "bass": "电贝斯 / 拨片贝斯",
        "drums": "原声鼓组（驱动）",
        "vocal": "SV 声库（力量型）",
        "note": "鼓与失真吉他形成冲击",
    },
    "singer_songwriter": {
        "melody": "人声（SV）+ 原声钢琴 叠奏",
        "pad": "原声吉他扫弦 / 暖色 Pad",
        "bass": "原声贝斯 / 电贝斯",
        "drums": "原声鼓组（克制）",
        "vocal": "SV 声库（抒情/民谣）",
        "note": "人声是第一层，配器留白",
    },
    "jazz": {
        "melody": "原声钢琴 / 萨克斯 / 小号",
        "pad": "原声钢琴 / 风琴",
        "bass": "原声贝斯（walking）",
        "drums": "爵士鼓（brush 感）",
        "vocal": "SV 声库（爵士/叙事）",
        "note": "和声色彩与即兴呼吸感优先",
    },
    "lofi": {
        "melody": "电钢琴 / 暖色 Pad",
        "pad": "暖色 Pad + 弦乐铺底（模糊）",
        "bass": "电贝斯",
        "drums": "采样碎拍（带噪声）",
        "vocal": "SV 声库（气声）",
        "note": "低通、噪声、慢速摇摆",
    },
    "jpop": {
        "melody": "合成主音 Lead / 原声钢琴",
        "pad": "弦乐铺底 + 电子 Pad",
        "bass": "电贝斯 / 合成贝斯",
        "drums": "原声鼓组 + 电子元素",
        "vocal": "SV 声库（日系清澈）",
        "note": "注重旋律与副歌冲击",
    },
    "cpop": {
        "melody": "合成主音 Lead / 原声钢琴",
        "pad": "暖色 Pad + 弦乐铺底",
        "bass": "电贝斯",
        "drums": "原声鼓组",
        "vocal": "SV 声库（中系甜美/气声）",
        "note": "人声中文咬字空间要留足",
    },
}

EMPTY = {"melody": "未检测", "pad": "未检测", "bass": "未检测",
         "drums": "未检测", "vocal": "未检测", "note": ""}


def _short_genre(name):
    aliases = {
        "R&B": "rnb", "R&B / Soul": "rnb", "Soul": "rnb",
        "Hip-Hop": "hiphop", "Trap": "hiphop",
        "EDM": "edm", "Electronic": "edm",
        "Singer-Songwriter": "singer_songwriter",
        "J-Pop": "jpop", "C-Pop": "cpop", "动漫": "jpop",
        "Lo-fi": "lofi", "Lo-Fi": "lofi",
    }
    return aliases.get(name, name.lower().replace("-", "_").replace(" ", "_"))


def main():
    ap = argparse.ArgumentParser(description="输出乐器类型标注")
    ap.add_argument("features_json")
    ap.add_argument("midi_dir")
    ap.add_argument("--out", default="INSTRUMENT_MAP.md")
    ap.add_argument("--genre", default="auto",
                    help="auto/pop/rnb/hiphop/edm/rock/singer_songwriter/jazz/lofi/jpop/cpop")
    args = ap.parse_args()

    features = {}
    if Path(args.features_json).exists():
        with open(args.features_json, "r", encoding="utf-8") as f:
            features = json.load(f)

    if args.genre and args.genre != "auto":
        genre = _short_genre(args.genre)
    else:
        genre = _short_genre(features.get("genre", "pop"))
    if genre not in GENRE_MAP:
        genre = "pop"
    rec = GENRE_MAP[genre]

    midi_dir = Path(args.midi_dir)
    present = {
        "melody": (midi_dir / "melody.mid").exists(),
        "pad": (midi_dir / "pad.mid").exists(),
        "bass": (midi_dir / "bass.mid").exists(),
        "drums": (midi_dir / "drums.mid").exists(),
        "vocal": (midi_dir / "vocals_melody.mid").exists(),
    }

    lines = ["# 乐器类型标注", "",
             f"> Genre 推断：`{genre}`。只给类型，不指定具体 VST / 硬件型号。", "",
             "| 轨 | MIDI 通道 | 乐器类型 | 推荐奏法 / 备注 |",
             "|---|---|---|---|"]
    rows = [
        ("主旋律", 1, "melody"),
        ("和声·Pad", 2, "pad"),
        ("贝斯", 3, "bass"),
        ("鼓组", 10, "drums"),
        ("人声(ref)", 5, "vocal"),
    ]
    for label, channel, key in rows:
        if present[key]:
            kind = rec[key]
            note = rec["note"] if key != "vocal" else "参考唱线，导入 SV 后对齐"
            lines.append(f"| {label} | {channel} | {kind} | {note} |")
    if not any(present.values()):
        lines.append("| （未检测到分轨 MIDI 文件） | — | — | 先运行 transcribe_stems / split_arrangement |")
    lines += ["",
              "## 备注",
              "- 若某些轨不是 Demucs 四轨完整分离，应删去不存在的轨。",
              f"- 作者指纹中的固定配器搭配可作为 `{genre}` 推荐的叠加依据。", ""]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[instrument_map] genre={genre} 输出: {out}")


if __name__ == "__main__":
    main()
