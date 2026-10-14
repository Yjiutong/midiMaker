---
name: music-style-deconstructor
description: 将给定 MP3 拆解为编曲元素多轨 MIDI 并分析音乐风格 / 作者风格指纹。当用户提供歌曲音频、希望分离编曲层(主旋律/和声/贝斯/鼓/人声)、获取乐器类型建议、用 Synthesizer V 制作人声、或提炼某作者风格指纹时使用。触发词:拆曲、扒带、分轨、多轨MIDI、风格分析、编曲参考、配器类型、风格指纹、music style。
---

# 音乐风格拆析与多轨 MIDI 生成

## Overview

本技能把一首（或同一作者的若干首）MP3，自动拆成**编曲元素分轨**，输出可直接导入 **FL Studio** 的多轨 MIDI，并产出：风格拆析报告、每轨**乐器类型**标注、以及供 **Synthesizer V** 使用的人声参考包（音高线 + 歌词占位 + 声库类型推荐）。歌词与演唱由你自行完成。

支持两种模式：

- **单首拆析模式**：一首歌 → 多轨 MIDI + 风格报告 + 乐器类型 + 人声包。

- **作者风格指纹模式**：多首同作者参考曲 → 提炼 `AUTHOR_FINGERPRINT.json`，后续单首拆析回查对照，标注「符合 / 偏离作者惯例」。

## 工作模式决策树

```
用户提供音频？
├─ 单首歌曲            → 单首拆析模式（见下「工作流」）
└─ 同一作者多首参考曲  → 作者风格指纹模式
   ├─ 只想要指纹        → 仅运行 build_fingerprint.py
   └─ 想要指纹 + 拆新曲 → 先 build_fingerprint.py，再对目标曲跑单首流程并传入指纹
```

## 环境依赖

详见仓库根目录 `README.md`。快速安装（Windows / macOS）：

```bash
pip install demucs basic-pitch librosa scipy pretty_midi numpy
```

- `demucs`：stem 分离（首次运行自动下载 htdemucs 模型，约数百 MB～1GB）。**失败时自动退回 librosa HPSS 兜底分离**。

- `librosa` + `scipy` + `numpy`：CQT 频谱、特征提取、**默认 CQT 转录引擎**、HPSS 兜底、感知滤波（纯信号处理，无需下载模型）。

- `basic-pitch`（可选）：高精度神经网络转录备选引擎（`--engine basicpitch`，首次自动下载 ICASSP_2022 模型）。

- `torchcrepe`（可选）：人声音高线 CREPE 引擎；不装则自动退回 `librosa.pyin` 单音提取。

- `pretty_midi`：读写 MIDI、分配通道。

> 转录算法**首选参考 [Yjiutong/AutoTranscriber-WebUI](https://github.com/Yjiutong/AutoTranscriber-WebUI)**（AutoTranscriber 的 WebUI 适配）：  
>     Demucs 音源分离 + CQT 多音高估计 + 局部归一化起音检测 + 振幅衰减式音符追踪 + CREPE 人声音高线。  
>     详见 `references/transcription_algorithms.md`（同时收录 Basic Pitch 与 gityag 作为备选/教学）。

## 工作流（单首拆析模式，脚本调用顺序）

```bash
# 1. 分 stem（vocals / drums / bass / other）— Demucs 信号域分离，HPSS 兜底
python scripts/separate_stems.py  input.mp3  --out stems/
# 仅分人声/伴奏两轨:  python scripts/separate_stems.py input.mp3 --two-stems vocals

# 2. 提取全局特征 → features.json
python scripts/extract_features.py  input.mp3  --stems stems/  --out features.json

# 3. 各 stem 转 MIDI + 鼓分类 → midi_raw/（默认 AutoTranscriber 风格 CQT 引擎）
python scripts/transcribe_stems.py  stems/  --out midi_raw/ --engine cqt
# 若需更高精度可改用: --engine basicpitch

# 4. other → 主旋律 / 和声Pad（符号域乐理感知分层，perceptual_filter）
python scripts/split_arrangement.py  midi_raw/other.mid  --out midi/

# 5. 乐器【类型】标注 → INSTRUMENT_MAP.md
python scripts/instrument_map.py  features.json  midi/  --out INSTRUMENT_MAP.md

# 6. 风格拆析报告 → STYLE_REPORT.md（结合指纹可选）
python scripts/style_report.py  features.json  midi/  --out STYLE_REPORT.md \
       [--fingerprint AUTHOR_FINGERPRINT.json]

# 7. 人声参考包（SV 专用）
python scripts/vocal_track_sv.py  stems/vocals.wav  --out vocal/

# 8. 合并多轨 MIDI + FL Studio 导入说明
python scripts/package_output.py  midi/  vocal/vocal_melody.mid  \
       --map INSTRUMENT_MAP.md  --out output/
```

## 作者风格指纹模式

```bash
# 对每首参考曲先跑 1–4 步，得到各自的 features.json + midi/
# 然后聚合：
python scripts/build_fingerprint.py  features1.json features2.json ... \
       --out AUTHOR_FINGERPRINT.json
```

指纹包含：常用调 / 典型和弦进行 / BPM 区间 / 固定配器搭配 / 段落比例 / 音色亮度区间。  
  单首拆析时把 `--fingerprint` 传给 `style_report.py`，报告会标注该曲「符合 / 偏离」作者惯例。

## 输出目录结构

```
output/
├── <song>_multitrack.mid   # 多轨 MIDI（每轨一个通道，见 midi_mapping.md）
├── README_导入FLStudio.md  # 导入步骤 + 每轨乐器类型
├── STYLE_REPORT.md         # 风格拆析
├── INSTRUMENT_MAP.md       # 每轨乐器类型建议
└── vocal/                  # 人声参考包
    ├── vocal_melody.mid    # 主旋律音高线（参考唱线）
    ├── lyrics_placeholder.txt  # 按乐句切分的歌词占位
    └── sv_recommendation.md    # SV 声库类型推荐 + 导入流程
```

## FL Studio 导入指引（要点，详见输出 README）

1. 把 `output/<song>_multitrack.mid` 拖入 FL Studio 工程。

2. FL Studio 会按 MIDI 通道生成对应音轨（通道分配见 `references/midi_mapping.md`）。

3. 每轨挂载你选的乐器插件，类型参考 `INSTRUMENT_MAP.md`（如「合成主音 Lead」「暖色 Pad」「电贝斯」「原声鼓组」）。

4. 鼓轨用 FPC / 自带鼓采样映射 GM 鼓键即可。

5. 人声：在 Synthesizer V 中导入 `vocal/vocal_melody.mid` 作参考唱线 → 对齐 → 填词 → 选声库 → 渲染，再回到 FL Studio 作为音频轨。

## 人声轨（Synthesizer V 专用）

- 只给**音高轮廓**（pitch contour）与**节奏格子**，**不识别也不猜测歌词**。

- 歌词占位按乐句切分，每个音符标注对应音节位置（`[歌词]` 占位）。

- SV 声库只推荐**类型**（日系/中系/英系、男/女、音域），不绑定具体声库商品。

- 详见 `references/sv_voicebank.md` 与 `vocal/sv_recommendation.md`。

## references 索引

- `analysis_framework.md` —— 风格拆析的维度、方法与 LLM 报告框架。

- `instrument_types.md` —— 按 genre 索引的**乐器类型**知识库（只给类型，不给具体 VST）。

- `sv_voicebank.md` —— Synthesizer V 声库**类型**推荐与导入指南。

- `fingerprint_framework.md` —— 作者风格指纹的维度、聚合方法与回查逻辑。

- `midi_mapping.md` —— GM 鼓键映射 + MIDI 通道分配规范。

- `transcription_algorithms.md` —— 转录算法参考（**AutoTranscriber** CQT 管线 / 人声分离两层架构 / 符号域分层 / Basic Pitch / gityag）。

## 脚本清单（scripts/）

| 脚本 | 作用 |
| --- | --- |
| `separate_stems.py` | **信号域人声/编曲分离**：Demucs（HPSS 兜底）+ 非 WAV 转码 + 跨平台调用 |
| `extract_features.py` | librosa 提 BPM/调性/和弦/段落 |
| `transcribe_stems.py` | CQT 转录 + 鼓分类 + CREPE 人声音高线（含贝斯符号域去噪） |
| `perceptual_filter.py` | **符号域旋律-伴奏分层**（移植 AutoTranscriber）：去噪 + 三层分离，纯 numpy |
| `split_arrangement.py` | 调用 perceptual_filter 把 other 拆 主旋律/和声Pad |
| `instrument_map.py` | 按 genre 输出**乐器类型**标注 |
| `style_report.py` | LLM 风格拆析报告（回查指纹） |
| `vocal_track_sv.py` | SV 人声参考包（音高线 + 歌词占位 + 声库类型） |
| `build_fingerprint.py` | 多首聚合 → AUTHOR_FINGERPRINT.json |
| `package_output.py` | 合并多轨 MIDI + FL Studio 导入说明 |

## 局限与置信度（务必告知用户）

- 自动转录对**密集织体、失真吉他、重叠人声**误差明显，所有 MIDI **仅供编曲参考，需人工修音**。

- Demucs 分离非无损：`drums` / `bass` 较准，`other` 混叠较多，主旋律提取置信度要标注。

- 歌词与演唱是用户的保留工作，本技能不产出歌词内容。

- 重依赖首次运行需联网下载模型（数 GB）。

- 人声 MIDI 仅为音高参考，实际演唱的咬字、气声、滑音需在 SV 中手动处理。
