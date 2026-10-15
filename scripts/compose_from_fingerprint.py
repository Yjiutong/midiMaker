#!/usr/bin/env python3
"""compose_from_fingerprint.py - 基于作者风格指纹生成分轨原创 MIDI。

该脚本不读取音频，而是根据已分析的作者风格指纹（key/BPM/和弦进行/层次/段落比例）
生成可导入 FL Studio 的多轨 MIDI，适合用作者参考曲的风格写一首新的编曲草稿。

CLI:
  python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
      --out midi_gen --name style_demo --bars 32 --seed 42

可选：
  --features features.json  补充/覆盖 key、bpm、chord_sequence
  --bpm 125 --key A --scale minor 手动覆盖
  --prompt "更明亮、鼓更密" 自然语言微调（agent 可直接使用）
  --params params.json       结构化覆盖参数
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()
from notes_io import write_notes_json  # noqa: E402


PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_TO_NATURAL = {
    "db": "C#",
    "eb": "D#",
    "gb": "F#",
    "ab": "G#",
    "bb": "A#",
}
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]
ROMAN_DEGREES = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7,
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
}


def _fmt(t):
    m = int(t // 60)
    s = int(t % 60)
    return f"{m}:{s:02d}"


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _pc(name):
    raw = str(name or "").strip()
    if raw.startswith("b"):
        raw = FLAT_TO_NATURAL.get(raw.lower(), raw[1:])
    raw = raw.replace("♯", "#").replace("♭", "b")
    if raw in PITCH_CLASSES:
        return PITCH_CLASSES.index(raw)
    return 0


def _pc_name(pc):
    return PITCH_CLASSES[pc % 12]


def _key_parts(key, scale):
    key_pc = _pc(key) if key else 0
    mode = "minor" if (scale or "").lower().startswith("min") else "major"
    return key_pc, mode


def _quality_intervals(body):
    body = (body or "").lower()
    if "dim" in body or body in ("o", "°"):
        return (0, 3, 6)
    if "aug" in body or body in ("+",):
        return (0, 4, 8)
    if "sus" in body:
        return (0, 5, 7)
    if "min" in body or "m7" in body or body.endswith("m") or body.startswith("m"):
        return (0, 3, 7)
    return (0, 4, 7)


def _roman_degree_root(label, mode):
    m = re.match(r"^([b#]?)([IViv]+)", label)
    if not m:
        return None
    accidental, roman = m.groups()
    degree = ROMAN_DEGREES.get(roman)
    if degree is None:
        return None
    scale = MAJOR_SCALE if mode == "major" else MINOR_SCALE
    root = scale[(degree - 1) % 7]
    if accidental:
        root += -1 if accidental == "b" else 1
    return root % 12, roman


def _chord_pcs(label, key_pc, mode):
    """Return pitch classes for a chord label (C:maj / Am / vi / I / D:sus4 style)."""
    if not label:
        return tuple((key_pc + d) % 12 for d in (0, 4, 7))
    label = str(label).strip()

    if ":" in label:
        root_label, body = label.split(":", 1)
        root_pc = _pc(root_label) if root_label else key_pc
        return tuple((root_pc + d) % 12 for d in _quality_intervals(body))

    roman = _roman_degree_root(label, mode)
    if roman:
        root_pc, roman_label = roman
        if label.endswith("°") or label.endswith("o"):
            intervals = (0, 3, 6)
        elif roman_label.isupper():
            intervals = _quality_intervals("maj")
        else:
            intervals = _quality_intervals("min")
        return tuple((root_pc + d) % 12 for d in intervals)

    # 纯字母和弦，例如 C、Am、C7、Gmaj7。只解析根音和最基础的品质后缀。
    body = label[1:].lower()
    root_pc = _pc(label[:1])
    return tuple((root_pc + d) % 12 for d in _quality_intervals(body))


def _fallback_progression(key_pc, mode):
    if mode == "minor":
        labels = [
            f"{_pc_name(key_pc + MINOR_SCALE[0])}:min",
            f"{_pc_name(key_pc + MINOR_SCALE[5])}:maj",
            f"{_pc_name(key_pc + MINOR_SCALE[4])}:maj",
            f"{_pc_name(key_pc + MINOR_SCALE[6])}:maj",
        ]
        return labels
    labels = [
        f"{_pc_name(key_pc + MAJOR_SCALE[0])}:maj",
        f"{_pc_name(key_pc + MAJOR_SCALE[4])}:maj",
        f"{_pc_name(key_pc + MAJOR_SCALE[5])}:min",
        f"{_pc_name(key_pc + MAJOR_SCALE[3])}:maj",
    ]
    return labels


def _chord_sequence(style):
    progressions = _as_list(style.get("progressions_top") or style.get("chord_sequence") or [])
    for prog in progressions:
        if isinstance(prog, str) and ("->" in prog or "-" in prog):
            sep = "->" if "->" in prog else "-"
            seq = [s.strip() for s in prog.split(sep) if s.strip()]
        else:
            seq = [str(s).strip() for s in _as_list(prog) if str(s).strip()]
        if seq:
            return seq
    key_pc, mode = _key_parts(style.get("key"), style.get("scale"))
    return _fallback_progression(key_pc, mode)


def _section_plan(total_bars, style, rng):
    ratio = style.get("section_ratio") or {}
    if ratio and sum(ratio.values()) > 0:
        keys = [k for k, v in ratio.items() if v > 0]
        weights = [max(float(ratio[k]), 0.05) for k in keys]
    else:
        keys = ["Intro", "Verse", "Chorus", "Bridge", "Outro"]
        weights = [0.10, 0.30, 0.32, 0.18, 0.10]
    total_w = sum(weights)
    plan = []
    remaining = total_bars
    for i, label in enumerate(keys):
        if remaining <= 0:
            break
        if i == len(keys) - 1:
            bars = remaining
        else:
            bars = max(0, int(round(total_bars * weights[i] / total_w)))
        bars = max(1, min(remaining, bars))
        plan.append({"label": str(label), "bars": bars})
        remaining -= bars
    if remaining > 0 and plan:
        plan[-1]["bars"] += remaining
    if not plan or total_bars <= 0:
        plan = [{"label": "Song", "bars": max(1, total_bars)}]
    return plan


def _scale_pcs(key_pc, mode):
    return sorted((key_pc + d) % 12 for d in (MAJOR_SCALE if mode == "major" else MINOR_SCALE))


def _is_sparse_section(label):
    lower = str(label).lower()
    return lower in ("intro", "outro", "a", "d", "e") or lower.startswith(("intro:", "outro:"))


def _generate_melody(plan, progression, key_pc, mode, beats_per_bar, rng,
                     brightness=0.5, melody_density=None):
    notes = []
    scale_pcs = _scale_pcs(key_pc, mode)
    t = 0.0
    last_pitch = None
    total_bars = sum(s["bars"] for s in plan)
    section_start_bars = {}
    bar_cursor = 0
    for s in plan:
        section_start_bars[bar_cursor] = s
        bar_cursor += s["bars"]

    for bar in range(total_bars):
        section = plan[-1]
        for start_bar, s in section_start_bars.items():
            if bar >= start_bar:
                section = s
            else:
                break
        cidx = bar % len(progression)
        chord_pcs = _chord_pcs(progression[cidx], key_pc, mode)
        base_octave = 5 if (section["label"] in ("chorus", "Chorus", "B", "C")
                            or brightness >= 0.65) else 4
        density = melody_density if melody_density is not None else (
            0.38 if _is_sparse_section(section["label"]) else 0.68
        )
        if brightness >= 0.8:
            density = min(1.0, density + 0.08)
            base_octave = min(6, base_octave + 1)
        for step in range(16):
            if rng.random() > density:
                continue
            if rng.random() < 0.62 and last_pitch is not None:
                pitch = last_pitch + rng.choice([-2, -1, 1, 2])
            else:
                pool = list(chord_pcs) + scale_pcs
                pitch = base_octave * 12 + rng.choice(pool)
                if brightness >= 0.8 and rng.random() < 0.25:
                    pitch += 12
            pitch = max(45, min(84, int(pitch)))
            step_sec = step / 4.0
            dur = 0.25 if step % 2 == 0 else 0.125
            start = t + step_sec
            end = start + dur
            notes.append({
                "start": round(start, 4),
                "end": round(end, 4),
                "pitch": pitch,
                "velocity": rng.randint(70, 92),
                "confidence": 0.92,
            })
            last_pitch = pitch
        t += beats_per_bar
    return notes


def _generate_pad(plan, progression, key_pc, mode, beats_per_bar, rng,
                  pad_density=1.0):
    notes = []
    t = 0.0
    bar = 0
    for s in plan:
        for _ in range(s["bars"]):
            if rng.random() > pad_density:
                bar += 1
                t += beats_per_bar
                continue
            cidx = bar % len(progression)
            chord_pcs = _chord_pcs(progression[cidx], key_pc, mode)
            for pc in chord_pcs:
                velocity = (rng.randint(58, 72) if pad_density >= 0.9 else rng.randint(50, 66)) \
                    if not _is_sparse_section(s["label"]) else rng.randint(40, 54)
                for base_pc in (48, 55):
                    notes.append({
                        "start": round(t, 4),
                        "end": round(t + beats_per_bar * 0.95, 4),
                        "pitch": base_pc + pc,
                        "velocity": velocity,
                        "confidence": 0.88,
                    })
            bar += 1
            t += beats_per_bar
    return notes


def _generate_bass(plan, progression, key_pc, mode, beats_per_bar, rng, density,
                   bass_density=None):
    notes = []
    t = 0.0
    bar = 0
    for s in plan:
        sparse = _is_sparse_section(s["label"])
        rhythm = [0, 2] if not sparse else ([0] if rng.random() < 0.7 else [0, 2])
        eff_density = density if bass_density is None else bass_density
        for _ in range(s["bars"]):
            cidx = bar % len(progression)
            chord_pcs = _chord_pcs(progression[cidx], key_pc, mode)
            root_pc = min(chord_pcs) % 12
            for beat in rhythm:
                if rng.random() > eff_density:
                    continue
                start = t + beat
                notes.append({
                    "start": round(start, 4),
                    "end": round(start + 0.35, 4),
                    "pitch": 36 + root_pc,
                    "velocity": 82 if not sparse else 64,
                    "confidence": 0.86,
                })
            bar += 1
            t += beats_per_bar
    return notes


def _generate_drums(plan, beats_per_bar, rng, density):
    notes = []
    t = 0.0
    for s in plan:
        sparse = _is_sparse_section(s["label"])
        if sparse:
            if rng.random() < 0.7:
                notes.append({
                    "start": round(t, 4),
                    "end": round(t + 0.1, 4),
                    "pitch": 42,
                    "velocity": 60,
                    "confidence": 0.8,
                })
        else:
            for step in range(16):
                beat = step / 4.0
                if step % 4 == 0:
                    notes.append({
                        "start": round(t + beat, 4),
                        "end": round(t + beat + 0.12, 4),
                        "pitch": 36,
                        "velocity": 95,
                        "confidence": 0.95,
                    })
                if step % 4 == 2:
                    notes.append({
                        "start": round(t + beat, 4),
                        "end": round(t + beat + 0.12, 4),
                        "pitch": 38,
                        "velocity": 100,
                        "confidence": 0.95,
                    })
                if rng.random() < 0.8 * density:
                    notes.append({
                        "start": round(t + beat, 4),
                        "end": round(t + beat + 0.08, 4),
                        "pitch": 42,
                        "velocity": 72,
                        "confidence": 0.8,
                    })
        t += beats_per_bar
    return notes


def _write_midi(notes, path, program=0, is_drum=False, bpm=120.0, channel=None):
    try:
        import pretty_midi
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py", file=sys.stderr)
        sys.exit(1)
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for n in notes:
        start = float(n["start"])
        end = max(float(n.get("end", start + 0.25)), start + 0.01)
        inst.notes.append(pretty_midi.Note(
            velocity=int(n["velocity"]), pitch=int(n["pitch"]),
            start=start, end=end))
    if channel is not None:
        inst.channel = channel
    pm.instruments.append(inst)
    path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(path))


def _features_style(features):
    style = {}
    if features.get("key"):
        style["key"] = features["key"]
    if features.get("scale"):
        style["scale"] = features["scale"]
    if features.get("bpm"):
        style["bpm"] = features["bpm"]
    if features.get("chord_sequence"):
        style["progressions_top"] = [features["chord_sequence"][:8]]
    if features.get("onset_density"):
        style["groove_density"] = {"mean": float(features["onset_density"])}
    sections = _as_list(features.get("sections"))
    if sections:
        duration_by_label = {}
        total = 0.0
        for s in sections:
            d = float(s.get("duration", 0.0))
            label = str(s.get("label", "Section"))
            duration_by_label[label] = duration_by_label.get(label, 0.0) + d
            total += d
        if total > 0:
            style["section_ratio"] = {
                k: round(v / total, 4) for k, v in duration_by_label.items() if v > 0
            }
    return style


def _pick_list(vals, default=None):
    vals = [v for v in _as_list(vals) if v is not None and str(v)]
    return vals[0] if vals else default


def _apply_prompt_params(prompt, params):
    """把自然语言风格提示词翻译成可计算的风格参数，供 agent 直接使用。

    agent 也可以跳过 `--prompt`，自己把用户提示词解析成 `--params` JSON 传入。
    """
    if not prompt:
        return dict(params)
    text = prompt.lower()
    out = dict(params)

    if any(k in text for k in ("快", "赶", "紧凑", "活跃", "动感", "fast", "upbeat", "energetic", "dance")):
        out["bpm_shift"] = out.get("bpm_shift", 0) + 6
        out["density"] = max(0.0, min(1.0, out.get("density", 0.78) + 0.10))
    if any(k in text for k in ("慢", "舒缓", "安静", "抒情", "slow", "chill", "ballad", "calm", "ambient")):
        out["bpm_shift"] = out.get("bpm_shift", 0) - 8
        out["density"] = max(0.0, min(1.0, out.get("density", 0.78) - 0.15))
    if any(k in text for k in ("亮", "明亮", "清亮", "通透", "bright", "sparkling", "pop")):
        out["brightness"] = max(out.get("brightness", 0.5), 0.8)
    if any(k in text for k in ("暗", "暗沉", "低沉", "深邃", "dark", "darker", "r&b", "rnb")):
        out["brightness"] = min(out.get("brightness", 0.5), 0.35)
    if any(k in text for k in ("鼓密", "鼓多", "强鼓", "重鼓", "drum-heavy", "more drums", "hits hard")):
        out["density"] = max(out.get("density", 0.8), 0.9)
    if any(k in text for k in ("少鼓", "无鼓", "不要鼓", "轻鼓", "less drums", "no drums", "drums off")):
        out["drums"] = False
    if any(k in text for k in ("少钢琴", "少pad", "少和弦", "less pad", "less chords", "pad off")):
        out["pad_density"] = min(float(out.get("pad_density", 1.0)), 0.55)
    elif any(k in text for k in ("多pad", "多钢琴", "多和弦", "more pad", "more chords", "pad dense")):
        out["pad_density"] = 1.0
    return out


def main():
    ap = argparse.ArgumentParser(description="基于作者风格指纹生成分轨原创 MIDI")
    ap.add_argument("fingerprint", nargs="?", default=None,
                    help="AUTHOR_FINGERPRINT.json")
    ap.add_argument("--features", default=None, help="可选 features.json")
    ap.add_argument("--prompt", default=None, help="自然语言风格提示词，例如：更明亮、鼓更密、慢一点")
    ap.add_argument("--params", default=None, help="可选 params.json，支持 bpm/bars/key/scale/density/brightness 等")
    ap.add_argument("--out", default="midi_gen", help="输出目录")
    ap.add_argument("--name", default="style_demo")
    ap.add_argument("--bars", type=int, default=32)
    ap.add_argument("--bpm", type=float, default=None)
    ap.add_argument("--key", default=None)
    ap.add_argument("--scale", default=None)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if not args.fingerprint and not args.features:
        print("请提供 AUTHOR_FINGERPRINT.json 或 --features features.json", file=sys.stderr)
        sys.exit(1)

    params = {}
    if args.params:
        params_path = Path(args.params)
        if not params_path.exists():
            print(f"params.json 不存在: {params_path}", file=sys.stderr)
            sys.exit(1)
        with open(params_path, "r", encoding="utf-8") as f:
            params.update({k: v for k, v in json.load(f).items() if v is not None})
    params = _apply_prompt_params(args.prompt, params)

    style = {}
    if args.features:
        fpath = Path(args.features)
        if not fpath.exists():
            print(f"features.json 不存在: {fpath}", file=sys.stderr)
            sys.exit(1)
        with open(fpath, "r", encoding="utf-8") as f:
            style.update(_features_style(json.load(f)))

    if args.fingerprint:
        fp_path = Path(args.fingerprint)
        if not fp_path.exists():
            print(f"指纹不存在: {fp_path}", file=sys.stderr)
            sys.exit(1)
        with open(fp_path, "r", encoding="utf-8") as f:
            fp = json.load(f)
        fp_key = fp.get("key") or {}
        style["progressions_top"] = fp.get("progressions_top") or style.get("progressions_top")
        style["section_ratio"] = fp.get("section_ratio") or style.get("section_ratio")
        style["layers"] = fp.get("layers") or style.get("layers")
        style["bpm"] = (fp.get("bpm") or {}).get("mean") or style.get("bpm")
        style["groove_density"] = fp.get("groove_density") or style.get("groove_density")
        key = _pick_list(fp_key.get("common_keys"), style.get("key")) or "C"
        scale = _pick_list(fp_key.get("mode"), style.get("scale")) or "major"
        style["key"] = key
        style["scale"] = scale

    if params.get("progression"):
        style["progressions_top"] = [params["progression"]]
    if params.get("section_ratio"):
        style["section_ratio"] = params["section_ratio"]

    bars = int(params.get("bars", args.bars))
    key = params.get("key") or args.key or style.get("key") or "C"
    scale = params.get("scale") or args.scale or style.get("scale") or "major"
    bpm = params.get("bpm") or args.bpm or style.get("bpm") or 120.0
    bpm += float(params.get("bpm_shift", 0))
    bpm = max(60.0, min(210.0, float(bpm)))
    key_pc, mode = _key_parts(key, scale)
    rng = random.Random(int(params.get("seed", args.seed)))
    progression = _chord_sequence(style)
    plan = _section_plan(bars, style, rng)
    beats_per_bar = 4.0
    total_sec = bars * beats_per_bar * 60.0 / bpm

    layers = style.get("layers") or {}
    drum_density = float((style.get("groove_density") or {}).get("mean", 0.8))
    drum_density = float(params.get("density", drum_density))
    use_drums = bool(params.get("drums", True)) and (
        not layers or float(layers.get("drums", {}).get("frequency", 1.0)) >= 0.25
    )
    drums = _generate_drums(plan, beats_per_bar, rng, drum_density) if use_drums else []

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    brightness = float(params.get("brightness", 0.5))
    melody = _generate_melody(
        plan, progression, key_pc, mode, beats_per_bar, rng,
        brightness=brightness,
        melody_density=params.get("melody_density"))
    pad = _generate_pad(
        plan, progression, key_pc, mode, beats_per_bar, rng,
        pad_density=float(params.get("pad_density", 1.0)))
    bass = _generate_bass(
        plan, progression, key_pc, mode, beats_per_bar, rng,
        drum_density, bass_density=params.get("bass_density"))

    _write_midi(melody, out / "melody.mid", program=0, bpm=bpm, channel=0)
    _write_midi(pad, out / "pad.mid", program=1, bpm=bpm, channel=1)
    _write_midi(bass, out / "bass.mid", program=33, bpm=bpm, channel=2)
    if drums:
        _write_midi(drums, out / "drums.mid", program=0, is_drum=True, bpm=bpm, channel=9)

    entries = [
        {"track": "melody", "file": "melody.mid", "channel": 0, "program": 0, "notes": melody},
        {"track": "pad", "file": "pad.mid", "channel": 1, "program": 1, "notes": pad},
        {"track": "bass", "file": "bass.mid", "channel": 2, "program": 33, "notes": bass},
    ]
    if drums:
        entries.append({
            "track": "drums",
            "file": "drums.mid",
            "channel": 9,
            "program": 0,
            "is_drum": True,
            "notes": drums,
        })
    write_notes_json(out / "notes.json", entries,
                     source=str(args.fingerprint or args.features))

    section_text = " → ".join(f"{s['label']}({s['bars']}bar)" for s in plan)
    report_lines = [
        "# 风格化 MIDI 生成报告", "",
        f"- 名称：{args.name}",
        f"- 调性：{key} {scale}",
        f"- BPM：{bpm}",
        f"- 小节：{bars}（预计 {int(total_sec)} 秒）",
        f"- 和弦进行：{' → '.join(progression)}",
        f"- 段落：{section_text}",
        f"- 分轨：melody / pad / bass" + (" / drums" if drums else ""),
        f"- 提示词：{args.prompt or '无'}",
        "",
        "该 MIDI 由作者风格指纹规则生成，不是音频转录；适合作为编曲草稿再人工完善。",
        "",
    ]
    (out / "COMPOSE_REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    print(f"[compose_from_fingerprint] 输出: {out}")


if __name__ == "__main__":
    main()
