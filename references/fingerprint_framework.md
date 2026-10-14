# 作者风格指纹框架（Author Fingerprint）

> 用途：输入同一作者的多首参考曲，提炼该作者的「听觉身份证」(`AUTHOR_FINGERPRINT.json`)。  
>     后续单首拆析时回查指纹，`style_report.py` 会标注该曲「符合 / 偏离作者惯例」，让拆析与编曲参考更有针对性。

## 一、指纹维度（作者级聚合）

对每首参考曲先跑 `extract_features.py` 得到 `features.json`，再在维度上做**统计聚合**（众数 / 均值 / 区间）：

| 维度 | 聚合方式 | 产出 |
| --- | --- | --- |
| 调性 (Key) | 众数 | 最常用调与调式 |
| 和弦进行 (Progressions) | n-gram 频次合并，取 Top-K | 作者标志性进行（如 `I–V–vi–IV`） |
| BPM | 均值 ± 标准差 / 区间 | 速度区间（如 118–128） |
| 配器搭配 (Layers) | 各层出现频率 + 能量占比均值 | 固定叠层（如「钢琴+弦乐+808」） |
| 段落比例 (Section Ratio) | 各段时长占比均值 | 副歌占比、是否有固定结构 |
| 音色亮度 (Brightness) | spectral_centroid 区间 | 冷暖取向区间 |
| 节奏密度 (Groove) | 鼓 onset 密度均值 | 律动强度区间 |

## 二、AUTHOR_FINGERPRINT.json 结构示例

```json
{
  "author": "某作者",
  "num_reference_tracks": 5,
  "key": {"mode": "major", "common_keys": ["C", "G", "D"]},
  "progressions_top": [["I","V","vi","IV"], ["vi","IV","I","V"]],
  "bpm": {"mean": 123.4, "std": 3.1, "range": [118, 128]},
  "layers": {
    "melody": {"frequency": 1.0, "types": ["合成主音 Lead", "原声钢琴"]},
    "pad":    {"frequency": 0.8, "types": ["暖色 Pad"]},
    "bass":   {"frequency": 1.0, "types": ["电贝斯", "合成贝斯"]},
    "drums":  {"frequency": 1.0, "types": ["原声鼓组"]}
  },
  "section_ratio": {"intro": 0.08, "verse": 0.34, "chorus": 0.34, "bridge": 0.10, "outro": 0.06},
  "brightness": {"mean": 2100.0, "range": [1700, 2500]},
  "groove_density": {"mean": 0.42, "range": [0.35, 0.50]}
}
```

## 三、聚合方法（build_fingerprint.py）

1. 载入 N 个 `features.json`。

2. 逐维度聚合：

  <BulletedList id="0O8iRletMA17cmxbX3E2Lj">
    **类别型**（key、layer types）：计数取众数 / Top。
  </BulletedList>

  <BulletedList id="HQ0mq9azHy7p2OOKAHidss">
    **数值型**（bpm、brightness、density）：算均值、标准差、范围（p5–p95）。
  </BulletedList>

  <BulletedList id="jFPVX2JtAYujzw4SOTTpSN">
    **序列型**（progressions）：把所有曲子的 chord n-gram 合并计数，取全局 Top-K。
  </BulletedList>

  <BulletedList id="7i3vKmvlgaOzyiqvvmcBPg">
    **比例型**（section_ratio）：逐段求均值。
  </BulletedList>

1. 写出 `AUTHOR_FINGERPRINT.json`（可手工补充 `author` 名与备注）。

> 建议参考曲 ≥ 3 首，否则统计不稳定；风格跨度大的作者指纹会「宽泛」，属正常现象。

## 四、单首回查（style_report.py --fingerprint）

传入指纹后，在报告每维度末尾追加对比：

- **符合**：该曲数值落在指纹区间内 / 类别在众数集合内 → 标注「符合作者惯例」。

- **偏离**：明显超出区间或不属于惯用类别 → 标注「偏离：差异点…」（如「本曲 BPM 150 高于作者常用 118–128」）。

这让用户快速判断：这首是作者「典型作」还是「实验/跨界作」，从而决定编曲参考的权重。
