# 训练结果索引（music-style-deconstructor · 虚拟歌姬数据集）

本目录仅存放**训练后结果**（音高线 MIDI、特征、指纹、生成编曲），原始素材 `samples/`
与运行时 `.skill-deps/` 按 `.gitignore` 规则**不纳入 git**。

## 数据来源（许可证干净）
- `assets/virtual_singer_sources.json`：34 个样本的来源与许可证元数据
  - hvuv23544 的 33 个 CV 单音样本（CC-BY-4.0）
  - 1 首整曲 demo：UTAU Seiren 演唱的 *Daisy Bell*（公开 demo，已排除商业/受限声库）
- 已排除 KOLDOS / Rikaloid / Anta_Shizuko / GoogVoiceBank / Iirai / SV·Dreamtonics 等受限来源

## 多轮训练记录

### 第 1 轮 — 逐样本人声参考线提取（vocal_track_sv --virtual-singer）
- 产物：`results/vocal/<样本名>/{vocal_melody.mid, lyrics_placeholder.txt, sv_recommendation.md}`
- 汇总：`results/SUMMARY.md`
- 结论：33 个 CV 单元音样本均检测到参考音高 A4（440Hz，CV 录音惯例）；
  唯一整曲 demo（Daisy Bell）音域 C3–D4、45 个音高事件。

### 第 2 轮 — 整曲解构 + 作者风格指纹
- 歌曲级特征：`results/songs/daisy_bell/features.json`
  （时长 33.2s、152 BPM、F 大调、亮度质心 1549Hz、干净集中/低频厚重）
- 风格报告：`results/songs/daisy_bell/STYLE_REPORT.md`
- 作者指纹：`results/fingerprint/daisy_bell_author.json`
  （F 大调、152 BPM、典型进行 A:min→F:maj / C:maj→D:min 等）

### 第 3 轮 — 基于指纹的风格化作曲（compose_from_fingerprint）
- 产物：`results/compose/{melody,pad,bass,drums}.mid` + `notes.json` + `COMPOSE_REPORT.md`
- 说明：由第 2 轮指纹规则生成的可导入 FL Studio 的多轨编曲草稿，
  验证「解构 → 指纹 → 作曲」完整闭环。非音频转录，需人工完善。

## 复现方式
```bash
# 依赖（安装到 .skill-deps，不进 git）
python scripts/install_skill_deps.py --core

# 第 1 轮：批量提取全部虚拟歌姬样本人声参考线
python _batch.py

# 第 2 轮：整曲解构 + 指纹
python scripts/extract_features.py samples/virtual_singer/utau_seiren_daisy_bell.wav \
    --virtual-singer --out results/songs/daisy_bell/features.json
python scripts/style_report.py results/songs/daisy_bell/features.json \
    --out results/songs/daisy_bell/STYLE_REPORT.md --virtual-singer
python scripts/build_fingerprint.py results/songs/daisy_bell/features.json \
    --out results/fingerprint/daisy_bell_author.json --author "UTAU Seiren (Daisy Bell demo)"

# 第 3 轮：风格化作曲
python scripts/compose_from_fingerprint.py results/fingerprint/daisy_bell_author.json \
    --out results/compose --name seiren_style_demo --bars 32 --seed 42
```
