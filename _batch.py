#!/usr/bin/env python3
"""一次性批量跑 vocal_track_sv 提取人声参考线并汇总（非 skill 正式脚本）。"""
import subprocess, re, glob
from pathlib import Path

PY = r"C:/Users/19105/.workbuddy/binaries/python/versions/3.13.12/python.exe"
ROOT = Path(r"E:/midiMaker")
SKILL = ROOT / "skills" / "music-style-deconstructor"
VENV_SITE = SKILL / ".skill-deps" / "Lib" / "site-packages"

samples = sorted(glob.glob(str(ROOT / "samples" / "virtual_singer" / "*.wav")))
rows = []
for wav in samples:
    wav = Path(wav)
    stem = wav.stem
    out = ROOT / "results" / "vocal" / stem
    out.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            [PY, str(SKILL / "scripts/vocal_track_sv.py"), str(wav),
             "--out", str(out), "--virtual-singer"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300)
        msg = (r.stdout or r.stderr).strip().splitlines()
        print(f"[{stem}] " + (msg[-1] if msg else "no output"), flush=True)
        if r.returncode != 0:
            print(f"  (非零退出 {r.returncode})", flush=True)
    except Exception as e:
        print(f"[{stem}] 子进程异常: {e}", flush=True)
        rows.append((stem, 0, "?"))
        continue

    rec = (out / "sv_recommendation.md").read_text(encoding="utf-8", errors="ignore") \
        if (out / "sv_recommendation.md").exists() else ""
    m = re.search(r"人声参考线音域：(\S+)\s*-\s*(\S+)", rec)
    rng = f"{m.group(1)}-{m.group(2)}" if m else "?"

    notes = 0
    try:
        import sys
        sys.path.insert(0, str(VENV_SITE))
        import pretty_midi
        pm = pretty_midi.PrettyMIDI(str(out / "vocal_melody.mid"))
        notes = sum(len(i.notes) for i in pm.instruments)
    except Exception as e:
        print(f"  (note 计数跳过: {e})", flush=True)
    rows.append((stem, notes, rng))

summary = ROOT / "results" / "SUMMARY.md"
with open(summary, "w", encoding="utf-8") as f:
    f.write("# 人声参考线分析汇总（多轮训练 · 第 1 轮）\n\n")
    f.write(f"共处理 **{len(rows)}** 个人声样本（单音参考线 + 1 首整曲）。\n\n")
    f.write("每个样本的产物在 `results/vocal/<样本名>/`：\n")
    f.write("- `vocal_melody.mid`：人声参考唱线（音高轮廓）\n")
    f.write("- `lyrics_placeholder.txt`：按乐句切分的歌词占位\n\n")
    f.write("| 样本 | 音高事件数 | 检测音域 |\n|---|---|---|\n")
    for stem, n, rng in rows:
        f.write(f"| {stem} | {n} | {rng} |\n")
print(f"SUMMARY 写入 {summary}（{len(rows)} 行）")
