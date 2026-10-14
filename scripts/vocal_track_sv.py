#!/usr/bin/env python3
"""vocal_track_sv.py - 生成 Synthesizer V 人声参考包。

CLI:
  python scripts/vocal_track_sv.py stems/vocals.wav --out vocal/
  python scripts/vocal_track_sv.py stems/vocals.wav --midi midi_raw/vocals_melody.mid

输出目录：
  vocal/vocal_melody.mid
  vocal/lyrics_placeholder.txt
  vocal/sv_recommendation.md

本脚本不识别、不生成歌词；只给音高轮廓、节奏格子和声库类型建议。
"""

import argparse
import sys
from pathlib import Path


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _midi_name(pitch):
    octave = int(pitch // 12) - 1
    return f"{NOTE_NAMES[pitch % 12]}{octave}"


def _read_midi_notes(path):
    try:
        import pretty_midi
    except ImportError:
        print("请先安装: pip install pretty_midi", file=sys.stderr)
        sys.exit(1)
    pm = pretty_midi.PrettyMIDI(str(path))
    return [{"pitch": int(n.pitch), "start": float(n.start), "end": float(n.end),
             "velocity": int(n.velocity)}
            for inst in pm.instruments for n in inst.notes]


def _estimate_notes(audio):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from transcribe_stems import estimate_vocal_pitch
    except ImportError:
        print("缺少 transcribe_stems.py 或音频依赖", file=sys.stderr)
        sys.exit(1)
    return estimate_vocal_pitch(str(audio))


def _write_midi(path, notes):
    try:
        import pretty_midi
    except ImportError:
        print("请先安装: pip install pretty_midi", file=sys.stderr)
        sys.exit(1)
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0, is_drum=False)
    for n in notes:
        end = max(float(n["end"]), float(n["start"]) + 0.01)
        inst.notes.append(pretty_midi.Note(
            velocity=int(n.get("velocity", 80)),
            pitch=int(n["pitch"]),
            start=float(n["start"]),
            end=end))
    pm.instruments.append(inst)
    pm.write(str(path))


def _phrase_notes(notes, gap=0.40):
    phrases = []
    cur = []
    prev_end = None
    for n in sorted(notes, key=lambda x: x["start"]):
        if prev_end is not None and n["start"] - prev_end > gap:
            phrases.append(cur)
            cur = []
        cur.append(n)
        prev_end = max(prev_end or 0.0, n["end"])
    if cur:
        phrases.append(cur)
    return phrases


def _lyrics_placeholder(notes):
    if not notes:
        return ["# 歌词占位", "", "未检测到足够的人声音高事件，本文件留空。", ""]
    lines = ["# 歌词占位", "",
             "# 每个 [歌词] 对应一个音符音节；请替换成实际歌词，音节数应大致匹配音符数。", ""]
    return _lyrics_placeholder_gap(notes, 0.40)


def _lyrics_placeholder_gap(notes, gap):
    if not notes:
        return ["# 歌词占位", "", "未检测到足够的人声音高事件，本文件留空。", ""]
    lines = ["# 歌词占位", "",
             "# 每个 [歌词] 对应一个音符音节；请替换成实际歌词，音节数应大致匹配音符数。", ""]
    phrases = _phrase_notes(notes, gap)
    for i, phrase in enumerate(phrases, start=1):
        start = phrase[0]["start"]
        end = phrase[-1]["end"]
        lines.append(f"[乐句 {i}] {int(start // 60)}:{int(start % 60):02d} - "
                     f"{int(end // 60)}:{int(end % 60):02d}")
        cols = []
        for n in phrase:
            cols.append("[歌词]")
            if len(cols) >= 6:
                lines.append(" ".join(cols))
                cols = []
        if cols:
            lines.append(" ".join(cols))
        lines.append("")
    return lines


def _recommendation(notes, style, virtual_singer=False):
    if not notes:
        return ["# SV 声库推荐", "", "未检测到人声音高事件，无法推荐声库。", ""]
    pitches = [n["pitch"] for n in notes]
    lo, hi = min(pitches), max(pitches)
    if style == "jp" or (style == "auto" and hi <= 67):
        name = "日系女声（清澈）"
    elif style == "en":
        name = "英系/韩系女声"
    elif style == "cn":
        name = "中系女声（甜美）"
    else:
        name = "日系/中系女声（清澈/甜美）"
    if virtual_singer:
        name = f"{name} / 虚拟歌姬声库"
    usage = "适合" if hi <= 64 else "需要较强共鸣"
    return [
        "# SV 声库推荐",
        "",
        f"- 人声参考线音域：{_midi_name(lo)} - {_midi_name(hi)}",
        f"- 推荐声库类型（只给类型，不绑定商品）：{name}",
        f"- 备注：{usage}；若原唱偏低/偏高，请按实际音域选择男/女声库。",
        (f"- 特化模式：虚拟歌姬。声库按合成/虚拟歌姬质感选型，"
         "人声参考线只锚定节奏与音高，滑音在 SV 中手动画 Pitch 曲线。"
         if virtual_singer else ""),
        "",
        "## 导入流程",
        "1. 在 Synthesizer V 新建工程，选择匹配类型的 AI 声库。",
        "2. 导入 vocal/vocal_melody.mid 作为参考唱线。",
        "3. 把 lyrics_placeholder.txt 的 [歌词] 占位替换为实际歌词音节。",
        "4. 对齐节奏后渲染 WAV，回到 FL Studio 作为音频轨。",
        "",
    ]


def main():
    ap = argparse.ArgumentParser(description="SV 人声参考包")
    ap.add_argument("vocals_wav", nargs="?", default=None, help="人声 stem WAV")
    ap.add_argument("--midi", default=None, help="可选现成 vocals_melody.mid")
    ap.add_argument("--out", default="vocal")
    ap.add_argument("--style", default="auto", choices=["auto", "jp", "cn", "en"])
    ap.add_argument("--virtual-singer", action="store_true",
                    help="虚拟歌姬歌曲特化：乐句切分更紧，声库推荐按合成人声处理")
    args = ap.parse_args()

    audio = Path(args.vocals_wav) if args.vocals_wav else None
    if audio and not audio.exists():
        print(f"人声音频不存在: {audio}", file=sys.stderr)
        sys.exit(1)
    if args.midi and not Path(args.midi).exists():
        print(f"MIDI 不存在: {args.midi}", file=sys.stderr)
        sys.exit(1)
    if not audio and not args.midi:
        print("需要提供 vocals_wav 或 --midi", file=sys.stderr)
        sys.exit(1)

    if args.midi:
        notes = _read_midi_notes(Path(args.midi))
    else:
        notes = _estimate_notes(audio)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_midi(out / "vocal_melody.mid", notes)
    if args.virtual_singer:
        lyrics_lines = _lyrics_placeholder_gap(notes, 0.20)
    else:
        lyrics_lines = _lyrics_placeholder(notes)
    (out / "lyrics_placeholder.txt").write_text(
        "\n".join(lyrics_lines), encoding="utf-8")
    (out / "sv_recommendation.md").write_text(
        "\n".join(_recommendation(notes, args.style, virtual_singer=args.virtual_singer)),
        encoding="utf-8")
    mode = "virtual-singer" if args.virtual_singer else "default"
    print(f"[vocal_track_sv] 人声参考包输出: {out}（{mode}，{len(notes)} 个音高事件）")


if __name__ == "__main__":
    main()
