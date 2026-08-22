# -*- coding: utf-8 -*-
"""Build a single offline ZIP for a Windows x64 customer with Python 3.8."""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_offline_package import verify_package  # noqa: E402
from tools.wheelhouse_manifest import build_manifest as build_wheelhouse_manifest  # noqa: E402


SOURCE_DIRECTORIES = ("app", "config", "data", "data_master", "models", "services", "tools", "docs")
EXCLUDED_DIRS = {
    ".git", ".pytest_cache", "__pycache__", "node_modules", "logs", "backups",
    "runtime", "runtime_state", "wheelhouse_win7", "wheelhouse_win7_py38",
    "deliverables", "outputs", "dist", ".venv", "venv",
}
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".log", ".tmp", ".bak", ".rar")
ROOT_FILES = {
    "README.md", "VERSION.txt", "requirements.txt", "requirements_offline_py38.txt", "run_app.py",
    "CHECK_ENVIRONMENT.bat", "CHECK_MODEL_SERVICES.bat", "VERIFY_MODEL_ENVIRONMENTS.bat",
    "START_PRICE_SERVICE_WIN7.bat", "START_EFFECTIVENESS_SERVICE_WIN7.bat",
    "START_ALL_SERVICES_WIN7.bat", "START_RECOMMENDATION_WITH_SERVICES_WIN7.bat",
    "START_ALL_NO_BROWSER.bat", "INSTALL_OFFLINE_RUNTIME_WIN7.bat", "START_OFFLINE_WIN7.bat",
}


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _excluded(path):
    return (
        any(part in EXCLUDED_DIRS for part in path.parts)
        or (path.name.startswith("service_portal.") and ".bak." in path.name)
        or path.suffix.lower() in EXCLUDED_SUFFIXES
    )


def _copy_tree(source, destination):
    for current, directories, files in os.walk(str(source)):
        current_path = Path(current)
        directories[:] = [name for name in directories if name not in EXCLUDED_DIRS]
        relative_dir = current_path.relative_to(source)
        for name in files:
            path = current_path / name
            relative = relative_dir / name
            if _excluded(relative):
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(path), str(target))


def requirement_names(requirements_path):
    names = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(re.split(r"[<>=!~\[]", line, 1)[0].strip().lower().replace("-", "_"))
    return names


def validate_wheelhouse(wheelhouse, requirements_path):
    wheelhouse = Path(wheelhouse).resolve()
    if not wheelhouse.is_dir():
        raise ValueError("Offline wheelhouse does not exist: %s" % wheelhouse)
    wheel_names = [path.name.lower().replace("-", "_") for path in wheelhouse.glob("*.whl")]
    missing = []
    for name in requirement_names(requirements_path):
        if not any(filename.startswith(name + "_") for filename in wheel_names):
            missing.append(name)
    if missing:
        raise ValueError("Offline wheelhouse is missing required packages: %s" % ", ".join(missing))
    for binary_name in ("numpy", "scipy", "pandas", "scikit_learn"):
        matches = [filename for filename in wheel_names if filename.startswith(binary_name + "_")]
        if matches and not any("cp38" in filename and "win_amd64" in filename for filename in matches):
            raise ValueError("%s wheel is not CPython 3.8 / win_amd64" % binary_name)
    return sorted(wheelhouse.glob("*.whl"), key=lambda path: path.name.lower())


def _manifest_files(stage):
    result = []
    for path in sorted(stage.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file() or path.name == "OFFLINE_PACKAGE_MANIFEST.json":
            continue
        result.append({
            "path": path.relative_to(stage).as_posix(),
            "size": path.stat().st_size,
            "sha256": file_sha256(path),
        })
    return result


def build_delivery(wheelhouse, output, package_name=None):
    requirements = ROOT / "requirements_offline_py38.txt"
    wheels = validate_wheelhouse(wheelhouse, requirements)
    output = Path(output).resolve()
    if output == ROOT or ROOT in output.parents and output.name in ("app", "services", "data", "config"):
        raise ValueError("Refusing unsafe output directory: %s" % output)
    package_name = package_name or "IndustrialProtocol_V21_1_1_Offline_Py38_Win64_%s" % datetime.now().strftime("%Y%m%d")
    stage = output / package_name
    zip_path = output / (package_name + ".zip")
    hash_path = output / (package_name + ".zip.sha256")
    output.mkdir(parents=True, exist_ok=True)
    for target in (stage,):
        if target.exists():
            shutil.rmtree(str(target))
    for target in (zip_path, hash_path):
        if target.exists():
            target.unlink()
    stage.mkdir(parents=True)

    for name in SOURCE_DIRECTORIES:
        source = ROOT / name
        if source.is_dir():
            _copy_tree(source, stage / name)
    for name in ROOT_FILES:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(str(source), str(stage / name))

    packaged_wheels = stage / "wheelhouse_win7_py38"
    packaged_wheels.mkdir()
    for wheel in wheels:
        shutil.copy2(str(wheel), str(packaged_wheels / wheel.name))
    wheel_manifest = build_wheelhouse_manifest(packaged_wheels)
    (packaged_wheels / "WHEELHOUSE_MANIFEST.json").write_text(
        json.dumps(wheel_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    runtime = stage / "runtime"
    runtime.mkdir(exist_ok=True)
    (runtime / "service_runtime.local.bat").write_text(
        "@echo off\r\n"
        "set \"PRICE_SERVICE_PYTHON=%~dp0venvs\\offline_py38\\Scripts\\python.exe\"\r\n"
        "set \"EFFECT_SERVICE_PYTHON=%~dp0venvs\\offline_py38\\Scripts\\python.exe\"\r\n"
        "set \"MAIN_APP_PYTHON=%~dp0venvs\\offline_py38\\Scripts\\python.exe\"\r\n",
        encoding="ascii",
    )
    (runtime / ".keep").write_text("Offline runtime is created on the target machine.\n", encoding="ascii")

    manifest = {
        "format_version": "industrial-offline-delivery-1.0",
        "release": "V21.1.1",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "package_name": package_name,
        "target": {"os": "Windows 7 or later x64", "python": "CPython 3.8 x64", "network_required": False},
        "entrypoint": "START_OFFLINE_WIN7.bat",
        "installer": "INSTALL_OFFLINE_RUNTIME_WIN7.bat",
        "wheel_count": len(wheels),
        "model_policy": "native price model only; no silent fallback",
        "files": _manifest_files(stage),
    }
    (stage / "OFFLINE_PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = verify_package(stage)
    if report["status"] != "PASS":
        raise RuntimeError("Staged package verification failed: %s" % report["errors"])

    with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(stage.rglob("*"), key=lambda item: str(item).lower()):
            if path.is_file():
                archive.write(str(path), path.relative_to(stage).as_posix())
    with zipfile.ZipFile(str(zip_path), "r") as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError("ZIP integrity check failed at %s" % corrupt)
        if "OFFLINE_PACKAGE_MANIFEST.json" not in archive.namelist():
            raise RuntimeError("ZIP does not contain OFFLINE_PACKAGE_MANIFEST.json")
    zip_hash = file_sha256(zip_path)
    hash_path.write_text("%s  %s\n" % (zip_hash, zip_path.name), encoding="ascii")
    return {
        "package": str(zip_path), "sha256_file": str(hash_path), "sha256": zip_hash,
        "stage": str(stage), "size_bytes": zip_path.stat().st_size,
        "wheel_count": len(wheels), "file_count": len(manifest["files"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--package-name")
    args = parser.parse_args(argv)
    try:
        result = build_delivery(args.wheelhouse, args.output, args.package_name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print("[FAIL] %s" % exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
