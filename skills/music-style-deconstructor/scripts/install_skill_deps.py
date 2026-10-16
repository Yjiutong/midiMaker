#!/usr/bin/env python3
"""install_skill_deps.py - 创建内置 .skill-deps 环境并安装 skill 依赖。"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from skill_runtime import SKILL_ROOT, VENV_DIR, VENV_SITE


def _run(cmd, cwd=None):
    print("[install_skill_deps]", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, cwd=cwd or SKILL_ROOT, check=True)


def _verify_core(interp):
    probe = (
        "import sys; sys.path.insert(0, r'%s'); "
        "import librosa, numpy, scipy, soundfile, pretty_midi; print('core ok')" % VENV_SITE
    )
    subprocess.run([str(interp), "-c", probe], check=True, cwd=SKILL_ROOT)


def main():
    ap = argparse.ArgumentParser(description="安装 skill 内置依赖")
    ap.add_argument("--venv", default=str(VENV_DIR))
    ap.add_argument("--full", action="store_true",
                    help="同时安装 demucs / basic-pitch / torchcrepe（体积很大）")
    ap.add_argument("--force", action="store_true",
                    help="强制重装，跳过已有环境检查")
    args = ap.parse_args()

    target = VENV_SITE
    target.mkdir(parents=True, exist_ok=True)
    interp = sys.executable

    _run([str(interp), "-m", "pip", "install", "--upgrade",
          "--target", str(target), "pip"])
    _run([str(interp), "-m", "pip", "install",
          "--target", str(target),
          "-r", str(SKILL_ROOT / "requirements" / "core.txt")])
    if args.full:
        _run([str(interp), "-m", "pip", "install",
              "--target", str(target),
              "-r", str(SKILL_ROOT / "requirements" / "full.txt")])
    _verify_core(interp)

    installed = {
        "target": str(target.resolve()),
        "python": str(interp),
        "full": bool(args.full),
        "verified": True,
    }
    (VENV_DIR / "installed.json").write_text(
        json.dumps(installed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[install_skill_deps] 依赖已安装到 {target}")


if __name__ == "__main__":
    main()
