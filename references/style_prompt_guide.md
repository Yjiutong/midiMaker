# 风格提示词微调指南（Agent 接入用）

本文用于 agent 在接入 `music-style-deconstructor` 后，把用户自然语言的编曲偏好翻译成 `compose_from_fingerprint.py` 可用的参数。

## Agent 规范化流程

1. 接收用户自然语言，例如“更明亮、鼓更密、副歌更高、前奏安静”。
2. 去除模糊或矛盾表达，整理为标准 prompt（见下）。
3. 把标准 prompt 写入 `STYLE_PROMPT.md`，或直接解析为 `params.json`。
4. 调用 `compose_from_fingerprint.py --prompt-file STYLE_PROMPT.md` 或 `--params params.json`。
5. 读取 `COMPOSE_REPORT.md` 回给用户，根据下一轮自然语言继续迭代。

## 标准 Prompt 模板

```markdown
# 风格方向
明亮 / 暗沉 / 中性

# 速度
比指纹快一点 / 保持原速 / 比指纹慢一点

# 配器强调
鼓：密 / 普通 / 稀疏
Pad：多 / 正常 / 少
贝斯：紧凑 / 正常

# 段落处理
Intro：安静
Chorus：更高、更密
Outro：收束
```

标准 prompt 必须避免同时出现互相矛盾的词；例如“前奏安静”不能写成“整体很安静”，否则会同时触发慢速和低密度。

## 调用方式

1. 让用户提供作者指纹或 `features.json`，例如 `AUTHOR_FINGERPRINT.json`。
2. 如果是 agent 已规范化的标准 prompt 文件，用 `--prompt-file` 传入：

```bash
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --prompt-file STYLE_PROMPT.md \
    --out output/compose/ --name new_song --bars 32 --seed 42
```

3. 如果提示词较短且明确，也可以直接传给 `--prompt`：

```bash
python scripts/compose_from_fingerprint.py AUTHOR_FINGERPRINT.json \
    --prompt "更明亮、鼓更密" \
    --out output/compose/ --name new_song --bars 32 --seed 42
```

4. 如果提示词比较复杂，agent 可以先解析成 `params.json`，再用 `--params` 传入：

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
