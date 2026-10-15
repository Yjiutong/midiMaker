# music-style-deconstructor

把一首音频自动拆成编曲元素分轨和多轨 MIDI，并生成风格拆析、段落摘要、音色分析、人声参考包。

适合用于：
- 扒带 / 编曲参考
- FL Studio 多轨 MIDI 导入
- Synthesizer V 虚拟歌姬人声参考
- 对一首或多首参考曲提炼作者风格指纹

> 完整 skill 工作流见 [SKILL.md](./SKILL.md)，算法设计见 [references](./references/music-style-deconstructor_design.md)。

## 功能

- 音频分轨：`vocals / drums / bass / other`
- 特征提取：BPM、调性、和弦、段落、频谱、音色
- 多轨转录：贝斯、鼓、主旋律、和声 Pad
- 逐轨 `notes.json`：起止时间、音高、力度、置信度
- 段落摘要与音频叙事：和弦、鼓型、织体、频谱、音色
- 作者风格指纹：多首参考曲聚合
- 风格化 MIDI 生成：基于作者指纹生成原创 melody / pad / bass / drums 分轨
- 虚拟歌姬特化：人声音高线、音节密度、SV 参考包

## 目录结构

```text
.
├── SKILL.md                    # skill 主文档
├── README.md
├── scripts/
│   ├── separate_stems.py       # Demucs / HPSS 分轨
│   ├── extract_features.py     # 全局特征与音色特征
│   ├── transcribe_stems.py     # stem -> MIDI + 鼓分类 + 人声音高
│   ├── split_arrangement.py    # other -> 主旋律 / Pad
│   ├── style_report.py         # 风格拆析报告
│   ├── section_summary.py      # 段落摘要 + 音频叙事
│   ├── timbre_analysis.py      # 音色分析报告
│   ├── vocal_track_sv.py       # Synthesizer V 人声参考包
│   ├── build_fingerprint.py    # 作者风格指纹
│   ├── compose_from_fingerprint.py # 指纹 -> 原创多轨 MIDI
│   ├── package_output.py       # 合并多轨 MIDI
│   ├── notes_io.py             # notes.json 读写
│   ├── notes_json.py           # 从 MIDI 目录生成 notes.json
│   ├── fetch_virtual_singer_samples.py
│   ├── install_skill_deps.py
│   └── skill_runtime.py
├── assets/
│   ├── virtual_singer_sources.json
│   └── lyric_template.txt
├── references/
│   ├── analysis_framework.md
│   ├── transcription_algorithms.md
│   ├── instrument_types.md
│   ├── midi_mapping.md
│   ├── sv_voicebank.md
│   ├── fingerprint_framework.md
│   ├── style_prompt_guide.md
│   ├── virtual_singer_spec.md
│   └── music-style-deconstructor_design.md
└── requirements/
    ├── core.txt
    └── full.txt
```

## 安装

需要 Python 3.10+，推荐使用仓库内置依赖安装器：

```bash
python scripts/install_skill_deps.py            # 核心依赖
python scripts/install_skill_deps.py --full     # 额外安装 demucs / basic-pitch / torchcrepe
```

也可以手动安装：

```bash
pip install demucs basic-pitch librosa scipy pretty_midi numpy
```

`demucs` 首次运行会下载神经网络模型；未安装时自动退回 HPSS 兜底分轨。

## 快速开始

请确认你有权分析目标音频，例如自己制作的歌曲、公开演示素材或已获得授权的曲目。

```bash
# 1. 分轨
python scripts/separate_stems.py input.mp3 --out stems/

# 2. 提取特征
python scripts/extract_features.py input.mp3 --stems stems/ --out features.json

# 3. stem 转 MIDI
python scripts/transcribe_stems.py stems/ --out midi_raw/

# 4. 拆分主旋律 / Pad
python scripts/split_arrangement.py midi_raw/other.mid --out midi/

# 5. 乐器类型标注
python scripts/instrument_map.py features.json midi/ --out INSTRUMENT_MAP.md --genre pop

# 6. 风格报告
python scripts/style_report.py features.json --out STYLE_REPORT.md \
    --drums midi_raw/drums.mid

# 7. 段落摘要 + 音频叙事
python scripts/section_summary.py features.json \
    --midi midi_raw/ --midi midi/ --out SECTION_SUMMARY.md

# 8. 音色分析
python scripts/timbre_analysis.py features.json --out TIMBRE_REPORT.md

# 9. SV 人声参考包
python scripts/vocal_track_sv.py stems/vocals.wav --out vocal/

# 10. 合并输出
python scripts/package_output.py midi/ vocal/vocal_melody.mid \
    --map INSTRUMENT_MAP.md --out output/ --name mysong

# 11. （可选）基于作者风格指纹生成一首新的分轨 MIDI 草稿
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --out output/compose/ --name new_song --bars 32 --seed 42

# 也可以用提示词微调风格参数（适合 agent 接入口语化指令）
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --prompt "更明亮、鼓更密、快一点" \
    --out output/compose/ --name new_song --bars 32 --seed 42
```

生成的 `output/compose/` 包含 `melody.mid`、`pad.mid`、`bass.mid`、`drums.mid`、`notes.json` 和 `COMPOSE_REPORT.md`，可以直接拖入 FL Studio 继续编曲。该过程不读取音频，而是用指纹中的调性、BPM、和弦进行、段落比例和层次比例生成原创编曲草稿。

`--prompt` 支持常见中文/英文风格词，如快慢、明亮/暗沉、鼓密/少鼓、Pad 多少；agent 也可以把提示词解析成 `params.json` 用 `--params` 传入，参数映射见 `references/style_prompt_guide.md`。

## 虚拟歌姬特化

对虚拟歌姬 / Synthesizer V / VOCALOID / UTAU 等歌曲，追加 `--virtual-singer` 参数：

```bash
python scripts/extract_features.py input.mp3 --stems stems/ --out features.json --virtual-singer
python scripts/transcribe_stems.py stems/ --out midi_raw/ --virtual-singer
python scripts/style_report.py features.json --out STYLE_REPORT.md --virtual-singer
python scripts/vocal_track_sv.py stems/vocals.wav --out vocal/ --virtual-singer
```

公开 UTAU 示例可以用以下命令拉取，用于快速验证：

```bash
python scripts/fetch_virtual_singer_samples.py --out /tmp/vs_sample
```

## 输出说明

```text
output/
├── mysong_multitrack.mid
├── README_导入FLStudio.md
├── features.json
├── notes.json
├── STYLE_REPORT.md
├── INSTRUMENT_MAP.md
├── SECTION_SUMMARY.md/json
├── AUDIO_NARRATIVE.md
├── TIMBRE_REPORT.md/json
└── vocal/
```

所有自动分析结果仅供编曲参考，最终仍需结合听感人工修正。

## 局限

- 自动转录对密集织体、失真吉他、重叠人声误差明显。
- HPSS 兜底分轨不是真实源分离，`other` 与 `vocals` 可能出现近似重复。
- 人声音高线不识别歌词，只锚定音高与节奏骨架。
- 请只处理你有权分析的音频，并遵守原始素材的许可要求。

## License

见 [LICENSE](./LICENSE)。
