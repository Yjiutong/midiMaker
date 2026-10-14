#!/usr/bin/env python3
"""separate_stems.py - 信号域人声/编曲分离。

优先调用 Demucs(htdemucs) 做 4-stem 分离；Demucs 不可用或失败时退回
librosa HPSS 的粗略分离（仅作为兜底，质感和精度明显低于 Demucs）。

CLI:
  python scripts/separate_stems.py input.mp3 --out stems/
  python scripts/separate_stems.py input.mp3 --two-stems vocals --out stems/
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def convert_to_wav(audio: Path, tmp: Path) -> Path:
    """非 wav 转 wav；wav 直接返回。"""
    if audio.suffix.lower() == ".wav":
        return audio
    try:
        import librosa
        import soundfile as sf
    except ImportError:
        print("[separate] 需要 librosa 和 soundfile 转码非 WAV 音频", file=sys.stderr)
        sys.exit(1)
    y, sr = librosa.load(str(audio), sr=44100, mono=False)
    wav_path = tmp / (audio.stem + ".wav")
    sf.write(str(wav_path), y.T, sr)
    return wav_path


def run_demucs(audio: Path, out: Path, two_stems: bool):
    cmd = [sys.executable, "-m", "demucs", "--out", str(out), str(audio)]
    if two_stems:
        cmd += ["--two-stems", "vocals"]
    env = {"PYTHONUTF8": "1"}
    subprocess.run(cmd, check=True, env=env)


def collect_demucs_stems(out_root: Path):
    """递归查找 Demucs 输出里的 expected stem wav。"""
    wanted = ["vocals", "drums", "bass", "other", "no_vocals"]
    found = {}
    for wav in out_root.rglob("*.wav"):
        if wav.stem in wanted:
            found[wav.stem] = wav
    return found


def write_wav(path: Path, data, sr: int):
    try:
        import soundfile as sf
    except ImportError:
        from scipy.io import wavfile
        wavfile.write(str(path), sr, data)
        return
    sf.write(str(path), data, sr)


def hpss_fallback(audio: Path, out: Path, two_stems: bool):
    """librosa HPSS 粗略分离。"""
    try:
        import librosa
        import numpy as np
        from scipy.signal import butter, sosfiltfilt
    except ImportError:
        print("[separate] HPSS 兜底需要 librosa/numpy/scipy", file=sys.stderr)
        sys.exit(1)

    y, sr = librosa.load(str(audio), sr=44100, mono=True)
    harmonic, percussive = librosa.effects.hpss(y)

    if two_stems:
        write_wav(out / "vocals.wav", harmonic, sr)
        write_wav(out / "no_vocals.wav", y - harmonic, sr)
        print("[separate] HPSS fallback: vocals.wav + no_vocals.wav (不是真实人声分离)")
        return

    sos = butter(8, 180.0, btype="low", fs=sr, output="sos")
    bass = sosfiltfilt(sos, harmonic)
    vocals = harmonic - bass
    other = y - bass - percussive
    write_wav(out / "drums.wav", percussive, sr)
    write_wav(out / "bass.wav", bass, sr)
    write_wav(out / "vocals.wav", vocals, sr)
    write_wav(out / "other.wav", other, sr)
    print("[separate] HPSS fallback: drums/bass/vocals/other (粗糙兜底)")


def main():
    ap = argparse.ArgumentParser(description="信号域人声/编曲分离")
    ap.add_argument("input", help="输入音频 MP3/WAV 等")
    ap.add_argument("--out", default="stems", help="输出目录")
    ap.add_argument("--two-stems", action="store_true",
                    help="只分 vocals / no_vocals 两轨")
    ap.add_argument("--no-demucs", action="store_true",
                    help="强制跳过 Demucs，直接使用 HPSS 兜底")
    args = ap.parse_args()

    audio = Path(args.input).resolve()
    if not audio.exists():
        print(f"输入音频不存在: {audio}", file=sys.stderr)
        sys.exit(1)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem_names = ["vocals.wav", "no_vocals.wav"] if args.two_stems else \
        ["vocals.wav", "drums.wav", "bass.wav", "other.wav"]

    with tempfile.TemporaryDirectory(prefix="midimaker_sep_") as tmpdir:
        tmp = Path(tmpdir)
        wav_input = convert_to_wav(audio, tmp)
        demucs_ok = False
        if not args.no_demucs:
            try:
                import demucs  # noqa
            except ImportError:
                print("[separate] demucs 未安装，使用 HPSS 兜底", file=sys.stderr)
            else:
                try:
                    demucs_out = tmp / "demucs_out"
                    demucs_out.mkdir()
                    run_demucs(wav_input, demucs_out, args.two_stems)
                    found = collect_demucs_stems(demucs_out)
                    copied = []
                    for name in stem_names:
                        stem = Path(name).stem
                        if stem in found:
                            shutil.copy2(str(found[stem]), str(out / name))
                            copied.append(name)
                    if copied:
                        demucs_ok = True
                        print(f"[separate] Demucs 完成: {', '.join(copied)}")
                except Exception as e:
                    print(f"[separate] Demucs 失败: {e}", file=sys.stderr)

        if not demucs_ok:
            hpss_fallback(wav_input, out, args.two_stems)

    print(f"[separate] 输出目录: {out}")


if __name__ == "__main__":
    main()
