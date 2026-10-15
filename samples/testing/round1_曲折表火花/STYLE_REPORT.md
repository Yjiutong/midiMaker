# 风格拆析报告

> 本报告由 style_report.py 基于 features.json 自动生成，供编曲参考。

- 时长：128.75s
- BPM：95.7
- 调性：E · minor
- 频谱质心（brightness）：2136.3
- RMS：0.199361
- Onset 密度：2.827 / s

## 一、曲式结构

A 0:00-0:21(21.6s) → A 0:21-1:06(45.3s) → A 1:06-2:08(61.9s)

段落时长占比：

- A: 128.8s

## 二、调性与和声

- 主调：E  minor
- 和弦片段 Top 进行：G:maj-E:min, E:min-G:maj, D:maj-E:min, E:min-F#:min, E:min-E:min
- 色彩/转调：暂按特征自动标注；如需人工确认请结合和弦序列。

## 三、节奏律动

- 最近拍点数量：199
- 起音帧数：364
- Onset 密度：2.827 / s
- 鼓轨：499 个鼓点，密度 4.02 / s

## 四、配器层次

- vocals stem RMS 能量：0.159729
- drums stem RMS 能量：0.070459
- bass stem RMS 能量：0.065451
- other stem RMS 能量：0.159729

## 五、音色取向

- 音色标签：中性亮度, 干净集中
- MFCC 亮度：0.1938
- 频谱平坦度：0.0177
- 低频能量占比：0.1198
- 分轨音色：

  - vocals: 中性亮度, 干净集中（centroid 1907.8 Hz，flatness 0.0049）
  - drums: 明亮, 干净集中, 颗粒/失真（centroid 2655.9 Hz，flatness 0.0442）
  - bass: 偏暗, 干净集中, 低频厚重（centroid 188.1 Hz，flatness 0.0001）
  - other: 中性亮度, 干净集中（centroid 1907.8 Hz，flatness 0.0049）
- 频谱质心：2136.3
- 频谱带宽：2166.6
- 说明：数字越大通常越亮；失真/饱和程度需结合音频主观听感。

## 六、动态与混音

- RMS：0.199361
- 说明：需对比段落 RMS 与各 stem 能量判断人声/鼓是否突出。

## 七、虚拟歌姬特化

- 该曲按虚拟歌姬歌曲处理：合成人声通常干净、音高稳定、音节密度高。
- syllabic_density：2.392
- formant_stability：0.0
- 人声 MIDI 仅锚定节奏与音高；滑音/转音在 Synthesizer V 中手动处理。

## 编曲要点总结

- 先核对主调与和弦进行的判断是否与听感一致。
- 自动转录只作为参考，最终编曲仍以耳朵为准。
