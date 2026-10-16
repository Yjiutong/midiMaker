#!/usr/bin/env python3
"""fetch_virtual_singer_samples.py - 抓取公开可用的虚拟歌姬示例音频。

只抓取清单里明确标注为公开许可/演示用途的样本，默认跳过已下载文件。

CLI:
  python scripts/fetch_virtual_singer_samples.py
  python scripts/fetch_virtual_singer_samples.py --out samples/virtual_singer --force
  python scripts/fetch_virtual_singer_samples.py --manifest assets/virtual_singer_sources.json
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "assets" / "virtual_singer_sources.json"


def _suffix_from_url(url):
    path = urllib.parse.urlparse(url).path
    suffix = Path(path).suffix.lower()
    return suffix if suffix in (".wav", ".mp3", ".flac", ".ogg", ".m4a") else ".wav"


def _download(url, out_path):
    req = urllib.request.Request(
        url, headers={
            "User-Agent": "midiMaker-skill/1.0",
            "Accept": "*/*",
        })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return len(data)


def main():
    ap = argparse.ArgumentParser(description="抓取虚拟歌姬示例音频")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--out", default="samples/virtual_singer")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"清单不存在: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sources = manifest.get("sources", [])
    if args.limit:
        sources = sources[:args.limit]

    downloaded = []
    for src in sources:
        url = src.get("url")
        if not url:
            continue
        file_name = src.get("file") or f"{src.get('id') or 'sample'}{_suffix_from_url(url)}"
        dest = out / file_name
        if dest.exists() and not args.force:
            print(f"[fetch] 已存在: {dest}")
            downloaded.append({"id": src.get("id"), "file": file_name,
                               "skipped": True})
            continue
        try:
            size = _download(url, dest)
        except Exception as e:
            print(f"[fetch] 下载失败 {url}: {e}", file=sys.stderr)
            continue
        rec = {"id": src.get("id"), "file": file_name, "bytes": size,
               "url": url, "kind": src.get("kind"), "license": src.get("license"),
               "name": src.get("name"), "notes": src.get("notes")}
        downloaded.append(rec)
        print(f"[fetch] 已下载 {dest} ({size} bytes)")

    if downloaded:
        (out / "sources.json").write_text(
            json.dumps({"manifest_version": manifest.get("version", 1),
                        "downloaded": downloaded},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"[fetch] 元数据写入 {out / 'sources.json'}")


if __name__ == "__main__":
    main()
