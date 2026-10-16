param(
  [string]$Repo = "https://github.com/Yjiutong/midiMaker.git",
  [string]$Dest = "$env:USERPROFILE\.codex\skills\music-style-deconstructor",
  [switch]$Force,
  [switch]$InstallDeps = $true
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git is required to install music-style-deconstructor."
}

$tmp = Join-Path $env:TEMP ("midiMaker-install-" + [guid]::NewGuid().ToString("N"))
$repoRoot = Join-Path $tmp "repo"
$skillName = "music-style-deconstructor"

try {
  & git clone --depth 1 --filter=blob:none --sparse $Repo $repoRoot
  Push-Location $repoRoot
  & git sparse-checkout set "skills/$skillName"
  & git checkout
  Pop-Location

  $src = Join-Path $repoRoot "skills" $skillName
  if (-not (Test-Path -LiteralPath $src)) {
    throw "Skill path not found: $src"
  }

  $parent = Split-Path -Parent $Dest
  New-Item -ItemType Directory -Force -Path $parent | Out-Null

  if (Test-Path -LiteralPath $Dest) {
    if (-not $Force) {
      throw "Destination already exists: $Dest (use -Force to replace)"
    }
    Remove-Item -LiteralPath $Dest -Recurse -Force
  }

  Copy-Item -Recurse -LiteralPath $src -Destination $Dest

  if ($InstallDeps) {
    Push-Location $Dest
    python scripts/install_skill_deps.py
    Pop-Location
  }
} finally {
  if (Test-Path -LiteralPath $tmp) {
    Remove-Item -LiteralPath $tmp -Recurse -Force
  }
}

Write-Host "Installed music-style-deconstructor to $Dest"
if (-not $InstallDeps) {
  Write-Host "Next: cd $Dest; python scripts/install_skill_deps.py --full"
}
