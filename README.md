# music-style-deconstructor

把一首（或同一作者的若干首）MP3 自动拆成**编曲元素分轨**，输出可直接导入 **FL Studio** 的  
  多轨 MIDI，并产出风格拆析报告、每轨**乐器类型**标注、以及供 **Synthesizer V** 使用的人声参考包  
  （音高线 + 歌词占位 + 声库类型推荐）。歌词与演唱由你自行完成。

> 原方案设计见 [music-style-deconstructor_design.md](./references/music-style-deconstructor_design.md)。

## 一、目录结构

```
music-style-deconstructor/
├── SKILL.md                      # skill 主文档（触发词、工作流、FL Studio 导入）
├── README.md                     # 本文件
├── scripts/                      # 分析脚本 + 内置依赖/运行时辅助
│   ├── separate_stems.py         # 信号域人声/编曲分离（Demucs + HPSS 兜底 + 非 WAV 转码）
│   ├── extract_features.py       # librosa 提特征
│   ├── transcribe_stems.py       # CQT 转录 + 鼓分类 + CREPE 人声音高线
│   ├── perceptual_filter.py      # 符号域旋律-伴奏分层（去噪 + 三层分离，纯 numpy）
│   ├── split_arrangement.py      # other → 主旋律 / 和声Pad（调用 perceptual_filter）
│   ├── style_report.py           # 风格报告（数值版）
│   ├── timbre_analysis.py        # 音色分析报告（全曲 + 分轨）
│   ├── instrument_map.py         # 乐器【类型】标注
│   ├── vocal_track_sv.py         # 人声参考包（SV）
│   ├── build_fingerprint.py      # 作者风格指纹聚合
│   ├── package_output.py         # 合并多轨 MIDI + 导入说明
│   ├── notes_io.py / notes_json.py # 每轨 notes.json（起止时间/音高/力度/置信度）
│   ├── section_summary.py        # 段落和弦/鼓型/织体摘要 + 音频叙事
│   ├── install_skill_deps.py     # 内置依赖安装器
│   └── skill_runtime.py          # 优先使用 .skill-deps 运行环境
├── references/                   # 知识库
│   ├── analysis_framework.md     # 风格拆析维度与方法
│   ├── instrument_types.md       # 乐器【类型】库（按 genre）
│   ├── sv_voicebank.md           # SV 声库【类型】推荐与导入
│   ├── fingerprint_framework.md  # 作者风格指纹维度
│   ├── midi_mapping.md           # GM 鼓键 + 通道规范
│   └── transcription_algorithms.md # 转录算法参考（AutoTranscriber / 人声分离两层 / Basic Pitch / gityag）
└── assets/
    └── lyric_template.txt        # 歌词占位模板
```

## 二、环境依赖与安装

需要 Python 3.10+（Basic Pitch 在 Mac M1 上仅支持 3.10）。在 Windows / macOS 上：

```bash
pip install demucs basic-pitch librosa scipy pretty_midi numpy
```

skill 已内置依赖安装器，推荐优先使用：

```bash
python scripts/install_skill_deps.py            # 安装核心依赖到 .skill-deps
python scripts/install_skill_deps.py --full     # 额外安装 demucs/basic-pitch/torchcrepe
```

- **demucs**：stem 分离，首次运行自动下载 `htdemucs` 模型（约数百 MB）。失败时自动退回 `librosa` HPSS 兜底分离。

- **basic-pitch**（可选）：音频→MIDI 转录，首次自动下载 ICASSP_2022 模型；不装则用默认 CQT 引擎。

- **librosa** + **scipy** + **numpy**：CQT 频谱、特征提取、默认 CQT 转录引擎、HPSS 兜底、感知滤波（纯信号处理，无需下载模型）。

- **pretty_midi**：读写 MIDI、分配通道。

- **torchcrepe**（可选）：人声音高线 CREPE 引擎；不装则自动退回 `librosa.pyin` 单音提取。

> 首次运行需联网下载模型（数 GB 级，请预留空间）。若离线，请提前在能联网环境预置模型缓存。

## 三、快速开始（单首拆析模式）

```bash
# 1. 分 stem（Demucs 信号域分离，HPSS 兜底；非 WAV 自动转码）
python scripts/separate_stems.py input.mp3 --out stems/
# 仅分人声/伴奏两轨:  python scripts/separate_stems.py input.mp3 --two-stems vocals

# 2. 提特征
python scripts/extract_features.py input.mp3 --stems stems/ --out features.json

# 3. 各 stem 转 MIDI + 鼓分类
python scripts/transcribe_stems.py stems/ --out midi_raw/

# 4. other → 主旋律 / 和声Pad
python scripts/split_arrangement.py midi_raw/other.mid --out midi/

# 5. 乐器【类型】标注（--genre 可选 pop/rnb/hiphop/edm/rock/lofi/jpoc/cpop）
python scripts/instrument_map.py features.json midi/ --out INSTRUMENT_MAP.md --genre pop

# 6. 风格报告
python scripts/style_report.py features.json --out STYLE_REPORT.md --drums midi_raw/drums.mid

# 6.5 段落摘要 + 音频叙事（建议同时传入 midi_raw/ 与 midi/）
python scripts/section_summary.py features.json \
    --midi midi_raw/ --midi midi/ --out SECTION_SUMMARY.md

# 6.6 音色分析（全曲 + 各 stem 的亮度/平坦度/MFCC/音色标签）
python scripts/timbre_analysis.py features.json --out TIMBRE_REPORT.md

# 7. 人声参考包（SV）
python scripts/vocal_track_sv.py stems/vocals.wav --out vocal/ --style cn

# 8. 合并多轨 MIDI + 导入说明
python scripts/package_output.py midi/ vocal/vocal_melody.mid \
    --map INSTRUMENT_MAP.md --out output/ --name mysong
```

完成后，`output/` 含 `mysong_multitrack.mid` 与 `README_导入FLStudio.md`，  
  `notes.json`（每轨音符的起止时间/音高/力度/置信度），`SECTION_SUMMARY.md` 与 `AUDIO_NARRATIVE.md`（段落摘要和音频叙事），`TIMBRE_REPORT.md`（音色分析），`vocal/` 含人声参考包。

## 四、作者风格指纹模式（增强）

```bash
# 对每首参考曲先跑 1–4 步，得到各自的 features.json + midi/
python scripts/build_fingerprint.py ref1_features.json ref2_features.json ref3_features.json \
    --out AUTHOR_FINGERPRINT.json

# 拆新曲时回查指纹（报告会标注符合/偏离作者惯例）
python scripts/style_report.py features.json --out STYLE_REPORT.md \
    --drums midi_raw/drums.mid --fingerprint AUTHOR_FINGERPRINT.json
```

## 五、FL Studio 导入

1. 把 `output/mysong_multitrack.mid` 拖入 FL Studio 工程，按 MIDI 通道生成音轨。

2. 每轨挂载乐器插件，类型参考 `INSTRUMENT_MAP.md`。

3. 鼓轨用 FPC / 自带鼓采样映射 GM 鼓键（见 `references/midi_mapping.md`）。

4. 人声：在 Synthesizer V 导入 `vocal/vocal_melody.mid` 作参考唱线 → 填词 → 选声库 → 渲染 WAV，  
  回 FL Studio 作音频轨（MIDI 参考轨静音/删除）。

## 六、局限（务必知悉）

- 自动转录对**密集织体、失真吉他、重叠人声**误差明显，所有 MIDI **仅供编曲参考，需人工修音**。

- Demucs 分离非无损：`drums` / `bass` 较准，`other` 混叠较多，主旋律置信度需人工判断。

- 歌词与演唱是你的保留工作，本技能不产出歌词内容。

- 人声音高线不含咬字、气声、颤音细节，仅锚定音高与节奏骨架。

## 七、转录算法参考

本项目的转录引擎与算法调研见 [references/transcription_algorithms.md](./references/transcription_algorithms.md)，  
  参考了 Spotify **Basic Pitch**（onset/frame/contour 三头神经网络 + 后处理）与  
  **gityag/Automated-Music-Transcription**（CQT 特征 + 时间桶解码）。
