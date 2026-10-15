#!/usr/bin/env python3
"""notes_json.py - 从现有 MIDI 目录生成 notes.json。

CLI:
  python scripts/notes_json.py midi/ --out notes.json

如果目录里已经有包含 confidence 的 notes.json，优先从它读置信度；
否则按力度/Drum 规则估计一个 0.5-0.95 的参考值。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()
from notes_io import write_notes_json  # noqa: E402


def _confidence_by_velocity(velocity, is_drum):
    if is_drum:
        return min(1.0, 0.4 + velocity / 200.0)
    return max(0.5, min(0.95, 0.5 + velocity / 127.0 * 0.45))


def _load_existing_notes(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, TypeError):
        return {}


def _flatten_existing(existing):
    values = {}
    for track in existing.get("tracks", []):
        for note in track.get("notes", []):
            key = (track.get("track"), round(note["start"], 3), round(note["end"], 3),
                   note["pitch"])
            values[key] = note.get("confidence")
    return values


def main():
    ap = argparse.ArgumentParser(description="从 MIDI 目录生成 notes.json")
    ap.add_argument("midi_dir")
    ap.add_argument("--out", default="notes.json")
    args = ap.parse_args()

    midi_dir = Path(args.midi_dir)
    if not midi_dir.exists():
        print(f"目录不存在: {midi_dir}", file=sys.stderr)
        sys.exit(1)
    try:
        import pretty_midi
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py", file=sys.stderr)
        sys.exit(1)

    existing = _load_existing_notes(midi_dir / "notes.json")
    meta = _flatten_existing(existing)
    entries = []
    for p in sorted(midi_dir.rglob("*.mid")):
        pm = pretty_midi.PrettyMIDI(str(p))
        notes = []
        is_drum = any(inst.is_drum for inst in pm.instruments)
        for inst in pm.instruments:
            for n in inst.notes:
                key = (p.stem, round(n.start, 3), round(n.end, 3), int(n.pitch))
                conf = meta.get(key) or _confidence_by_velocity(int(n.velocity), inst.is_drum)
                notes.append({
                    "start": float(n.start),
                    "end": float(n.end),
                    "pitch": int(n.pitch),
                    "velocity": int(n.velocity),
                    "confidence": round(float(conf), 3),
                })
        entries.append({"track": p.stem, "file": p.name,
                        "channel": 9 if is_drum else 0,
                        "program": inst.program,
                        "is_drum": is_drum, "notes": notes})

    out = Path(args.out)
    write_notes_json(out, entries, source=str(midi_dir))
    print(f"[notes_json] 输出: {out}（{len(entries)} 轨）")


if __name__ == "__main__":
    main()
