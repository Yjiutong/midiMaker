#!/usr/bin/env python3
"""build_local_virtual_singer_manifest.py - 扫描本地虚拟歌姬 MP3 目录并生成清单。

CLI:
  python scripts/build_local_virtual_singer_manifest.py \
      --dir "C:/Users/19105/Documents/GitHub/YunjiutongBlog/radio/music" \
      --out assets/virtual_singer_local_sources.json
"""

import argparse
import json
import re
import sys
from pathlib import Path


def _parse_filename(name):
    stem = name[:-4] if name.lower().endswith(".mp3") else name
    match = re.match(r"^(\d+)_(.*)$", stem)
    if match:
        number = int(match.group(1))
        body = match.group(2)
    else:
        number = None
        body = stem
    if "_" in body:
        artist, title = body.split("_", 1)
    else:
        artist = body
        title = ""
    return number, artist.strip(), title.strip()


def main():
    ap = argparse.ArgumentParser(description="扫描本地虚拟歌姬 MP3 目录")
    ap.add_argument("--dir", required=True, help="MP3 目录")
    ap.add_argument("--out", default="assets/virtual_singer_local_sources.json")
    args = ap.parse_args()

    root = Path(args.dir)
    if not root.exists():
        print(f"目录不存在: {root}", file=sys.stderr)
        sys.exit(1)
    files = sorted(root.rglob("*.mp3"))
    if not files:
        print(f"未发现 MP3 文件: {root}", file=sys.stderr)
        sys.exit(1)

    sources = []
    for p in files:
        n, artist, title = _parse_filename(p.name)
        sources.append({
            "id": f"local-vs-{p.stem}",
            "file": str(p.resolve()),
            "name": title or p.stem,
            "artist": artist,
            "track_index": n,
            "kind": "local-virtual-singer",
            "virtual_singer": True,
        })

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True) if out.parent != Path(".") else None
    data = {
        "version": 1,
        "directory": str(root.resolve()),
        "count": len(sources),
        "sources": sources,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[build_local] 发现 {len(sources)} 首 MP3，清单已写入: {out}")


if __name__ == "__main__":
    main()
