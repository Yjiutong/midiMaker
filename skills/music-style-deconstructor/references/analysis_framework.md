# 风格拆析框架（Analysis Framework）

本文件规定 `style_report.py` 如何把 `features.json` 与分轨 MIDI 的数值特征，组织成**可被人理解的风格拆析报告**。  
  LLM 在生成报告时，应逐项覆盖下列维度，并尽量用**具体数值**（BPM、调、进行、比例）支撑结论，避免空泛形容词。

## 维度一：曲式结构（Form）

- **数据来源**：`features.json` 的 `sections`（基于频谱 novelty / 自相似性的段落边界）。

- **分析方法**：列出段落序列与各自时长占比，如 `Intro 8s(8%) → Verse 24s → Pre 8s → Chorus 24s → ...`。

- **报告要点**：主歌/副歌循环模式、是否有 Bridge/Intro/Outro、段落长度是否规律。

## 维度二：调性与和声（Tonality \& Harmony）

- **数据来源**：`features.json` 的 `key` / `scale` / `chord_sequence`；`notes` 的音高集合。

- **分析方法**：

  <BulletedList id="Cd87H1MXcGl6tzYjPot4Vx">
    主调与调式（大调/小调/其他）。
  </BulletedList>

  <BulletedList id="APH9UN4swpRNyDVNFSAR9U">
    提取**高频和弦进行**（对 chord_sequence 做 n-gram 统计，给出 Top 进行，如 `I–V–vi–IV`）。
  </BulletedList>

  <BulletedList id="EaRZj1CvFlBk8AvsVLFV2B">
    是否使用色彩和弦（七和弦、九和弦、挂留、转位）、是否有转调/离调。
  </BulletedList>

- **报告要点**：典型进行、和声紧张度、是否频繁离调、调性稳定性。

## 维度三：节奏律动（Groove）

- **数据来源**：`features.json` 的 `bpm` / `beat_positions`；鼓轨 onset 密度。

- **分析方法**：

  <BulletedList id="lxBSYmkyQfBc2BC1BWTeI4">
    BPM 与拍号（4/4 为主则标注）。
  </BulletedList>

  <BulletedList id="A7TMitnsCVyXsKndIW1q4x">
    鼓型：kick 与 snare 的节律（如「四踩底鼓 + 反拍军鼓」）、hi-hat 密度（八分/十六分）。
  </BulletedList>

  <BulletedList id="QDsOAuV9qZSPdJBlNBFKf0">
    切分密度：非正拍音符占比。
  </BulletedList>

  <BulletedList id="kbQZYhCBcrY83456Rz5he6">
    是否 swing / 三连感觉。
  </BulletedList>

- **报告要点**：律动类型（直拍/摇摆/碎拍）、密度、稳定性。

## 维度四：配器层次（Arrangement Layers）

- **数据来源**：各 stem 的能量包络与占比（`features.json` 的 `stem_energy`）；分轨 MIDI 的音区分布。

- **分析方法**：统计同时存在几层（主旋律 / 和声垫 / 节奏 / 贝斯 / 打击），各层在段落中的进出（哪些段加鼓、哪些段加 Pad）。

- **报告要点**：织体密度随段落的变化、哪一层是「骨架」、留白处理。

## 维度五：音色取向（Timbre）

- **数据来源**：`features.json` 的 `spectral_centroid`/`spectral_bandwidth`（明暗）、`roughness`（失真/粗糙度估计）、`timbre`/`stem_timbre`（音色标签、平坦度、过零率、低频占比、MFCC、频谱对比）。

- **分析方法**：用亮度/粗糙度区间判断音色冷暖、干净/失真、模拟/数字取向；用 MFCC 与分轨音色标签区分人声、鼓、贝斯、和声层质感；结合各轨乐器类型（`INSTRUMENT_MAP.md`）。

- **报告要点**：整体明暗、是否大量失真/饱和、空间感（混响多少可从低频/高频衰减粗略判断）、各 stem 是否偏亮/偏暗/干净/颗粒。

## 维度六：动态与混音（Dynamics \& Mix）

- **数据来源**：`features.json` 的 `rms` 包络、各 stem 的响度平衡。

- **分析方法**：段落间动态对比（副歌是否明显更响）、各层响度平衡（人声/鼓是否突出）。

- **报告要点**：动态范围、混音重点（人声前置 / 鼓驱动 / 乐器铺底）。

## LLM 报告生成提示框架（style_report.py 使用）

```
你是资深编曲分析师。基于以下结构化特征，生成一份风格拆析报告。
务必用具体数值支撑，分六个小节：曲式结构 / 调性与和声 / 节奏律动 /
配器层次 / 音色取向 / 动态与混音。最后给一段「编曲要点总结」。
{features_json}
{chord_top_progressions}
{stem_energy}
{optional_fingerprint_deviation}   # 若提供指纹，标注符合/偏离作者惯例
```

> 若传入 `--fingerprint`，在每小节末尾追加「与作者指纹对比：符合 / 偏离（差异点）」。
