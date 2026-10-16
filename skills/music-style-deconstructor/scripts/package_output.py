#!/usr/bin/env python3
"""package_output.py - 合并多轨 MIDI 并生成 FL Studio 导入说明。

CLI:
  python scripts/package_output.py midi/ vocal/vocal_melody.mid \
      --map INSTRUMENT_MAP.md --out output/ --name mysong

可选：
  --features features.json  # 从中读取 BPM 写入 MIDI 头部
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()


TRACK_SPECS = [
    ("melody", "melody.mid", "Melody Lead", 0, False, 0),
    ("pad", "pad.mid", "Chords / Pad", 1, False, 1),
    ("bass", "bass.mid", "Bass", 2, False, 2),
    ("vocal", "vocals_melody.mid", "Vocal (ref)", 4, False, 3),
    ("drums", "drums.mid", "Drums", 9, True, 9),
]


def _read_notes(midi_path):
    try:
        import pretty_midi
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py（最佳）或 pip install pretty_midi", file=sys.stderr)
        sys.exit(1)
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    return [n for inst in pm.instruments for n in inst.notes]


def _load_bpm(features_path, bpm_override):
    if bpm_override:
        return float(bpm_override)
    if features_path and Path(features_path).exists():
        with open(features_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("bpm"):
            return float(data["bpm"])
    return 120.0


def main():
    ap = argparse.ArgumentParser(description="合并多轨 MIDI + FL Studio 导入说明")
    ap.add_argument("midi_dir")
    ap.add_argument("vocal_midi", nargs="?", default=None,
                    help="vocal/vocal_melody.mid")
    ap.add_argument("--map", default="INSTRUMENT_MAP.md")
    ap.add_argument("--out", default="output")
    ap.add_argument("--name", default="mysong")
    ap.add_argument("--features", default=None)
    ap.add_argument("--bpm", default=None, type=float)
    args = ap.parse_args()

    midi_dir = Path(args.midi_dir)
    if not midi_dir.exists():
        print(f"分轨目录不存在: {midi_dir}", file=sys.stderr)
        sys.exit(1)
    try:
        import pretty_midi
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py（最佳）或 pip install pretty_midi", file=sys.stderr)
        sys.exit(1)

    bpm = _load_bpm(args.features, args.bpm)
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    used = []
    temp_instruments = []
    for label, filename, display_name, channel, is_drum, program in TRACK_SPECS:
        if label == "vocal" and args.vocal_midi and Path(args.vocal_midi).exists():
            path = Path(args.vocal_midi)
        else:
            path = midi_dir / filename
        if not path.exists():
            continue
        notes = _read_notes(path)
        inst = pretty_midi.Instrument(program=program, is_drum=is_drum, name=display_name)
        for n in notes:
            end = max(float(n.end), float(n.start) + 0.01)
            inst.notes.append(pretty_midi.Note(
                velocity=int(n.velocity), pitch=int(n.pitch),
                start=float(n.start), end=end))
        inst.channel = channel
        temp_instruments.append(inst)
        used.append((label, display_name, channel, len(inst.notes)))
    pm.instruments.extend(temp_instruments)

    if not used:
        print("没有可合并的 MIDI 轨", file=sys.stderr)
        sys.exit(1)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    midi_out = out / f"{args.name}_multitrack.mid"
    pm.write(str(midi_out))

    lines = [f"# FL Studio 导入：{args.name}", "",
             f"- BPM：{bpm:.2f}", "",
             "| 轨 | MIDI 通道 | 通道号(1-based) | 乐器类型参考 |",
             "|---|---|---|---|"]
    for label, display_name, channel, count in used:
        one_based = channel + 1 if channel < 9 else 10
        lines.append(f"| {display_name} | {channel} | {one_based} | 见 INSTRUMENT_MAP.md |")
    lines += ["",
              "1. 把 `<song>_multitrack.mid` 拖入 FL Studio。",
              "2. 每轨按 INSTRUMENT_MAP.md 选择乐器插件。",
              "3. 鼓轨使用 GM 鼓键映射，通道 10 会被 FL Studio 识别为打击乐轨。",
              "4. 人声参考轨导入 Synthesizer V 后，FL Studio 中的 MIDI 参考轨可静音。", ""]
    readme = out / "README_导入FLStudio.md"
    readme.write_text("\n".join(lines), encoding="utf-8")

    map_path = Path(args.map)
    if map_path.exists():
        shutil.copy2(str(map_path), str(out / "INSTRUMENT_MAP.md"))
    style_report = Path("STYLE_REPORT.md")
    if style_report.exists():
        shutil.copy2(str(style_report), str(out / "STYLE_REPORT.md"))
    notes_json = midi_dir / "notes.json"
    if notes_json.exists():
        shutil.copy2(str(notes_json), str(out / "notes.json"))
    for extra in ("SECTION_SUMMARY.md", "SECTION_SUMMARY.json", "AUDIO_NARRATIVE.md"):
        p = Path(extra)
        if p.exists():
            shutil.copy2(str(p), str(out / p.name))
    vocal_src = Path("vocal")
    if vocal_src.exists():
        shutil.copytree(str(vocal_src), str(out / "vocal"), dirs_exist_ok=True)

    print(f"[package_output] 多轨 MIDI: {midi_out}")
    print(f"[package_output] 导入说明: {readme}")


if __name__ == "__main__":
    main()
