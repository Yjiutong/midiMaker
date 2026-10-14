#!/usr/bin/env python3
"""
transcribe_stems.py - 各 stem 转 MIDI + 鼓分类 + 人声音高线

转录引擎（详见 references/transcription_algorithms.md）：
  - 默认: AutoTranscriber 风格纯 librosa CQT 管线
         CQT → 频谱通量 → 局部归一化起音检测 → 多音高估计(每帧 n_peaks 峰值)
         → 振幅衰减式音符追踪 → MIDI
  - 备选: Spotify Basic Pitch (--engine basicpitch)
  - 人声: CREPE 深度学习音高线 (torchcrepe)，不可用时退回 librosa.pyin

输出 (--out 默认 midi_raw/):
    bass.mid  other.mid  drums.mid  vocals_melody.mid
"""
import argparse
import sys
from pathlib import Path
import numpy as np

try:
    import librosa
    import pretty_midi
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    from scipy.signal import find_peaks
except ImportError:
    print("请先安装: pip install librosa pretty_midi scipy", file=sys.stderr)
    sys.exit(1)

SR = 22050
HOP = 512
FMIN = 65.41      # C2
FMAX = 2093.0     # C7
BPO = 36          # 每八度频带数 = 1/3 半音精度

# 复用本仓库的感知滤波做单声部去噪（符号域，无需 torch）
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from perceptual_filter import clean_notes as pf_clean_notes
except ImportError:
    pf_clean_notes = None


# ---------- 频率/MIDI 互转 ----------
def hz_to_midi(freq):
    if freq <= 0:
        return 0
    return int(round(12.0 * np.log2(freq / 440.0) + 69))


def midi_to_hz(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


# ---------- CQT 频谱（AutoTranscriber/spectral.py） ----------
def compute_cqt(y, sr=SR, hop=HOP, fmin=FMIN, fmax=FMAX, bpo=BPO):
    n_bins = int(np.ceil(bpo * np.log2(fmax / fmin)))
    cqt = np.abs(librosa.cqt(
        y, sr=sr, hop_length=hop, fmin=fmin, n_bins=n_bins,
        bins_per_octave=bpo, tuning=0.0, norm=1,
        window='hann', pad_mode='reflect'))
    times = librosa.frames_to_time(np.arange(cqt.shape[1]), sr=sr, hop_length=hop)
    freqs = librosa.cqt_frequencies(n_bins, fmin=fmin, bins_per_octave=bpo)
    cqt /= (np.max(cqt) + 1e-12)          # 帧内归一化，便于跨曲比较振幅
    return cqt, times, freqs


def compute_spectral_flux(cqt):
    cqt_db = librosa.amplitude_to_db(cqt, ref=np.max)
    diff = np.maximum(np.diff(cqt_db, axis=1), 0)     # 半波整流
    flux = np.sum(diff, axis=0)
    flux /= (np.max(flux) + 1e-12)
    return flux


# ---------- 起音检测（AutoTranscriber/onset_detection.py） ----------
def detect_onsets(flux, sr=SR, hop=HOP, threshold=0.3, min_distance=3, smooth_sigma=1.0):
    flux_smooth = gaussian_filter1d(flux, sigma=smooth_sigma)
    window = max(3, int(0.1 * sr / hop))              # ~100ms
    local_env = maximum_filter1d(flux_smooth, size=2 * window + 1, mode='nearest')
    norm = flux_smooth / (local_env + 1e-12)          # 局部归一化（消除动态范围影响）
    energy_floor = 0.05 * np.max(flux_smooth)
    score = np.where(flux_smooth >= energy_floor, norm, 0.0)
    peaks, _ = find_peaks(score, height=threshold * 0.6, distance=min_distance)
    if len(peaks) == 0:                               # 兜底: 局部均值自适应阈值
        window_mean = np.convolve(flux_smooth, np.ones(window) / window, mode='same')
        adaptive = window_mean + threshold * 0.3 * np.max(flux_smooth)
        fd = np.maximum(flux_smooth - adaptive, 0)
        peaks, _ = find_peaks(fd, height=1e-9, distance=min_distance)
    if len(peaks) == 0:                               # 最后兜底: 绝对阈值
        peaks, _ = find_peaks(flux_smooth, height=threshold * 0.1 * np.max(flux_smooth),
                              distance=min_distance)
    return peaks, peaks * hop / sr


# ---------- 多音高估计（每 onset 帧取 n_peaks 峰值 → MIDI） ----------
def estimate_pitches_onset_driven(cqt, freqs, times, onset_frames, sr=SR, hop=HOP,
                                  n_peaks=5, threshold_factor=0.1):
    onset_notes = []
    n_frames = cqt.shape[1]
    for of in onset_frames:
        col = cqt[:, of]
        peak_val = np.max(col)
        if peak_val < 1e-6:
            continue
        thr = peak_val * threshold_factor
        idx_sorted = np.argsort(col)[::-1]
        picked = 0
        used_freqs = []
        for bi in idx_sorted:
            if col[bi] < thr:
                break
            f = freqs[bi]
            # 跳过与已选频率相差不足半个半音的相邻峰值（避免同音重复）
            if any(abs(np.log2(f / uf)) < 0.5 / 12.0 for uf in used_freqs):
                continue
            used_freqs.append(f)
            amp = float(col[bi])
            # SNR: 该频带在 onset 之前的能量作为背景，真正起音应远大于背景
            bg_lo = max(0, of - 10)
            bg = np.mean(cqt[bi, bg_lo:of]) + 1e-9
            snr = amp / bg
            onset_notes.append({
                'pitch': hz_to_midi(f),
                'onset_frame': int(of),
                'onset_time': float(times[of]),
                'amplitude': amp,
                'snr': float(snr),
            })
            picked += 1
            if picked >= n_peaks:
                break
    return onset_notes


# ---------- 音符追踪（AutoTranscriber/note_tracking.py 振幅衰减式） ----------
def track_notes_onset_driven(onset_notes, cqt, freqs, times, sr=SR, hop=HOP,
                             max_gap_frames=3, decay_ratio=0.25,
                             min_note_frames=2, max_note_seconds=4.0,
                             velocity_scale=80.0, snr_threshold=0.5,
                             track_semitones=1.0, max_drift_semitones=3.0):
    if not onset_notes or cqt.size == 0:
        return []
    n_frames = cqt.shape[1]
    onset_notes = sorted(onset_notes, key=lambda n: n['onset_time'])
    onset_notes = [n for n in onset_notes if n['snr'] >= snr_threshold]

    notes = []
    active_pitches = {}

    for on in onset_notes:
        of = on['onset_frame']
        pitch = on['pitch']
        # 同音高已在响 → 先闭合旧音
        if pitch in active_pitches:
            prev = active_pitches.pop(pitch)
            end_time = times[of]
            if (end_time - times[prev['start_frame']]) >= min_note_frames * (hop / sr):
                vel = int(min(127, max(1, prev['start_amp'] * velocity_scale)))
                notes.append({'start': float(times[prev['start_frame']]),
                              'end': float(end_time), 'pitch': int(pitch), 'velocity': vel})
        freq = midi_to_hz(pitch)
        band_mask = (freqs >= freq * 2 ** (-1 / 12)) & (freqs <= freq * 2 ** (1 / 12))
        band_indices = np.where(band_mask)[0]
        if len(band_indices) == 0:
            continue
        peak_pos = int(np.argmax(cqt[band_indices, of]))
        start_amp_frame = float(cqt[band_indices[peak_pos], of])
        if start_amp_frame == 0:
            continue
        track_freq = float(freqs[band_indices[peak_pos]])

        end_frame = of
        below = 0
        max_end = min(n_frames - 1, of + int(max_note_seconds * sr / hop))
        for t in range(of + 1, max_end + 1):
            f_low = track_freq * 2 ** (-track_semitones / 12.0)
            f_high = track_freq * 2 ** (track_semitones / 12.0)
            win_mask = (freqs >= f_low) & (freqs <= f_high)
            win_idx = np.where(win_mask)[0]
            if len(win_idx) == 0:
                break
            pos = int(np.argmax(cqt[win_idx, t]))
            current_amp = float(cqt[win_idx[pos], t])
            track_freq = float(freqs[win_idx[pos]])
            if abs(12 * np.log2(track_freq / freq)) > max_drift_semitones:
                break
            if current_amp > decay_ratio * start_amp_frame:
                end_frame = t
                below = 0
            else:
                below += 1
                if below > max_gap_frames:
                    break
        if end_frame - of >= min_note_frames:
            active_pitches[pitch] = {'start_frame': of, 'start_amp': on['amplitude'],
                                    'end_frame': end_frame}

    for pitch, info in active_pitches.items():
        end_time = float(times[info['end_frame']])
        start_time = float(times[info['start_frame']])
        if (end_time - start_time) >= min_note_frames * (hop / sr):
            vel = int(min(127, max(1, info['start_amp'] * velocity_scale)))
            notes.append({'start': start_time, 'end': end_time,
                          'pitch': int(pitch), 'velocity': vel})

    notes = _merge_by_pitch(notes, gap_threshold=0.05)
    notes.sort(key=lambda n: n['start'])
    return notes


def _merge_by_pitch(notes, gap_threshold=0.05):
    if not notes:
        return []
    by_pitch = {}
    for n in notes:
        by_pitch.setdefault(n['pitch'], []).append(n)
    merged = []
    for pitch, lst in by_pitch.items():
        lst.sort(key=lambda n: n['start'])
        cur = dict(lst[0])
        for n in lst[1:]:
            if n['start'] - cur['end'] <= gap_threshold:
                cur['end'] = max(cur['end'], n['end'])
                cur['velocity'] = max(cur['velocity'], n['velocity'])
            else:
                merged.append(cur)
                cur = dict(n)
        merged.append(cur)
    return merged


# ---------- CQT 转录总入口 ----------
def transcribe_cqt(audio_path, n_peaks=5, fmin=FMIN, fmax=FMAX,
                   onset_threshold=0.3, pitch_threshold=0.1, hop=HOP):
    y, _ = librosa.load(audio_path, sr=SR, mono=True)
    cqt, times, freqs = compute_cqt(y, sr=SR, hop=hop, fmin=fmin, fmax=fmax)
    flux = compute_spectral_flux(cqt)
    onset_frames, _ = detect_onsets(flux, sr=SR, hop=hop, threshold=onset_threshold)
    onset_notes = estimate_pitches_onset_driven(
        cqt, freqs, times, onset_frames, sr=SR, hop=hop,
        n_peaks=n_peaks, threshold_factor=pitch_threshold)
    notes = track_notes_onset_driven(onset_notes, cqt, freqs, times, sr=SR, hop=hop)
    return notes


def notes_to_midi(note_events, program=0, is_drum=False):
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=program, is_drum=is_drum)
    for n in note_events:
        inst.notes.append(pretty_midi.Note(
            velocity=int(n.get('velocity', 80)),
            pitch=int(n['pitch']),
            start=float(n['start']),
            end=max(float(n['end']), float(n['start']) + 0.01)))
    midi.instruments.append(inst)
    return midi


# ---------- 人声音高线：CREPE 优先，pyin 后备 ----------
def estimate_vocal_pitch(audio_path, hop=320, model='tiny',
                         energy_threshold=0.02, min_duration_frames=5):
    """返回人声主旋律音高轮廓 note_events（仅供 Synthesizer V 参考，不识别歌词）。"""
    try:
        import torch
        import torchcrepe
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        audio_t = torch.from_numpy(y).unsqueeze(0).float()
        with torch.no_grad():
            f0 = torchcrepe.predict(audio_t, sr, hop_length=hop,
                                    batch_size=128, model=model)
        f0_np = f0.cpu().numpy().flatten()
        frame_energy = np.array([
            np.sum(y[max(0, i):min(len(y), i + hop)] ** 2)
            for i in range(0, len(y) - hop, hop)])
        frame_energy /= (np.max(frame_energy) + 1e-12)
        n = min(len(f0_np), len(frame_energy))
        voiced = (f0_np[:n] > 0) & (frame_energy[:n] > energy_threshold)
        pitch_seq = [hz_to_midi(f) if v else 0 for f, v in zip(f0_np[:n], voiced)]
        pitch_seq = _median_smooth(pitch_seq, window=3)
        times = np.arange(len(pitch_seq)) * hop / 16000.0
        return _merge_pitch_seq_to_notes(pitch_seq, times, min_duration_frames, velocity=80)
    except ImportError:
        print("[vocal] torchcrepe 不可用，退回 librosa.pyin 做单音提取")
        return estimate_vocal_pitch_pyin(audio_path)


def estimate_vocal_pitch_pyin(audio_path, hop=512, fmin=65.41, fmax=1000.0,
                              min_duration_frames=3, threshold=0.3):
    y, sr = librosa.load(audio_path, sr=SR, mono=True)
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y, sr=sr, fmin=fmin, fmax=fmax, hop_length=hop, fill_na=0.0)
    voiced = (voiced_flag > 0) & (voiced_prob > threshold) & (f0 > 0)
    try:
        from scipy.signal import medfilt
        voiced = medfilt(voiced.astype(int), kernel_size=5).astype(bool)
    except Exception:
        pass
    pitch_seq = [hz_to_midi(f0[i]) if voiced[i] else 0 for i in range(len(f0))]
    pitch_seq = _median_smooth(pitch_seq, window=5)
    times = librosa.frames_to_time(np.arange(len(pitch_seq)), sr=sr, hop_length=hop)
    return _merge_pitch_seq_to_notes(pitch_seq, times, min_duration_frames, velocity=80)


def _median_smooth(seq, window=3):
    out = list(seq)
    for i in range(window, len(seq) - window):
        if seq[i] > 0:
            nb = [seq[i + j] for j in range(-window, window + 1) if seq[i + j] > 0]
            if nb:
                out[i] = int(np.median(nb))
    return out


def _merge_pitch_seq_to_notes(pitch_seq, times, min_duration_frames, velocity=80):
    notes = []
    cur_pitch = 0
    cur_start = 0
    cur_count = 0
    for i, pitch in enumerate(pitch_seq):
        if pitch > 0:
            if cur_pitch == 0:
                cur_pitch, cur_start, cur_count = pitch, i, 1
            elif abs(pitch - cur_pitch) <= 1:
                cur_pitch, cur_count = pitch, cur_count + 1
            else:
                if cur_count >= min_duration_frames:
                    notes.append({'start': float(times[cur_start]),
                                  'end': float(times[i]), 'pitch': int(cur_pitch),
                                  'velocity': velocity})
                cur_pitch, cur_start, cur_count = pitch, i, 1
        else:
            if cur_pitch > 0 and cur_count >= min_duration_frames:
                notes.append({'start': float(times[cur_start]),
                              'end': float(times[i]), 'pitch': int(cur_pitch),
                              'velocity': velocity})
            cur_pitch = 0
            cur_count = 0
    if cur_pitch > 0 and cur_count >= min_duration_frames:
        notes.append({'start': float(times[cur_start]),
                      'end': float(times[-1]), 'pitch': int(cur_pitch),
                      'velocity': velocity})
    return notes


# ---------- 鼓分类（onset + 频段能量 → GM 鼓键） ----------
def classify_drum_hits(y, sr):
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    times = librosa.times_like(onset_env, sr=sr)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="frames")
    if len(onset_frames) == 0:
        return []
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    lo_band = freqs <= 150
    mid_band = (freqs > 150) & (freqs <= 2000)
    hi_band = freqs > 6000
    hits = []
    for f in onset_frames:
        t = times[f]
        seg = S[:, max(0, f - 1):f + 2]
        e_lo = seg[lo_band].sum()
        e_mid = seg[mid_band].sum()
        e_hi = seg[hi_band].sum()
        total = e_lo + e_mid + e_hi + 1e-9
        r_lo, r_hi = e_lo / total, e_hi / total
        if r_lo > 0.45:
            key = 36           # kick
        elif r_hi > 0.5:
            key = 46 if onset_env[f] > np.percentile(onset_env, 70) else 42  # open/closed hat
        elif e_mid > e_hi:
            key = 38           # snare
        else:
            key = 49           # crash/cymbal 兜底
        vel = int(np.clip(60 + onset_env[f] * 30, 40, 120))
        hits.append((float(t), int(key), int(vel)))
    return hits


def build_drum_midi(hits):
    midi = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0, is_drum=True)   # 通道 9 = 鼓
    for t, key, vel in hits:
        inst.notes.append(pretty_midi.Note(velocity=vel, pitch=key,
                                           start=t, end=t + 0.12))
    midi.instruments.append(inst)
    return midi


# ---------- Basic Pitch 备选引擎 ----------
def transcribe_melodic_basic_pitch(audio_path, min_freq=None, max_freq=None):
    from basic_pitch.inference import predict, Model
    from basic_pitch import ICASSP_2022_MODEL_PATH
    model = Model(ICASSP_2022_MODEL_PATH)
    _, midi_data, note_events = predict(
        audio_path, model,
        onset_thresh=0.5, frame_thresh=0.3, min_note_len=11,
        infer_onsets=True, melodia_trick=True,
        min_freq=min_freq, max_freq=max_freq)
    return midi_data, note_events


# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser(description="stem 转 MIDI + 鼓分类 + 人声音高线")
    ap.add_argument("stems", help="stem 目录(含 vocals/drums/bass/other.wav)")
    ap.add_argument("--out", default="midi_raw", help="输出目录")
    ap.add_argument("--engine", choices=["cqt", "basicpitch"], default="cqt",
                    help="转录引擎: cqt(AutoTranscriber 风格) / basicpitch")
    ap.add_argument("--n-peaks", type=int, default=5,
                    help="每帧最大同时音符数(贝斯设1-2,和弦设5-8)")
    args = ap.parse_args()

    sd = Path(args.stems)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.engine == "basicpitch":
        try:
            import basic_pitch  # noqa
        except ImportError:
            print("basicpitch 未安装，回退到 cqt 引擎", file=sys.stderr)
            args.engine = "cqt"

    # 贝斯
    bass_wav = sd / "bass.wav"
    if bass_wav.exists():
        if args.engine == "cqt":
            notes = transcribe_cqt(str(bass_wav), n_peaks=2, fmin=30, fmax=260)
            notes = [n for n in notes if n['pitch'] <= 59]     # 限定贝斯音区
            if pf_clean_notes:                                  # 符号域去噪: 去倍频/离群/碎音
                notes = pf_clean_notes(notes, min_duration=0.04,
                                       merge_gap=0.06, outlier_semitones=10)
            notes_to_midi(notes, program=33).write(str(out / "bass.mid"))
        else:
            md, _ = transcribe_melodic_basic_pitch(str(bass_wav), min_freq=30, max_freq=260)
            md.write(str(out / "bass.mid"))
        print("[transcribe] bass.mid 完成")

    # other（后续 split_arrangement 拆分主旋律/和声）
    other_wav = sd / "other.wav"
    if not other_wav.exists():
        other_wav = sd / "no_vocals.wav"      # 兼容 two-stems 输出
    if other_wav.exists():
        if args.engine == "cqt":
            notes = transcribe_cqt(str(other_wav), n_peaks=args.n_peaks)
            notes_to_midi(notes, program=0).write(str(out / "other.mid"))
        else:
            md, _ = transcribe_melodic_basic_pitch(str(other_wav))
            md.write(str(out / "other.mid"))
        print("[transcribe] other.mid 完成（待 split_arrangement 拆分主旋律/和声）")

    # 鼓
    drums_wav = sd / "drums.wav"
    if drums_wav.exists():
        y, sr = librosa.load(str(drums_wav), sr=SR, mono=True)
        hits = classify_drum_hits(y, sr)
        build_drum_midi(hits).write(str(out / "drums.mid"))
        print(f"[transcribe] drums.mid 完成，{len(hits)} 个鼓点")

    # 人声主旋律音高线（CREPE / pyin）
    vocals_wav = sd / "vocals.wav"
    if vocals_wav.exists():
        vnotes = estimate_vocal_pitch(str(vocals_wav))
        notes_to_midi(vnotes, program=0).write(str(out / "vocals_melody.mid"))
        print(f"[transcribe] vocals_melody.mid 完成（{len(vnotes)} 个音高事件，仅供 SV 参考）")

    print(f"\n输出目录: {out}")


if __name__ == "__main__":
    main()
