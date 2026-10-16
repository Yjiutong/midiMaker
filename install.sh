#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-https://github.com/Yjiutong/midiMaker.git}"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
DEST="${2:-$CODEX_HOME/skills/music-style-deconstructor}"
FORCE="${FORCE:-0}"
INSTALL_DEPS="${INSTALL_DEPS:-1}"

command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 1; }

tmp="$(mktemp -d)"
repo_root="$tmp/repo"
skill_name="music-style-deconstructor"

cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

git clone --depth 1 --filter=blob:none --sparse "$REPO" "$repo_root"
git -C "$repo_root" sparse-checkout set "skills/$skill_name"
git -C "$repo_root" checkout

src="$repo_root/skills/$skill_name"
if [ ! -d "$src" ]; then
  echo "Skill path not found: $src" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
if [ -e "$DEST" ]; then
  if [ "$FORCE" != "1" ]; then
    echo "Destination already exists: $DEST (set FORCE=1 to replace)" >&2
    exit 1
  fi
  rm -rf "$DEST"
fi

cp -R "$src" "$DEST"

if [ "$INSTALL_DEPS" = "1" ]; then
  (
    cd "$DEST"
    if command -v python >/dev/null 2>&1; then
      python scripts/install_skill_deps.py
    else
      python3 scripts/install_skill_deps.py
    fi
  )
fi

echo "Installed music-style-deconstructor to $DEST"
if [ "$INSTALL_DEPS" != "1" ]; then
  echo "Next: cd $DEST; python scripts/install_skill_deps.py --full"
fi
