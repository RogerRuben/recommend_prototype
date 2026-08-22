# -*- coding: utf-8 -*-
"""Verify every file in an extracted V21.1.1 offline delivery package."""
from __future__ import print_function

import argparse
import hashlib
import json
import sys
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_package(root):
    root = Path(root).resolve()
    manifest_path = root / "OFFLINE_PACKAGE_MANIFEST.json"
    errors = []
    if not manifest_path.is_file():
        return {"status": "FAIL", "root": str(root), "errors": ["OFFLINE_PACKAGE_MANIFEST.json is missing"]}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"status": "FAIL", "root": str(root), "errors": ["Package manifest cannot be read: %s" % exc]}
    if manifest.get("format_version") != "industrial-offline-delivery-1.0":
        errors.append("Unsupported package format: %s" % manifest.get("format_version"))
    for item in manifest.get("files") or []:
        relative = str(item.get("path") or "")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append("Unsafe manifest path: %s" % relative)
            continue
        if not path.is_file():
            errors.append("Missing file: %s" % relative)
            continue
        actual_size = path.stat().st_size
        expected_size = item.get("size")
        if expected_size is None or actual_size != int(expected_size):
            errors.append("Size mismatch: %s" % relative)
            continue
        if file_sha256(path).lower() != str(item.get("sha256") or "").lower():
            errors.append("SHA-256 mismatch: %s" % relative)
    required = [
        "START_OFFLINE_WIN7.bat", "INSTALL_OFFLINE_RUNTIME_WIN7.bat",
        "START_ALL_SERVICES_WIN7.bat", "requirements_offline_py38.txt",
        "services/price_service/model/price_native_bundle.pkl",
        "services/effectiveness_service/model/current/effectiveness_runtime_manifest.json",
        "data/protocol_demo.db",
    ]
    for relative in required:
        if not (root / relative).is_file():
            errors.append("Required delivery file is missing: %s" % relative)
    wheels = list((root / "wheelhouse_win7_py38").glob("*.whl"))
    if not wheels:
        errors.append("Offline wheelhouse is empty")
    return {
        "status": "PASS" if not errors else "FAIL",
        "root": str(root),
        "file_count": len(manifest.get("files") or []),
        "wheel_count": len(wheels),
        "target": manifest.get("target"),
        "errors": errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    report = verify_package(args.root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
