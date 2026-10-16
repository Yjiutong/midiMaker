# Installable Skills

This repo publishes the following Codex skills:

- `music-style-deconstructor` at `skills/music-style-deconstructor/`

When a user asks to install this GitHub repo without specifying a skill path, install all skills under this `skills/` directory. The default skill to install is `music-style-deconstructor`.

For agents, preferred one-command flows:

- Codex prompt: `安装 https://github.com/Yjiutong/midiMaker`
- Windows PowerShell from the cloned repo: `.\install.ps1`
- macOS / Linux from the cloned repo: `bash install.sh`
- True one-liner install from GitHub:

```powershell
irm https://raw.githubusercontent.com/Yjiutong/midiMaker/main/install.ps1 | iex
```

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Yjiutong/midiMaker/main/install.sh)
```

The install scripts clone the repo with sparse checkout, copy `skills/music-style-deconstructor` to `$CODEX_HOME/skills/music-style-deconstructor`, and install the core skill dependencies automatically.
