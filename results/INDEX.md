# 训练结果索引（music-style-deconstructor）

本目录仅存放**训练后结果**（音高线 MIDI、特征、指纹、生成编曲），原始素材 `samples/`
与运行时 `.skill-deps/` 按 `.gitignore` 规则**不纳入 git**。

## 多轮训练记录

### 第 1 轮 — 逐样本人声参考线提取
- 产物：`results/vocal/<样本名>/{vocal_melody.mid, lyrics_placeholder.txt}`
- 汇总：`results/SUMMARY.md`
- 结论：33 个单音样本各检出 1 个音高事件（稳定参考音高 A4）；
  1 首整曲样本音域 C3–D4、45 个音高事件。

### 第 2 轮 — 整曲解构 + 风格指纹
- 歌曲级特征：`results/songs/song_01/features.json`
  （时长 33.2s、152 BPM、F 大调、亮度质心 1549Hz、干净集中/低频厚重）
- 风格报告：`results/songs/song_01/STYLE_REPORT.md`
- 风格指纹：`results/fingerprint/song_01_author.json`
  （F 大调、152 BPM、典型进行 A:min→F:maj / C:maj→D:min 等）

### 第 3 轮 — 基于指纹的风格化作曲（compose_from_fingerprint）
- 产物：`results/compose/{melody,pad,bass,drums}.mid` + `notes.json` + `COMPOSE_REPORT.md`
- 说明：由第 2 轮指纹规则生成的可导入 FL Studio 的多轨编曲草稿，
  验证「解构 → 指纹 → 作曲」完整闭环。非音频转录，需人工完善。

## 复现方式
```bash
# 依赖（安装到 skill 内部 .skill-deps，不进 git）
cd skills/music-style-deconstructor
python scripts/install_skill_deps.py

# 回仓库根目录
cd ../..

# 第 1 轮：批量提取全部人声样本参考线
python _batch.py

# 第 2 轮：整曲解构 + 指纹（再次进入 skill 目录执行）
cd skills/music-style-deconstructor
python scripts/extract_features.py ../../samples/vocal/<整曲样本>.wav \
    --virtual-singer --out ../../results/songs/song_01/features.json
python scripts/style_report.py ../../results/songs/song_01/features.json \
    --out ../../results/songs/song_01/STYLE_REPORT.md --virtual-singer
python scripts/build_fingerprint.py ../../results/songs/song_01/features.json \
    --out ../../results/fingerprint/song_01_author.json

# 第 3 轮：风格化作曲
python scripts/compose_from_fingerprint.py ../../results/fingerprint/song_01_author.json \
    --out ../../results/compose --name vocal_style_demo --bars 32 --seed 42
```
