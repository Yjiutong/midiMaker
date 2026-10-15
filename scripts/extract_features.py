#!/usr/bin/env python3
"""extract_features.py - 提取全局音乐特征到 features.json。

CLI:
  python scripts/extract_features.py input.mp3 --stems stems/ --out features.json

输出字段供 style_report.py / instrument_map.py / build_fingerprint.py 使用：
  bpm / key / scale / beats / chord_sequence / sections / spectral_* / rms /
  onset_density / stem_energy / duration_sec
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_runtime import prepend_site_packages  # noqa: E402
prepend_site_packages()


def _load_audio(audio_path):
    try:
        import librosa
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py（最佳）或 pip install librosa", file=sys.stderr)
        sys.exit(1)
    return librosa.load(str(audio_path), sr=22050, mono=True)


def _estimate_key(librosa, chroma):
    import numpy as np
    profile = chroma.mean(axis=1)
    if profile.max() == 0:
        return "C", "major", 0.0
    pitch_classes = ["C", "C#", "D", "D#", "E", "F",
                     "F#", "G", "G#", "A", "A#", "B"]
    pc = int(np.argmax(profile))
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                              2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                              2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    best_scale, best_key, best_corr = "major", 0, -999.0
    for scale, prof in (("major", major_profile), ("minor", minor_profile)):
        for shift in range(12):
            rolled = np.roll(profile, -shift)
            denom = np.sqrt(np.sum(rolled ** 2) * np.sum(prof ** 2)) + 1e-9
            corr = float(np.dot(rolled, prof) / denom)
            if corr > best_corr:
                best_corr = corr
                best_scale = scale
                best_key = shift
    return pitch_classes[best_key], best_scale, float(best_corr)


def _chord_label(chroma_col):
    import numpy as np
    pitch_classes = ["C", "C#", "D", "D#", "E", "F",
                     "F#", "G", "G#", "A", "A#", "B"]
    root = int(np.argmax(chroma_col))
    third = (root + 4) % 12 if chroma_col[(root + 4) % 12] >= chroma_col[(root + 3) % 12] \
        else (root + 3) % 12
    suffix = "maj" if chroma_col[(root + 4) % 12] >= chroma_col[(root + 3) % 12] else "min"
    _ = third
    return f"{pitch_classes[root]}:{suffix}"


def _sections(librosa, y, sr, hop_length=512):
    import numpy as np
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    n = len(onset_env)
    times = librosa.times_like(onset_env, sr=sr, hop_length=hop_length)
    if n <= 1:
        return [{"id": 0, "label": "A", "start": 0.0, "end": float(len(y) / sr),
                 "duration": float(len(y) / sr)}]
    bounds = [0]
    peaks = librosa.util.peak_pick(onset_env, pre_max=8, post_max=8,
                                   pre_avg=8, post_avg=8, delta=0.06, wait=20)
    if len(peaks) >= 2:
        peaks = peaks[np.argsort(onset_env[peaks])[-5:]]
        peaks.sort()
        # 去掉离曲首/曲尾太近的边界，避免出现 0:00-0:00 的碎片段落。
        duration_sec = float(len(y) / sr)
        for p in peaks:
            t = float(times[p])
            if 1.5 < t < duration_sec - 1.5:
                bounds.append(int(p))
    bounds.append(n - 1)
    bounds = sorted(set(bounds))
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)

    raw_sections = []
    labels = ["A", "B", "C", "D", "E", "F", "G", "H"]
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        seg_chroma = chroma[:, s:e].mean(axis=1) if e > s else chroma[:, s]
        start = float(times[s])
        end = float(times[e])
        raw_sections.append({
            "id": i,
            "label": "?",
            "start": start,
            "end": end,
            "duration": round(end - start, 3),
            "chroma": seg_chroma,
        })

    # 合并过短段落：短的优先并入前一段，段首碎片并入后一段。
    min_seconds = 6.0
    merged = []
    for sec in raw_sections:
        if not merged:
            merged.append(sec)
            continue
        prev = merged[-1]
        if sec["duration"] < min_seconds or prev["duration"] < min_seconds:
            prev["end"] = sec["end"]
            prev["duration"] = round(prev["end"] - prev["start"], 3)
        else:
            merged.append(sec)
    if merged:
        merged[-1]["end"] = float(len(y) / sr)
        merged[-1]["duration"] = round(merged[-1]["end"] - merged[-1]["start"], 3)

    # 用已有段落色度相似度贴 A/B/C 标签，重复段落复用旧标签。
    label_means = []
    next_label = 0
    sections = []
    for sec in merged:
        best_label, best_corr = None, -1.0
        for idx, mean in enumerate(label_means):
            denom = (np.sqrt(np.sum(sec["chroma"] ** 2)) *
                     np.sqrt(np.sum(mean ** 2)) + 1e-9)
            corr = float(np.dot(sec["chroma"], mean) / denom)
            if corr > best_corr:
                best_corr = corr
                best_label = labels[idx]
        if best_corr >= 0.88 and best_label is not None:
            label = best_label
        else:
            label = labels[min(next_label, len(labels) - 1)]
            label_means.append(sec["chroma"])
            next_label += 1
        sections.append({
            "id": len(sections),
            "label": label,
            "start": round(sec["start"], 3),
            "end": round(sec["end"], 3),
            "duration": round(sec["end"] - sec["start"], 3),
        })
    return sections


def _stem_energy(librosa, stems_dir, expected):
    import numpy as np
    result = {}
    sd = Path(stems_dir) if stems_dir else None
    if sd and sd.exists():
        for name in expected:
            p = sd / f"{name}.wav"
            if p.exists():
                try:
                    y, _ = librosa.load(str(p), sr=22050, mono=True)
                    rms = float(np.sqrt(np.mean(y ** 2) + 1e-12))
                    result[name] = round(rms, 6)
                except Exception:
                    continue
    return result


def _stem_spectral(librosa, stems_dir, expected, hop=512):
    import numpy as np
    result = {}
    sd = Path(stems_dir) if stems_dir else None
    if sd and sd.exists():
        for name in expected:
            p = sd / f"{name}.wav"
            if not p.exists():
                continue
            try:
                y, sr = librosa.load(str(p), sr=22050, mono=True)
                dur = max(float(len(y) / sr), 1e-6)
                S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
                cent = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
                bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)[0]
                rms = librosa.feature.rms(S=S)[0]
                flux = np.mean(np.abs(np.diff(S, axis=1)))
                denom = float(np.mean(S) + 1e-9)
                roughness = float(flux / denom)
                onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
                onset_count = len(librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr))
                result[name] = {
                    "rms": round(float(np.mean(rms)), 6),
                    "spectral_centroid": round(float(np.mean(cent)), 1),
                    "spectral_bandwidth": round(float(np.mean(bandwidth)), 1),
                    "roughness": round(roughness, 4),
                    "onset_count": int(onset_count),
                    "onset_density": round(onset_count / dur, 3),
                }
            except Exception:
                continue
    return result


def _timbre_profile(librosa, y, sr, hop=512):
    """计算一段音频的模型友好音色特征。"""
    import numpy as np
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
    if S.size == 0:
        return None
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    cent = librosa.feature.spectral_centroid(S=S, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(S=S, sr=sr)[0]
    flatness = librosa.feature.spectral_flatness(S=S)[0]
    contrast = librosa.feature.spectral_contrast(S=S, sr=sr)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, hop_length=hop, roll_percent=0.85)[0]
    zcr = librosa.feature.zero_crossing_rate(y, hop_length=hop)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=14, hop_length=hop)
    seg_energy = np.sum(S, axis=0) + 1e-12
    low_ratio = float(np.mean(np.sum(S[freqs <= 200.0], axis=0) / seg_energy))
    bright_norm = float(np.mean(cent) / (sr / 2.0))

    tags = []
    if bright_norm > 0.24:
        tags.append("明亮")
    elif bright_norm < 0.10:
        tags.append("偏暗")
    else:
        tags.append("中性亮度")
    mean_flat = float(np.mean(flatness))
    if mean_flat > 0.35:
        tags.append("噪声感")
    elif mean_flat < 0.12:
        tags.append("干净集中")
    else:
        tags.append("中等平坦")
    if low_ratio > 0.20:
        tags.append("低频厚重")
    if float(np.mean(zcr)) > 0.15:
        tags.append("颗粒/失真")
    if not tags:
        tags.append("中性")

    return {
        "brightness": round(bright_norm, 4),
        "spectral_centroid": round(float(np.mean(cent)), 1),
        "spectral_bandwidth": round(float(np.mean(bandwidth)), 1),
        "spectral_flatness": round(mean_flat, 4),
        "spectral_rolloff": round(float(np.mean(rolloff)), 1),
        "zero_crossing_rate": round(float(np.mean(zcr)), 4),
        "low_energy_ratio": round(low_ratio, 4),
        "spectral_contrast_mean": [round(float(v), 2) for v in contrast.mean(axis=1)],
        "mfcc_mean": [round(float(v), 2) for v in mfcc.mean(axis=1)],
        "mfcc_std": [round(float(v), 2) for v in mfcc.std(axis=1)],
        "tags": tags,
    }


def _stem_timbre(librosa, stems_dir, expected, hop=512):
    result = {}
    sd = Path(stems_dir) if stems_dir else None
    if sd and sd.exists():
        for name in expected:
            p = sd / f"{name}.wav"
            if not p.exists():
                continue
            try:
                y, sr = librosa.load(str(p), sr=22050, mono=True)
                profile = _timbre_profile(librosa, y, sr, hop=hop)
                if profile:
                    result[name] = profile
            except Exception:
                continue
    return result


def main():
    ap = argparse.ArgumentParser(description="提取音乐全局特征")
    ap.add_argument("input", help="输入音频")
    ap.add_argument("--stems", default="stems", help="stem 目录")
    ap.add_argument("--out", default="features.json", help="输出 JSON")
    ap.add_argument("--virtual-singer", action="store_true",
                    help="开启虚拟歌姬歌曲特化特征")
    args = ap.parse_args()

    audio_path = Path(args.input)
    if not audio_path.exists():
        print(f"输入音频不存在: {audio_path}", file=sys.stderr)
        sys.exit(1)
    try:
        import librosa
        import numpy as np
    except ImportError:
        print("缺少依赖：请先运行 python scripts/install_skill_deps.py（最佳）或 pip install librosa numpy", file=sys.stderr)
        sys.exit(1)

    y, sr = _load_audio(audio_path)
    duration = float(len(y) / sr)
    hop = 512

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
    bpm = float(tempo) if np.isscalar(tempo) else float(tempo[0])

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    key, scale, tonality_confidence = _estimate_key(librosa, chroma)

    # 每 2 秒一个和弦窗口。
    frames_per_window = max(1, int(2.0 * sr / hop))
    chord_sequence = []
    chord_times = []
    for start in range(0, chroma.shape[1], frames_per_window):
        end = min(chroma.shape[1], start + frames_per_window)
        col = chroma[:, start:end].mean(axis=1)
        chord_sequence.append(_chord_label(col))
        chord_times.append(round(start * hop / sr, 3))

    sections = _sections(librosa, y, sr, hop_length=hop)
    spectral = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, hop_length=hop)
    rms = librosa.feature.rms(y=y, hop_length=hop)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="frames")

    features = {
        "source": str(audio_path),
        "duration_sec": round(duration, 3),
        "audio_kind": "virtual_singer" if args.virtual_singer else "general_song",
        "virtual_singer": args.virtual_singer,
        "bpm": round(bpm, 2),
        "beats": [round(float(t), 3) for t in librosa.frames_to_time(beats, sr=sr, hop_length=hop)],
        "key": key,
        "scale": scale,
        "tonality_confidence": round(tonality_confidence, 4),
        "chord_sequence": chord_sequence,
        "chord_times": chord_times,
        "sections": sections,
        "spectral_centroid": round(float(np.mean(spectral)), 1),
        "spectral_bandwidth": round(float(np.mean(bandwidth)), 1),
        "rms": round(float(np.mean(rms)), 6),
        "onset_frames": int(len(onset_frames)),
        "onset_density": round(len(onset_frames) / max(duration, 1e-6), 3),
        "timbre": _timbre_profile(librosa, y, sr, hop=hop),
        "stem_energy": _stem_energy(librosa, args.stems, ["vocals", "drums", "bass", "other"]),
        "stem_spectral": _stem_spectral(librosa, args.stems, ["vocals", "drums", "bass", "other"]),
        "stem_timbre": _stem_timbre(librosa, args.stems, ["vocals", "drums", "bass", "other"], hop=hop),
    }

    if args.virtual_singer:
        vocal_path = Path(args.stems) / "vocals.wav"
        if vocal_path.exists():
            y_voc, _ = librosa.load(str(vocal_path), sr=22050, mono=True)
            vocab_duration = max(float(len(y_voc) / 22050.0), 1e-6)
            voc_onset_env = librosa.onset.onset_strength(y=y_voc, sr=22050, hop_length=hop)
            voc_onsets = librosa.onset.onset_detect(onset_envelope=voc_onset_env,
                                                    sr=22050, units="frames")
            features["syllabic_density"] = round(len(voc_onsets) / vocab_duration, 3)
            S = np.abs(librosa.stft(y_voc))
            flatness = librosa.feature.spectral_flatness(S=S)
            denom = float(np.mean(flatness) + 1e-9)
            stability = 1.0 - min(1.0, float(np.std(flatness)) / denom)
            features["formant_stability"] = round(stability, 4)
        else:
            features["syllabic_density"] = None
            features["formant_stability"] = None

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    with open(out, "w", encoding="utf-8") as f:
        json.dump(features, f, ensure_ascii=False, indent=2)
    print(f"[extract_features] 输出: {out}")


if __name__ == "__main__":
    main()
