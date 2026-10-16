#!/usr/bin/env python3
"""split_arrangement.py - 把 other.mid 拆成主旋律 / 和声 Pad。

CLI:
  python scripts/split_arrangement.py midi_raw/other.mid --out midi/

输出：
  midi/melody.mid
  midi/pad.mid
  midi/bass.mid（若符号域分层产生低音音符）
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()
from notes_io import write_notes_json  # noqa: E402


def _read_midi_notes(path: Path):
    try:
        import pretty_midi
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py（最佳）或 pip install pretty_midi", file=sys.stderr)
        sys.exit(1)
    pm = pretty_midi.PrettyMIDI(str(path))
    notes = []
    for inst in pm.instruments:
        for n in inst.notes:
            notes.append({
                "pitch": int(n.pitch),
                "start": float(n.start),
                "end": float(n.end),
                "velocity": int(n.velocity),
                "confidence": 0.8,
            })
    return pm.resolution, notes


def _write_midi(out_path: Path, note_events, program=0, is_drum=False):
    try:
        import pretty_midi
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py（最佳）或 pip install pretty_midi", file=sys.stderr)
        sys.exit(1)
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for n in note_events:
        inst.notes.append(pretty_midi.Note(
            velocity=int(n.get("velocity", 80)),
            pitch=int(n["pitch"]),
            start=float(n["start"]),
            end=max(float(n["end"]), float(n["start"]) + 0.01)))
    pm.instruments.append(inst)
    pm.write(str(out_path))


def main():
    ap = argparse.ArgumentParser(description="other stem 拆主旋律/和声")
    ap.add_argument("other_midi")
    ap.add_argument("--out", default="midi", help="输出目录")
    ap.add_argument("--melody-low", type=int, default=48,
                    help="低于该音高视为和声/贝斯，默认 48")
    ap.add_argument("--pad-low", type=int, default=36,
                    help="低于该音高视为贝斯，默认 36")
    ap.add_argument("--overlap-threshold", type=int, default=1,
                    help="同时出现音符超过该数量则倾向作为和声，默认 1")
    args = ap.parse_args()

    other_path = Path(args.other_midi)
    if not other_path.exists():
        print(f"缺少 other MIDI: {other_path}", file=sys.stderr)
        sys.exit(1)

    from perceptual_filter import separate_arrangement_layers
    resolution, notes = _read_midi_notes(other_path)
    layers = separate_arrangement_layers(notes, melody_low=args.melody_low,
                                         pad_low=args.pad_low,
                                         overlap_threshold=args.overlap_threshold)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for layer_name, ext in (("melody", "melody"), ("pad", "pad"), ("bass", "bass")):
        events = layers[layer_name]
        counts[layer_name] = len(events)
        if events:
            _write_midi(out / f"{ext}.mid", events, program=0 if ext != "pad" else 1)
    entries = []
    for name, ch, prog in (("melody", 0, 0), ("pad", 1, 1), ("bass", 2, 2)):
        if layers[name]:
            entries.append({"track": name, "file": f"{name}.mid", "channel": ch,
                            "program": prog, "notes": layers[name]})
    if entries:
        write_notes_json(out / "notes.json", entries, source=str(other_path))
    with open(out / "arrangement_notes.json", "w", encoding="utf-8") as f:
        json.dump({"resolution": resolution, "layers": layers, "counts": counts},
                  f, ensure_ascii=False, indent=2)
    print(f"[split_arrangement] melody={counts['melody']} pad={counts['pad']} "
          f"bass={counts['bass']} 输出: {out}")


if __name__ == "__main__":
    main()
