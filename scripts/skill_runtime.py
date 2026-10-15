#!/usr/bin/env python3
"""skill_runtime.py - 让 skill 脚本优先使用内置 .skill-deps 运行时。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_ROOT / ".skill-deps"

if os.name == "nt":
    VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
    VENV_SITE = VENV_DIR / "Lib" / "site-packages"
else:
    VENV_PYTHON = VENV_DIR / "bin" / "python"
    VENV_SITE = VENV_DIR / "lib" / "python3.12" / "site-packages"


def prepend_site_packages() -> bool:
    """把 .skill-deps 的 site-packages 放到 sys.path 前面，返回是否找到。"""
    if VENV_SITE.exists():
        site = str(VENV_SITE.resolve())
        if site not in sys.path:
            sys.path.insert(0, site)
        return True
    return False


def venv_python() -> Path | None:
    if VENV_PYTHON.exists():
        return VENV_PYTHON
    return None


def ensure_venv_message() -> str:
    return (
        "未发现 skill 内置依赖。请先运行:\n"
        f"  python scripts/install_skill_deps.py --full  # 或仅核心依赖: 不加 --full"
    )
