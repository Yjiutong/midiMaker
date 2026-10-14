# MIDI 映射规范（GM 鼓键 + 通道分配）

本文件规范 `transcribe_stems.py`（鼓分类）与 `package_output.py`（合并多轨）使用的 MIDI 映射，  
  保证输出的 `.mid` 在 FL Studio 等任意 DAW 中按预期解析。

## 一、鼓组 GM 键位映射（Drums 轨，通道 10）

鼓组使用 **General MIDI 标准打击乐键位**（MIDI 通道 10，即程序内通道索引 9）。  
  `transcribe_stems.py` 通过 onset + 频段能量把鼓点分类映射到下列键：

| MIDI 键 | 名称 | 分类 | 频段特征 |
| --- | --- | --- | --- |
| 35 | Acoustic Bass Drum | 底鼓 | 低频能量突增 |
| 36 | Bass Drum 1 (Kick) | 底鼓 | 低频能量突增 |
| 37 | Side Stick | 边击 | 中高频瞬态 |
| 38 | Acoustic Snare | 军鼓 | 中频瞬态 |
| 39 | Hand Clap | 拍手 | 中频瞬态群 |
| 40 | Electric Snare | 军鼓 | 中频瞬态 |
| 41 | Low Floor Tom | 桶鼓 | 中低频瞬态 |
| 42 | Closed Hi-Hat | 闭镲 | 高频短瞬态 |
| 44 | Pedal Hi-Hat | 踏镲 | 低频短瞬态 |
| 45 | Low Tom | 桶鼓 | 中低频瞬态 |
| 46 | Open Hi-Hat | 开镲 | 高频长瞬态 |
| 47 | Low-Mid Tom | 桶鼓 | 中频瞬态 |
| 48 | Hi-Mid Tom | 桶鼓 | 中高频瞬态 |
| 49 | Crash Cymbal 1 | 碎音镲 | 高频长衰减 |
| 51 | Ride Cymbal 1 | 叮叮镲 | 高频中衰减 |
| 52 | Chinese Cymbal | 中国镲 | 高频长衰减 |
| 53 | Ride Bell | 叮叮钟 | 高频瞬态 |
| 54 | Tambourine | 铃鼓 | 高频群瞬态 |
| 55 | Splash Cymbal | 水镲 | 高频短衰减 |
| 56 | Cowbell | 牛铃 | 中高频瞬态 |
| 57 | Crash Cymbal 2 | 碎音镲 | 高频长衰减 |
| 59 | Ride Cymbal 2 | 叮叮镲 | 高频中衰减 |

> 分类逻辑：用 `librosa` 对 `drums` stem 分频段计算 onset 强度谱，按频段能量占比判断 kick / snare / hat / cymbal / tom，再映射到上表键位。具体实现见 `transcribe_stems.py` 的 `classify_drum_hits`。

## 二、编曲元素轨 → MIDI 通道分配

合并多轨时，`package_output.py` 按以下通道分配（1-based 显示 / 0-based 程序索引）：

| 轨 | 名称 | MIDI 通道 | 程序索引 | 说明 |
| --- | --- | --- | --- | --- |
| 主旋律 | Melody Lead | 1 | 0 | Basic Pitch 提取的主奏音线 |
| 和声·Pad | Chords / Pad | 2 | 1 | 中低音区持续音 / 和弦 |
| 贝斯 | Bass | 3 | 2 | 低音区音符 |
| （预留） | — | 4 | 3 | 备用 |
| 人声 | Vocal (ref) | 5 | 4 | SV 参考唱线，导入后替换 |
| （预留） | — | 6–9 | 5–8 | 备用 |
| 鼓组 | Drums | 10 | 9 | GM 打击乐键位 |

> 注意：GM 规定**通道 10（索引 9）为打击乐专用**。鼓轨务必放在通道 10，否则 FL Studio 会把它当旋律乐器解释。

## 三、音符属性映射

- **音高**：频率索引 + `MIDI_OFFSET(21)`；鼓用上表固定键。

- **力度（Velocity）**：旋律/贝斯/和声 = `round(amplitude × 127)`，范围裁剪到 [1, 127]；鼓 = 按频段能量归一化到 [60, 120]。

- **时值**：起音 onset 时刻 + 尾音（frame 阈值 + 能量容忍定界），见 `transcription_algorithms.md`。

- **弯音（Pitch Bend）**：人声/主旋律保留 Basic Pitch 的 contour 弯音（1/3 半音精度），增强滑音真实感。

- **速度（Tempo）**：写入 MIDI 头，默认 120 BPM 占位；实际 BPM 来自 `extract_features.py` 的 `beat_track` 结果，由 `package_output.py` 覆盖。
