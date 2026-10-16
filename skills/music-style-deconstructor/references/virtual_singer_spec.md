# 虚拟歌姬歌曲算法特化

本文件规定 flow 中遇到虚拟歌姬（Vocaloid / Synthesizer V / CeVIO / ACE Studio / UTAU / SV 等）歌曲时的特化处理。目标不是把人声当成普通自然人声去拆，而是利用虚拟歌姬声音的规律提高分轨、转录、风格报告和 SV 参考包的质量。

## 一、虚拟歌姬声音的常见规律

- **合成质**：人声轨通常干净、少真实房间混响，高频 formant 稳定，无明显气声/口水音。
- **音高准确**：多数虚拟歌姬由 MIDI/音符驱动，音高线稳定，音头和音尾边界比真人更规则。
- **连滑音/颤音偏人工**：滑音和 vibrato 通常由参数控制，存在“阶梯化”或机械感，不能套用自然颤音阈值。
- **音节密集**：常见 J-Pop / C-Pop / 电子舞曲风格中，歌词密度高，音节边界紧，静音间隔短。
- **音域偏高**：很多虚拟歌姬 demo 使用中高音区，低音区能量少；适合单独提高人声检测 fmin/fmax。
- **伴奏模板化**：虚拟歌姬歌曲中常见钢琴/合成器 Pad/电子鼓/打弦贝斯组合，`other` 层混叠相对可控。

## 二、算法特化建议

### 1. stem 分离

- 优先使用 `demucs --two-stems vocals` 或 `htdemucs_6s`，把合成人声与伴奏分离得更干净。
- 若 Demo 只有一个纯人声 `.wav`（如 UTAU 参考样本），跳过 stem 分离，直接做 `vocal_track_sv.py` 的人声参考包。
- HPSS 兜底对虚拟歌姬效果一般，只建议作为最后的占位。

### 2. 人声音高提取

- 推荐 CREPE `model='full'`，因为它对干净合成人声的稳定音高效果好。
- 对虚拟歌姬人声，建议把 fmin 调到 `120`–`140`，fmax 调到 `1500`–`1800`，缩小搜索范围。
- 对连续音高序列做更保守的中值平滑，避免把 synth vibrato 片段切成过多短音符。
- 对 `vocal` stem 中低能量帧直接置静音，不要硬造音高。

### 3. 歌词占位与乐句切分

- 虚拟歌姬歌曲往往乐句内静音间隔更短，`vocal_track_sv.py --virtual-singer` 时把乐句切分 gap 从 `0.4s` 降到 `0.2s`。
- 音高线只保留节奏骨架；合成滑音/转音要在 Synthesizer V 中用 Pitch 曲线处理，不强行写成半音阶梯。

### 4. 特征提取

- `extract_features.py --virtual-singer` 会在 features.json 中写入 `virtual_singer: true`。
- 增加 `syllabic_density`：用 vocals stem 的音符/起音数量除以时长，虚拟歌姬通常偏高。
- 增加 `formant_stability` 的粗略估计：haronic 段频谱包络变化越小越像合成声。

### 5. 风格报告

`style_report.py --virtual-singer` 时：

- 语速/音节密度会成为节奏律动小节的重要指标。
- 配器小节增加“合成人声与伴奏的相对亮度”描述。
- 结尾提示“该曲疑似虚拟歌姬”，并建议 SV 声库按虚拟歌姬质感选型。

### 6. 乐器类型

虚拟歌姬歌曲的主旋律/人声轨不按传统 VST 推荐，而是直接进入 `sv_voicebank.md` 的声库推荐。鼓组与贝斯仍按 genre 表推荐。

## 三、CLI 接入点

- `extract_features.py --virtual-singer`
- `transcribe_stems.py --virtual-singer`
- `vocal_track_sv.py --virtual-singer`
- `style_report.py --virtual-singer`

## 四、测试样本

- `assets/virtual_singer_sources.json`（本地留存，不进 git）提供若干公开许可的虚拟歌姬 demo 链接。
- 可用 `scripts/fetch_virtual_singer_samples.py` 拉取样本到本地临时目录验证人声轨特化。
- 完整多轨虚拟歌姬歌曲需用户自行准备或通过公开许可源补充。

## 五、模型友好输出

- 非多模态模型无法直接读取音频，因此管线的最终落点不只是 MIDI：
  - `notes.json`：每轨音符带起止时间、音高、力度、置信度。
  - `SECTION_SUMMARY.md/json`：每段落的和弦 / 鼓型 / 织体摘要 + 每 stem 频谱特征。
  - `AUDIO_NARRATIVE.md`：用一两句中文概括前奏/主歌/副歌/鼓组变化，供模型快速阅读。
  - `TIMBRE_REPORT.md/json`：全曲与每 stem 的音色标签、亮度、平坦度、MFCC 与频谱对比。
- 当前默认测试路径基于 HPSS 兜底分离；若安装 `demucs` 后可换真实 4-stem 再次对比。
