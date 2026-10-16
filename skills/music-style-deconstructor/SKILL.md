---
name: music-style-deconstructor
description: 将给定 MP3 拆解为编曲元素多轨 MIDI 并分析音乐风格 / 作者风格指纹。当用户提供歌曲音频、希望分离编曲层(主旋律/和声/贝斯/鼓/人声)、获取乐器类型建议、用 Synthesizer V 制作人声、或提炼某作者风格指纹时使用。触发词:拆曲、扒带、分轨、多轨MIDI、风格分析、编曲参考、配器类型、风格指纹、music style。
---

# 音乐风格拆析与多轨 MIDI 生成

## Overview

本技能把一首（或同一作者的若干首）MP3，自动拆成**编曲元素分轨**，输出可直接导入 **FL Studio** 的多轨 MIDI，并产出：风格拆析报告、每轨**乐器类型**标注、以及供 **Synthesizer V** 使用的人声参考包（音高线 + 歌词占位 + 声库类型推荐）。歌词与演唱由你自行完成。

支持两种模式：

- **单首拆析模式**：一首歌 → 多轨 MIDI + 风格报告 + 乐器类型 + 人声包。

- **作者风格指纹模式**：多首同作者参考曲 → 提炼 `AUTHOR_FINGERPRINT.json`，后续单首拆析回查对照，标注「符合 / 偏离作者惯例」，也可基于指纹生成新的分轨 MIDI 草稿。

## 工作模式决策树

```
用户提供音频？
├─ 单首歌曲            → 单首拆析模式（见下「工作流」）
└─ 同一作者多首参考曲  → 作者风格指纹模式
   ├─ 只想要指纹        → 仅运行 build_fingerprint.py
   └─ 想要指纹 + 拆新曲 → 先 build_fingerprint.py，再对目标曲跑单首流程并传入指纹
   └─ 想要原创编曲草稿  → build_fingerprint.py 后运行 compose_from_fingerprint.py
```

## 环境依赖

依赖已内置为 skill 的一部分：优先使用仓库内 `.skill-deps` 运行环境，首次使用请执行：

```bash
python scripts/install_skill_deps.py            # 核心依赖：librosa/scipy/numpy/soundfile/pretty_midi
python scripts/install_skill_deps.py --full     # 额外安装 demucs/basic-pitch/torchcrepe（体积较大）
```

也可手动快速安装（Windows / macOS）：

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
# 虚拟歌姬歌曲可追加 --virtual-singer 写入特化特征

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

# 6.5 段落摘要 + 音频叙事（供模型快速阅读）
python scripts/section_summary.py  features.json  \
       --midi midi_raw/ --midi midi/  --out SECTION_SUMMARY.md

# 6.6 音色分析（全曲 + 各 stem 的音色标签/MFCC/频谱对比）
python scripts/timbre_analysis.py  features.json  --out TIMBRE_REPORT.md

# 7. 人声参考包（SV 专用）
python scripts/vocal_track_sv.py  stems/vocals.wav  --out vocal/ --virtual-singer

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

## 基于指纹生成风格化 MIDI（原创分轨）

当用户想按某作者的风格写一首新编曲，而不是继续扒带时，运行：

```bash
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --out output/compose/ --name new_song --bars 32 --seed 42
```

输出分轨：

- `melody.mid`：主旋律草稿，按段落调整音区与密度
- `pad.mid`：和弦铺底，逐小节轮转指纹中的和弦进行
- `bass.mid`：根音贝斯线，前奏/尾奏自动稀疏
- `drums.mid`：鼓组草稿，按前奏/尾奏降密度
- `notes.json`：与分轨一一对应的音符元数据
- `COMPOSE_REPORT.md`：调性、BPM、和弦进行、段落配比摘要

该模式不读取音频，不保证还原某首歌；它是把作者指纹翻译成可编辑的原创 MIDI 草稿，适合先搭结构再交由人工完善。

### Agent 提示词规范化流程（必须步骤）

接入 agent 后，用户自然语言不能直接当作最终参数使用，agent 需要先把它规范成标准 prompt，再进入生成流程：

1. **收集自然语言**：读取用户的风格描述，例如“更明亮、鼓更密、副歌更高、前奏安静”。

2. **规范成标准 prompt**：按 `references/style_prompt_guide.md` 的模板整理为结构化标准 prompt，包含风格方向、速度、配器强调、段落处理；不保留互相矛盾的模糊词。

3. **解析可计算参数**：agent 把标准 prompt 映射为 `params.json` 参数，或确认 `--prompt` 的关键词能表达清楚。

4. **传入生成流程**：把标准 prompt 写入 `STYLE_PROMPT.md` 后通过 `--prompt-file` 输入，或直接用 `--prompt` / `--params` 输入：

```bash
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --prompt-file STYLE_PROMPT.md \
    --out output/compose/ --name new_song --bars 32 --seed 42
```

5. **回读并迭代**：脚本会输出 `COMPOSE_REPORT.md` 和标准 prompt 快照 `STYLE_PROMPT.md`。agent 据此向用户说明生效的 BPM、密度、明亮度、和弦进行，再按用户的下一轮自然语言继续循环。

如果 agent 已把提示词解析成明确参数，也可以直接传 `--params`：

```bash
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --params params.json --out output/compose/
```

支持参数包括 `bpm / bpm_shift / bars / key / scale / density / brightness / pad_density / melody_density / bass_density / drums / progression / section_ratio / seed`。完整提示词模板和映射见 `references/style_prompt_guide.md`。

## 输出目录结构

```
output/
├── <song>_multitrack.mid   # 多轨 MIDI（每轨一个通道，见 midi_mapping.md）
├── README_导入FLStudio.md  # 导入步骤 + 每轨乐器类型
├── STYLE_REPORT.md         # 风格拆析
├── INSTRUMENT_MAP.md       # 每轨乐器类型建议
    ├── notes.json              # 每轨音符元数据（起止时间/音高/力度/置信度）
    ├── SECTION_SUMMARY.md      # 每段落和弦/鼓型/织体摘要 + stem 频谱
    ├── AUDIO_NARRATIVE.md      # 简短音频叙事，给模型快速阅读
    ├── TIMBRE_REPORT.md/json   # 音色分析：全曲 + 分轨音色标签/MFCC/频谱对比
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

- `virtual_singer_spec.md` —— 虚拟歌姬歌曲特化：合成人声规律、CLI 开关、样本说明。

- `style_prompt_guide.md` —— agent 接入后，把用户提示词翻译成风格参数的映射表。

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
| `timbre_analysis.py` | 音色分析报告：全曲 + 分轨音色标签/MFCC/频谱对比 |
| `section_summary.py` | 每段落和弦/鼓型/织体摘要 + Stem 频谱 + 音频叙事 |
| `notes_json.py` / `notes_io.py` | 生成/读写每轨 `notes.json`（起止/音高/力度/置信度） |
| `vocal_track_sv.py` | SV 人声参考包（音高线 + 歌词占位 + 声库类型） |
| `build_fingerprint.py` | 多首聚合 → AUTHOR_FINGERPRINT.json |
| `compose_from_fingerprint.py` | 指纹 → 原创 melody/pad/bass/drums 多轨 MIDI；支持 `--prompt` 或 `--params` 微调风格参数 |
| `package_output.py` | 合并多轨 MIDI + FL Studio 导入说明 |
| `install_skill_deps.py` / `skill_runtime.py` | 内置依赖安装与运行时路径 |

## 局限与置信度（务必告知用户）

- 自动转录对**密集织体、失真吉他、重叠人声**误差明显，所有 MIDI **仅供编曲参考，需人工修音**。

- Demucs 分离非无损：`drums` / `bass` 较准，`other` 混叠较多，主旋律提取置信度要标注。

- 歌词与演唱是用户的保留工作，本技能不产出歌词内容。

- 重依赖首次运行需联网下载模型（数 GB）。

- 人声 MIDI 仅为音高参考，实际演唱的咬字、气声、滑音需在 SV 中手动处理。
