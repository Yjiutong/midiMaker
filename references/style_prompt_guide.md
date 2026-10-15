# 风格提示词微调指南（Agent 接入用）

本文用于 agent 在接入 `music-style-deconstructor` 后，把用户自然语言的编曲偏好翻译成 `compose_from_fingerprint.py` 可用的参数。

## 调用方式

1. 让用户提供作者指纹或 `features.json`，例如 `AUTHOR_FINGERPRINT.json`。
2. 理解用户提示词，例如“更明亮、鼓更密、副歌高点”。
3. 直接调用：

```bash
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --prompt "更明亮、鼓更密" \
    --out output/compose/ --name new_song --bars 32 --seed 42
```

4. 如果提示词比较复杂，agent 可以先把其解析成 `params.json`，再用 `--params` 传入：

```bash
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --params params.json --out output/compose/
```

## 参数说明

| 参数 | 类型 | 作用 |
| --- | --- | --- |
| `bpm` | number | 直接指定 BPM |
| `bpm_shift` | number | 相对指纹 BPM 加减，例如 `+6` |
| `bars` | number | 生成小节数 |
| `key` / `scale` | string | 覆盖调性，例如 `A` / `minor` |
| `density` | 0.0–1.0 | 鼓/贝斯整体密度 |
| `brightness` | 0.0–1.0 | 明亮度，越高主旋律音区越亮 |
| `pad_density` | 0.0–1.0 | Pad 铺底密度，越小越稀疏 |
| `melody_density` | 0.0–1.0 | 主旋律密度，不传则按段落自动 |
| `bass_density` | 0.0–1.0 | 贝斯密度 |
| `drums` | bool | 是否生成鼓轨，`false` 表示不生成 |
| `progression` | string[] | 覆盖和弦进行 |
| `section_ratio` | object | 覆盖段落比例 |
| `seed` | number | 随机种子，便于复现 |

## 常见提示词映射

| 用户说 | 建议 agent 处理 |
| --- | --- |
| “快一点 / 更活跃 / 动感” | `bpm_shift: +6`, `density: 0.9` |
| “慢一点 / 抒情 / 安静” | `bpm_shift: -8`, `density: 0.55` |
| “更明亮 / 清亮” | `brightness: 0.8` |
| “更暗 / 低沉” | `brightness: 0.3` |
| “鼓再密一点 / 强鼓” | `density: 0.95` |
| “少一点鼓 / 无鼓” | `drums: false` 或 `density: 0.4` |
| “Pad 少一点” | `pad_density: 0.5` |
| “Pad 多一点” | `pad_density: 1.0` |
| “副歌更高一点” | `brightness: 0.8`，或调 `melody_density: 0.75` |

## 使用原则

- 只把用户要求明确映射到参数，不做过度解释。
- 生成的 MIDI 仍是草稿；agent 应把 `COMPOSE_REPORT.md` 里的关键参数反馈给用户，便于继续微调。
- 如果要“更像某作者”，优先依赖指纹本身；只有在用户明确说“风格偏一点”时才调整覆盖参数。
