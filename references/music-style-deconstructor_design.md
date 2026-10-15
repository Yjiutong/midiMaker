# Skill 技术方案：music-style-deconstructor（音乐风格拆析 + 多轨 MIDI 生成）

> 状态：**方案定稿，准备实现**  
>     已确认决策：宿主 = **FL Studio**；乐器标注 = **只给类型**（不列具体 VST/型号）；支持 **作者风格指纹** 增强模式。

## 一、Skill 要解决什么

给定一首（或同一作者的若干首）MP3，自动完成：

1. **风格拆析**：分析该曲目 / 该作者的编曲手法、和声语言、节奏律动、配器层次、音色取向、曲式结构。

2. **多轨分离**：把混音拆成编曲元素分轨——`主旋律 / 和声·Pad / 贝斯 / 鼓组 / 人声`。

3. **多轨 MIDI 生成**：把各音轨转录 / 映射为标准多轨 MIDI（每轨一个 MIDI 通道），可直接导入 **FL Studio**。

4. **乐器标注（只给类型）**：给出每一轨的**乐器类型**（如"合成主音 Lead""暖色 Pad""电贝斯""原声鼓组"），不指定具体 VST/型号。

5. **人声轨（SV 专用）**：只产出**主旋律音高线 MIDI + 歌词占位文本 + SV 声库类型推荐**，歌词与演唱由你用 Synthesizer V 自行完成。

6. **作者风格指纹（增强）**：输入同一作者多首参考曲，提炼该作者的"风格指纹"（常用调、典型进行、BPM 区间、固定配器搭配、段落比例），作为后续单首拆析的对照基准。

最终你拿到：一个多轨 `.mid` + 工程导入说明 + 风格报告 + 乐器类型标注 + 人声参考包，导入 FL Studio 和 SV 继续制作。

## 二、整体架构（三层 + 指纹聚合）

```
单首模式:
输入 MP3 ──► [1. 音频分析层] ──► features.json
                │  (demucs 分 stem + librosa 提特征)
                ▼
            [2. 转录 / 映射层] ──► 各 stem 的 MIDI + notes.json
                │
                ▼
            [3. 风格推理 + 输出层] ──► STYLE_REPORT + 乐器类型 + 多轨.mid + 人声包

指纹模式(增强):
多首参考 MP3 ──► 各自走 [1][2] ──► 聚合 stats ──► AUTHOR_FINGERPRINT.json
                                                              │
单首拆析时 ◄────────────── 作为对照基准(标注"符合/偏离作者惯例") ◄┘
```

设计原则：**重计算（分离/转录）交给 Python 离线批处理；"理解"部分（风格语言、乐器类型、歌词结构）交给 LLM + references 知识库。**

## 三、技术栈与依赖

| 用途 | 工具 | 备注 |
| --- | --- | --- |
| Stem 分离 | `demucs` (htdemucs) | 分 vocals/drums/bass/other；可选 `htdemucs_6s` 细分 guitar/piano |
| 旋律/音符转录 | `AutoTranscriber` 风格 CQT 管线（librosa，默认）/ `basic-pitch` (Spotify，备选) | 输出 notes → MIDI |
| 特征提取 | `librosa` + `soundfile` | BPM、调性、和弦、onset、频谱包络、结构分段 |
| 鼓点检测 | `madmom` 或 demucs drum | kick/snare/hat 分类 → GM 鼓键 |
| MIDI 读写 | `pretty_midi` | 生成、合并、通道分配 |
| 后端 | `torch` | demucs/basic-pitch 依赖，首次需下模型 |

> 本地 Windows/macOS：`pip install demucs basic-pitch librosa pretty_midi`。首次自动下载模型（数 GB）。FL Studio 直接支持导入标准 `.mid`，无需特殊模板。

## 四、编曲元素分轨策略

| 目标轨 | 来源 | 处理方式 |
| --- | --- | --- |
| **主旋律 (Melody Lead)** | `other` | basic-pitch 后取能量最高主奏音线；`htdemucs_6s` 的 piano/guitar 辅助 |
| **和声·Pad (Chords/Pad)** | `other` | 中低音区持续音/和弦音聚类成和弦事件，去主旋律残留 |
| **贝斯 (Bass)** | `bass` | basic-pitch 转低音，修正八度 |
| **鼓组 (Drums)** | `drums` | onset + 频段能量分类 → GM 鼓键(35-59) |
| **人声 (Vocal)** | `vocals` | 只提音高轮廓 + 节奏格子，不识别歌词 |

> `other` 混叠严重（失真吉他、密集织体）时，保留"退回标准 4 轨"降级路径并标注置信度。

## 五、脚本模块（确认后实现）

```
music-style-deconstructor/
├── SKILL.md
├── scripts/
│   ├── separate_stems.py      # demucs 分 stem
│   ├── extract_features.py    # librosa 全局特征 → features.json
│   ├── transcribe_stems.py    # CQT 转录(AutoTranscriber 风格) + 鼓分类 + CREPE/pyin 人声音高线 → 各 stem MIDI
│   ├── split_arrangement.py   # other → 主旋律 / 和声Pad
│   ├── style_report.py        # LLM 生成风格拆析报告
│   ├── instrument_map.py      # 乐器【类型】推荐
│   ├── vocal_track_sv.py      # 人声音高线 + 歌词占位 + SV 声库类型推荐
│   ├── build_fingerprint.py   # 【新增】多首聚合 → AUTHOR_FINGERPRINT.json
│   └── package_output.py      # 合并多轨 MIDI + FL Studio 导入说明
├── references/
│   ├── analysis_framework.md  # 风格拆析维度与方法
│   ├── instrument_types.md    # 乐器【类型】知识库(按 genre 索引,只类型)
│   ├── sv_voicebank.md        # Synthesizer V 声库【类型】推荐与导入指南
│   ├── fingerprint_framework.md # 【新增】作者风格指纹维度与聚合方法
│   └── midi_mapping.md        # GM 鼓键映射 + 通道规范
└── assets/
    └── lyric_template.txt     # 歌词占位模板
```

> 不再提供 `.flp` 工程模板（二进制无法文本生成）。FL Studio 导入指引写在 `package_output.py` 生成的 README 中：拖入 `.mid` → FL Studio 按通道生成轨道 → 每轨挂载你选的乐器插件（类型见报告）。

## 六、SKILL.md 草案（frontmatter + 骨架）

```yaml
---
name: music-style-deconstructor
description: 将给定 MP3 拆解为编曲元素多轨 MIDI 并分析音乐风格/作者风格指纹。当用户提供歌曲音频、希望分离编曲层(主旋律/和声/贝斯/鼓/人声)、获取乐器类型建议、用 Synthesizer V 制作人声、或提炼某作者风格指纹时使用。触发词:拆曲、扒带、分轨、多轨MIDI、风格分析、编曲参考、配器类型、风格指纹。
---
```

正文：单首 vs 指纹模式决策树、脚本调用顺序、FL Studio 导入说明、人声轨 SV 处理、references 索引、降级与置信度提示。

## 七、关键方法论

### 1. 风格拆析维度（analysis_framework.md）

曲式结构 / 调性与和声 / 节奏律动 / 配器层次 / 音色取向 / 动态与混音。

### 2. 乐器标注——只给类型（instrument_types.md）

依据音域、奏法、genre、作者惯用配置，输出**乐器类型**（如"合成主音 Lead""暖色 Pad""电贝斯""原声鼓组""弦乐铺底"），**不列具体 VST/硬件型号**。标注 MIDI 通道、推荐 pan、演奏法类型。

### 3. 人声轨（SV 专用，sv_voicebank.md）

只给音高轮廓 + 按乐句切分的歌词占位 + **SV 声库类型**推荐（日系/中系/英系、男/女、音域）。不猜歌词。导入流程：用 `vocal_melody.mid` 作参考唱线 → SV 对齐 → 填词 → 选声库。

### 4. 作者风格指纹（fingerprint_framework.md，新增）

- 对每首参考曲提取特征（调、进行、BPM、配器占比、段落比例、音色亮度）。

- 聚合统计：众数/区间（如 BPM 120–128、常用 I–V–vi–IV、固定"钢琴+弦乐+808"搭配）。

- 产出 `AUTHOR_FINGERPRINT.json`：该作者的"听觉身份证"。

- 单首拆析时回查指纹，标注"符合作者惯例 / 偏离"，让拆析更有针对性。

### 4.1 风格化 MIDI 生成（compose_from_fingerprint.py）

指纹不只能用于回查，还能作为原创编曲生成器的条件输入。`compose_from_fingerprint.py` 把调性、BPM、典型和弦进行、段落比例、层次频率翻译成 `melody / pad / bass / drums` 分轨 MIDI：

- 每一小节按指纹中的和弦进行轮转，避免生成时卡在同一个和弦。
- 主旋律根据段落调整音区和密度；前奏/尾奏自动降低鼓与贝斯密度。
- 输出 `notes.json` 与 `COMPOSE_REPORT.md`，让非多模态模型无需读 MIDI 也能读取音符和段落摘要。
- 支持 `--key / --scale / --bpm / --bars / --seed` 覆盖，便于生成多版草稿。
- 支持 `--prompt` 自然语言微调和 `--params params.json` 结构化覆盖；参数映射见 `style_prompt_guide.md`。

该模块属于规则式编曲草稿，不读音频、不复现具体歌曲；目的是在作者语言边界内快速生成可编辑的多轨 MIDI 起点。

## 八、局限与风险（写进报告）

- 自动转录对密集织体/失真吉他有误差，需人工修音。

- Demucs 分离非无损，`drums/bass` 较准，`other` 混叠多，主旋律置信度要标注。

- 歌词与演唱是你的保留工作。

- 重依赖首次需下载模型（数 GB）。

## 九、下一步（实现阶段）

1. 创建 `/workspace/music-style-deconstructor/`：SKILL.md + 9 个脚本 + 5 个 references + assets。

2. 给出本地安装说明（Windows/macOS `pip` 命令、模型预置、FL Studio 导入步骤）。

3. （可选）用样例 MP3 在沙箱跑通端到端验证。

### 已确认决策（替代原"待确认点"）

- 宿主：**FL Studio**（导入通用 `.mid`，无需 `.flp` 模板）。

- 乐器标注：**只输出类型**，不给具体 VST/型号。

- 增强：**支持作者风格指纹**（多首参考曲聚合）。

- 增强：**支持基于指纹生成原创分轨 MIDI**（compose_from_fingerprint.py）。
