# 转录算法参考（Transcription Algorithms）

> 本 skill 的转录引擎**首选参考 [Yjiutong/AutoTranscriber-WebUI](https://github.com/Yjiutong/AutoTranscriber-WebUI)**（AutoTranscriber 项目的 WebUI 适配）。  
>     它原生集成了 **Demucs 音源分离 + CQT 多音高估计 + 起音检测 + 振幅衰减式音符追踪 + CREPE 人声音高线**，  
>     与我们的「拆多轨 → 多轨 MIDI → SV 人声」目标链路高度一致，是落地首选。
> 同时保留两条备选/教学路线：
> - **Spotify Basic Pitch**（`spotify/basic-pitch`）—— 高精度神经网络引擎，作精确转录备选。
> - **gityag/Automated-Music-Transcription** —— 教学用 CQT 时间桶解码，帮助理解 AMT 原理。
> 我们的 `transcribe_stems.py` 同时实现 **AutoTranscriber 风格的纯 librosa CQT 管线** 与 **Basic Pitch API** 两条路径，可按质量/速度需求切换。

## 一、AutoTranscriber 核心算法（首选参考，已复刻）

项目结构：`AutoTranscriber/` 内含 `spectral.py / onset_detection.py / pitch_estimation.py / note_tracking.py / separator.py / crepe_wrapper.py / midi_writer.py`。

### 1. 音源分离（`separator.py`）

```python
# Demucs 仅分离人声/伴奏两轨（two-stems），比 4-stem 更快更准
cmd = ["python", "-m", "demucs", "--two-stems", "vocals",
       "-o", out_dir, "-n", "htdemucs", "--device", "cpu", wav]
# 输出: {out_dir}/htdemucs/{name}/vocals.wav + no_vocals.wav
# 后备: 若 Demucs 不可用 → librosa HPSS + 80~2000Hz 带通粗分人声
```

- 非 WAV（mp3/m4a/ogg）先经 `librosa.load → soundfile` 转码为临时 WAV（44100 Hz）。

- HPSS 后备方案用 `librosa.effects.hpss` 分离谐波/打击乐，再 `butter` 带通 80–2000 Hz 估算人声，**质量明显低于 Demucs**，仅兜底。

### 2. CQT 频谱（`spectral.py`）

```python
cqt = np.abs(librosa.cqt(y, sr=22050, hop_length=512,
                         fmin=65.41, fmax=2093.0,        # C2 ~ C7
                         n_bins=int(36*log2(2093/65.41)),
                         bins_per_octave=36,             # 1/3 半音精度
                         tuning=0.0, norm=1, window='hann'))
freqs = librosa.cqt_frequencies(n_bins, fmin=65.41, bins_per_octave=36)
times = librosa.frames_to_time(np.arange(n_frames), sr=22050, hop_length=512)
```

### 3. 频谱通量（起音特征，`spectral.py`）

```python
cqt_db = librosa.amplitude_to_db(cqt, ref=np.max)
diff = np.maximum(np.diff(cqt_db, axis=1), 0)   # 半波整流（只取能量增加）
flux = np.sum(diff, axis=0)                      # 沿频率轴求和
flux /= np.max(flux)                             # 归一化
```

### 4. 起音检测（`onset_detection.py`）—— 关键的「局部归一化」技巧

```python
flux_smooth = gaussian_filter1d(flux, sigma=1.0)
window = max(3, int(0.1*sr/hop))                 # 约 100ms
local_env = maximum_filter1d(flux_smooth, size=2*window+1, mode='nearest')
norm = flux_smooth / (local_env + 1e-12)          # 消除动态范围影响
energy_floor = 0.05 * np.max(flux_smooth)        # 绝对能量门限（防静音段噪声）
score = np.where(flux_smooth >= energy_floor, norm, 0.0)
peaks, _ = find_peaks(score, height=threshold*0.6, distance=min_distance)
# 兜底: 局部均值自适应阈值 → 最后绝对阈值
```

> 设计要点：长音/持续段在局部窗口内接近自身包络 → `norm≈1`；真正的瞬态 onset 相对自身包络也≈1，但持续段不会因绝对能量高而压过弱 onset。**归一化消除了强弱段落的动态范围影响**，是比纯能量阈值更稳的做法。

### 5. 多音高估计（`pitch_estimation.py`）

逐帧取 CQT 幅度最大的 `n_peaks` 个峰值（默认 5，钢琴模式强制 2），将频率映射为 MIDI：

```python
def hz_to_midi(freq):
    if freq <= 0:
        return 0
    return int(round(12*np.log2(freq/440.0) + 69))   # A4=440
# 每帧 frame_notes: [{pitch, amplitude}]，amplitude=CQT 幅度
```

- 钢琴模式额外做 `n_peaks=2` 限制 + 中值滤波去单帧毛刺。

- 人声单音（`estimate_vocal_pitch`）改用 `librosa.pyin`（f0 + voiced_prob）做单音提取，置信度阈值 0.3 + 中值滤波(kernel=5) + 最短时长（≥3 帧）。

### 6. 音符追踪（`note_tracking.py`）—— 基于振幅衰减

```python
def track_notes_onset_driven(onset_notes, cqt, freqs, times, sr, hop,
                             max_gap_frames=3, decay_ratio=0.25,
                             min_note_frames=2, max_note_seconds=4.0,
                             velocity_scale=80.0, snr_threshold=0.5,
                             track_semitones=1.0, max_drift_semitones=3.0):
    # 1) 剔除低 SNR 起音（噪声）
    # 2) 每起音在 CQT 中找到 ±1 半音频带，取起始帧峰值振幅 start_amp
    # 3) 逐帧向前追踪：在上一帧 ±track_semitones 滑动窗内找最大能量（跟随颤音）
    # 4) 振幅衰减到 < decay_ratio×start_amp 时记 end_frame；
    #    连续 below_threshold 超过 max_gap_frames 则结束（防颤音误断）
    # 5) 漂移保护：|12*log2(track_freq/freq)| > max_drift_semitones 则停止
    # 6) velocity = clip(start_amp * velocity_scale, 1, 127)
    # 7) 相同音高相邻音符按 gap_threshold=0.05s 合并
```

> 相比「逐帧拼接连续同音高」，这种**起音→衰减→延音**的追踪更符合人耳感知。

### 7. 人声专用 CREPE 音高线（`crepe_wrapper.py`）

```python
# torchcrepe 深度学习音高估计（独立 venv 子进程调用）
f0 = torchcrepe.predict(audio_t, sr=16000, hop_length=320, model='tiny')
voiced = (f0 > 0) & (frame_energy > 0.02)          # 能量门限 0.02
pitch_seq = [hz_to_midi(f) if v else 0 for f, v in zip(f0, voiced)]
# 中值滤波平滑(window=3) → 合并连续同音(±1半音) → min_duration=5 帧
# 输出: [{start, end, pitch, velocity}]
```

CREPE 对人声基频估计鲁棒，适合直接作为 Synthesizer V 的**主旋律音高轮廓**参考。

### 8. 主流程调用顺序（`main.py`）

```
[--separate] separate_audio (Demucs two-stems)  →  vocals / no_vocals
load_audio(sr=22050) → preprocess
compute_cqt(hop=512, bins=36)
compute_spectral_flux → detect_onsets(threshold=0.3)
estimate_pitches(n_peaks=5)  / estimate_pitches_onset_driven
track_notes / track_notes_onset_driven(decay=0.25)
[perceptual] perceptual_filter(harmonic_check=True)
write_midi / write_multitrack_midi
```

### 9. 关键参数对照表

| 参数 | 默认 / 钢琴模式 | 含义 |
| --- | --- | --- |
| `sr` | 22050 | 分析采样率 |
| `hop_length` | 512 / 256 | 帧移，越小时间精度越高 |
| `fmin` / `fmax` | 65.41 / 2093.0 | CQT 频带（C2~C7） |
| `bins_per_octave` | 36 | 1/3 半音精度 |
| `n_peaks` | 5 / 2 | 每帧最大同时音符数 |
| `onset_threshold` | 0.3 / 0.15 | 起音灵敏度 |
| `pitch_threshold` | 0.1 / 0.2 | 音高幅度阈值因子 |
| `min_note_duration` | 4（帧） | 最小音符时长，滤短噪声 |
| `decay_ratio` | 0.25 | 振幅衰减比例判定音符结束 |
| `snr_threshold` | 0.5 | 起音信噪比门限 |
| `velocity_scale` | 80.0 | 力度 = 起始振幅 × 该系数 |

## 二、Spotify Basic Pitch（高精度备选引擎）

论文：*A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch Estimation* (ICASSP 2022, Spotify)。

### 输入与结构

- 单声道重采样 22050 Hz → 提取 **HCQT**（谐波 CQT）特征。

- 轻量全卷积网络，输出三头概率矩阵：**onset / frame / contour**（1/3 半音精度）。

### 解码（`note_creation`）

1. 频率约束（`min_freq/max_freq`）。

2. 推断起音：frame 帧间差分融合到 onset。

3. **极大值抑制**（`argrelmax`，`>= onset_thresh`）找候选起音。

4. **定尾音**：向后统计连续低于 `frame_thresh` 帧数，超过 `energy_tol`（默认 11）才结束，允许音符内短暂掉帧。

5. **最小音符长度** 11 帧过滤。

6. 力度 = 区间内 frame 均值 ×127。

7. Melodia 补充提取遗漏音符。

8. contour 高斯窗（std=5）估弯音 → MIDI Pitch Bend。

### 程序化调用（本 skill 备选）

```python
from basic_pitch.inference import predict, Model
from basic_pitch import ICASSP_2022_MODEL_PATH
model = Model(ICASSP_2022_MODEL_PATH)
_, midi_data, note_events = predict(audio_path, model,
    onset_thresh=0.5, frame_thresh=0.3, min_note_len=11,
    infer_onsets=True, melodia_trick=True,
    min_freq=..., max_freq=...)
```

## 三、gityag/Automated-Music-Transcription（教学参考）

- 特征：`librosa.cqt` 取实部 → log-CQT 幅度谱。

- 解码：模型输出二值 piano-roll，按**时间桶**转 note_on/off，`pitch = scaled + 21`（A0）。

- 简单可解释，但无 onset/frame 融合、无弯音、无 Melodia，精度低于前两者，仅作原理教学。

## 四、本 skill 的转录策略（落实到 transcribe_stems.py）

| 目标轨 | 来源 stem | 转录方式 |
| --- | --- | --- |
| 贝斯 (Bass) | `bass` | CQT 管线取低音区（MIDI \< 60）→ 或 Basic Pitch `max_freq≈260Hz` |
| 鼓组 (Drums) | `drums` | onset + 频段能量分类 → GM 鼓键(35–59) |
| 主旋律 (Melody) | `other` | CQT 管线转录整层 → `split_arrangement.py` 调用 `perceptual_filter` 按乐理分层提取 |
| 和声·Pad | `other` | 同上，中音区与旋律协和的残留音归入伴奏层 |
| 人声 (Vocal) | `vocals` | **CREPE 音高线**（音高轮廓）+ 节奏格子；不识别歌词 |

> **人声分离是两层而非一层**：先由 `separate_stems.py` 在**信号域**用 Demucs（HPSS 兜底）把人声从混音中剥离，  
>     再由 `vocal_track_sv.py` / `transcribe_stems.py` 在**符号域**对剥离出的人声单声部做 CREPE 音高提取。  
>     两层解耦：信号域负责"把声音分出来"，符号域负责"把音高记下来"。详见文末第五、六节。

### 置信度声明

- `drums`/`bass` 分离较准；`other` 混叠较多，主旋律提取置信度需在报告中标注。

- 自动转录对密集织体、失真吉他、重叠人声误差明显，**所有 MIDI 仅供编曲参考，需在 FL Studio 中人工修音**。

## 五、人声分离的两层架构（本 skill 工程落地）

AutoTranscriber 的"人声分离"实际上由**两个独立阶段**构成，二者目标不同、不可互相替代：

### 层 1 — 信号域分离（`separate_stems.py`，移植自 `separator.py`）

- **目标**：从混音波形中剥离出干净的 `vocals.wav`，供后续单独处理。

- **主路径**：Demucs `--two-stems vocals`（`htdemucs`）→ `vocals.wav` + `no_vocals.wav`。

  <BulletedList id="0oOl2fBQTM3HVIOKdO6McW">
    我们默认用 **4-stem**（`vocals/drums/bass/other`）以支撑编曲元素分轨；`--two-stems vocals` 则与上游一致。
  </BulletedList>

  <BulletedList id="ee4jHtr3hfXB9x3y8xXvZH">
    **跨平台修复**：上游硬编码了 Windows conda 路径 `C:\Users\kotsu\miniconda3\...`，我们改为 `sys.executable -m demucs`，任何系统可用。
  </BulletedList>

  <BulletedList id="mfBek07WosyHljBHSad2hd">
    **格式转码**：非 WAV（mp3/m4a/ogg/flac 等）先经 `librosa.load → soundfile` 转码为 44100Hz WAV 再送入 Demucs。
  </BulletedList>

- **兜底**：Demucs 不可用/超时时 → `librosa.effects.hpss` 分离谐波/打击乐 + `butter` 带通 80–2000Hz 粗估人声（`_hpss_separate`）。质量明显低于 Demucs，但**无需模型即可运行**，保证流程不中断。

### 层 2 — 符号域人声转录（`transcribe_stems.py` → `estimate_vocal_pitch`）

- **目标**：对已经分离干净的人声单声部，提取主旋律音高轮廓（不识别歌词）。

- **主路径**：CREPE 深度学习音高（`torchcrepe`，16000Hz，hop=320，model='tiny'）→ 能量门限 0.02 取 voiced → 中值平滑 → 合并 ±1 半音连续段。

- **后备**：无 torchcrepe 时退回 `librosa.pyin`（f0+voiced_prob，阈值 0.3，中值滤波 kernel=5）。

- **输出**：`vocals_melody.mid`（音高轮廓），交给 `vocal_track_sv.py` 生成 SV 参考包。

> 关键直觉：**只在人声 stem 上跑 CREPE**，伴奏走 CQT 管线——这正是 AutoTranscriber 在 `main.py` 中的做法（`if stem_label=='人声' and has_crepe() → estimate_vocal_pitch_crepe`）。

## 六、符号域旋律-伴奏分层分离（`perceptual_filter.py`，移植自 `perceptual_filter.py`）

AutoTranscriber 在 `--perceptual` 模式下，对**转录后的音符事件**（而非波形）再做一次"乐理感知"分层。  
  我们把这套逻辑独立成 `perceptual_filter.py`，在 `split_arrangement.py` 中对 `other` 轨做精细分层，  
  并对 `transcribe_stems.py` 的贝斯单声部做去噪。它是纯 numpy 逻辑，**无需 torch/demucs**，可在任意环境运行。

### 输入 / 输出

- 输入：音符列表 `[{start, end, pitch, velocity}, ...]`（转录结果）。

- `clean_notes(notes, ...)` → 去噪后的音符（用于 vocal/bass 单声部）。

- `separate_melody_accompaniment(notes, melody_split=True)` → `{'melody', 'bass', 'accompaniment'}` 三层。

### 核心步骤

1. **全局去噪 `clean_notes`**：

  <BulletedList id="NVFE81TCUf6XMn2GCYQGe3">
    剔除超短音（`<0.05s`）与过低力度音（噪声）；
  </BulletedList>

  <BulletedList id="lgBeN7qe4k4YKeaC896DwS">
    `merge_short_gaps`：粘合相距 ≤0.08s、音高差 ≤2 半音的碎音；
  </BulletedList>

  <BulletedList id="RzyICYNFpfhwkN4HpeD14u">
    `harmonic_rejection`：**倍频抑制（保守版）**——仅当上层音明显弱于基频（`velocity ≤ 0.7×` 基频）、且半音差 ∈ {12,19}（1~1.5 八度内的强泛音）、且基频不在低音区时，才把弱音当泛音剔除。**不删等强八度（和弦音）**，也不让低音作为基频去吸收和弦，避免误毁和声。
  </BulletedList>

  <BulletedList id="dcSnZ6EBnRKYGMqGSJfFBx">
    `outlier_rejection`：**离群跳音剔除**——局部 ±0.5s 窗中位数偏差 > 阈值（长音放宽）则删除。
  </BulletedList>

1. **音域路由**：`MELODY_RANGE=(60,96)` 高音区候选旋律，`BASS_RANGE=(24,55)` 低音区候选骨架。

2. **旋律提取 `_extract_melody_line`**：每 0.12s 时间窗内取"最突出"音（`score = 重叠时长 × 高音加分 × 力度/127`），平滑去跳变。

3. **低音提取 `_extract_bass_line`**：每 0.15s 窗取最低、最稳音。

4. **和声过滤 `_filter_mid_notes`**：中音区仅保留与最近旋律音构成**协和音程**（{0,3,4,5,7,8,9} 模 12）的和声；极不协和（{1,6,11}）需足够强才留，其余视为杂音丢弃。

### 与我们旧版 `split_arrangement.py` 的对比

| 维度 | 旧版（取最高音） | 新版（perceptual_filter） |
| --- | --- | --- |
| 主旋律判定 | 重叠音群内取最高音 | 时间窗最突出音 + 高音加分评分 |
| 泛音处理 | 无，易把基频+八度都当旋律 | 倍频抑制去泛音 |
| 和声选择 | 群内剩余音全保留 | 仅保留与旋律协和的和声 |
| 噪声 | 无专门去除 | 离群跳音/碎音/低幅统一剔除 |
| 依赖 | pretty_midi | numpy（更轻） |
