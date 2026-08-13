# -*- coding: utf-8 -*-
"""Create a deterministic SHA-256 manifest for an offline wheelhouse."""
from __future__ import print_function

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(wheelhouse):
    wheelhouse = Path(wheelhouse).resolve()
    if not wheelhouse.is_dir():
        raise ValueError("wheelhouse不存在: %s" % wheelhouse)
    files = []
    for path in sorted(wheelhouse.glob("*.whl"), key=lambda item: item.name.lower()):
        files.append({
            "name": path.name,
            "size": path.stat().st_size,
            "sha256": file_sha256(path),
        })
    if not files:
        raise ValueError("wheelhouse中没有whl文件: %s" % wheelhouse)
    return {
        "format_version": "industrial-offline-wheelhouse-1.0",
        "target": {
            "python": "3.8",
            "implementation": "CPython",
            "platform": "win_amd64",
        },
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "wheel_count": len(files),
        "total_size": sum(item["size"] for item in files),
        "files": files,
    }


def main():
    parser = argparse.ArgumentParser(description="生成离线wheelhouse摘要清单")
    parser.add_argument("--wheelhouse", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.wheelhouse)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output.resolve())


if __name__ == "__main__":
    main()
