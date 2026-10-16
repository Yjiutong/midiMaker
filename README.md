# midiMaker

这是一个可以被 Claude 对话安装的 Codex skill 仓库，仓库里包含一个可安装的 skill：

`music-style-deconstructor`：给定音频，分离编曲元素、提取风格指纹、生成拆分乐器 MIDI，并支持基于提示词微调风格参数。

Skill 主体在 [skills/music-style-deconstructor](./skills/music-style-deconstructor)，其中 [SKILL.md](./skills/music-style-deconstructor/SKILL.md) 是技能入口。

## 一键安装

### 在 Codex 中安装

在 Codex 对话里直接说：

```text
安装 https://github.com/Yjiutong/midiMaker 的 music-style-deconstructor skill
```

也可以直接说：

```text
安装 https://github.com/Yjiutong/midiMaker
```

Codex 会读取 `skills/README.md`，自动选择 `skills/music-style-deconstructor` 完成安装。

等价命令（如果你本机已安装 Codex 自带 skill-installer）：

```bash
python <CODEX_HOME>/skills/.system/skill-installer/scripts/install-skill-from-github.py \
    --repo Yjiutong/midiMaker \
    --path skills/music-style-deconstructor
```

安装后会复制到：

```text
$CODEX_HOME/skills/music-style-deconstructor/
```

### 命令行一键安装

真实一行命令（不需先 clone 本仓库）：

Windows PowerShell：

```powershell
irm https://raw.githubusercontent.com/Yjiutong/midiMaker/main/install.ps1 | iex
```

macOS / Linux：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Yjiutong/midiMaker/main/install.sh)
```

这条命令会从 GitHub 拉取安装脚本，sparse checkout 对应 skill 目录，复制到 `$CODEX_HOME/skills/music-style-deconstructor`，并自动安装核心依赖。

也可以先 clone 再运行安装脚本：

Windows PowerShell：

```powershell
git clone --depth 1 https://github.com/Yjiutong/midiMaker.git midiMaker
cd midiMaker
.\install.ps1
```

macOS / Linux：

```bash
git clone --depth 1 https://github.com/Yjiutong/midiMaker.git midiMaker
cd midiMaker
INSTALL_DEPS=1 bash install.sh
```

安装脚本会用 git sparse checkout 只拉取 `skills/music-style-deconstructor`，复制到 Codex skills 目录，并可选安装核心依赖。如需完整重型依赖（demucs / basic-pitch / torchcrepe），安装后再运行：

```bash
cd $CODEX_HOME/skills/music-style-deconstructor
python scripts/install_skill_deps.py --full
```

## 仓库结构

```text
.
├── skills/
│   └── music-style-deconstructor/
│       ├── SKILL.md
│       ├── scripts/
│       ├── references/
│       ├── assets/
│       └── requirements/
├── results/                  # 训练/验证结果（示例，不入 skill 本体）
├── install.ps1               # Windows 一键安装
├── install.sh                # macOS / Linux 一键安装
└── README.md
```

`results/` 只用于验证和复盘，不属于安装后的 skill 本体。`samples/`、`.skill-deps/`、`output/` 等本地产物不纳入 git。

## 本地开发

直接进入 skill 目录开发：

```bash
cd skills/music-style-deconstructor
python scripts/install_skill_deps.py --full
python scripts/separate_stems.py demo.mp3 --out output/stems
python scripts/extract_features.py demo.mp3 --stems output/stems --out output/features.json
```

## 注意

- 本仓库只提交 skill 代码和验证结果，不提交原始音频样本及模型权重。
- 生成 MIDI 用于编曲草稿，不代表音频转录结果；最终仍需人工修音和编排。
