# -*- coding: utf-8 -*-
"""Build one V22 ZIP with a single Python 3.8/sklearn 0.24.1 runtime."""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_offline_delivery_py38 import _copy_tree  # noqa: E402


SOURCE_DIRECTORIES = (
    "app", "config", "cost_effectiveness_analysis", "data", "data_master",
    "docs", "models", "services", "tools",
)
ROOT_FILES = (
    "README.md", "VERSION.txt", "requirements.txt",
    "requirements_field_py38_sklearn0241.txt", "requirements_offline_py38.txt",
    "run_app.py", "CHECK_RUNTIME.bat", "CHECK_ENVIRONMENT.bat",
    "CHECK_MODEL_SERVICES.bat", "START_ALL_SERVICES_WIN7.bat",
    "START_ALL_NO_BROWSER.bat", "START_PRICE_SERVICE_WIN7.bat",
    "START_EFFECTIVENESS_SERVICE_WIN7.bat",
    "START_COST_EFFECTIVENESS_ANALYSIS_WIN7.bat",
    "START_RECOMMENDATION_WITH_SERVICES_WIN7.bat",
)
MAX_ZIP_BYTES = 100 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_pth(runtime):
    path = Path(runtime) / "python38._pth"
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    lines = [line for line in lines if line.strip() != "..\\.."]
    lines.insert(1, "..\\..")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_runtime(source, destination):
    """Copy a relocatable runtime without package test/cache trees."""
    source, destination = Path(source).resolve(), Path(destination)
    excluded = {"test", "tests", "__pycache__", ".pytest_cache"}
    for current, directories, files in os.walk(str(source)):
        current_path = Path(current)
        directories[:] = [name for name in directories if name.lower() not in excluded]
        relative = current_path.relative_to(source)
        for name in files:
            if name.lower().endswith((".pyc", ".pyo", ".log")):
                continue
            target = destination / relative / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(current_path / name), str(target))


def manifest_files(stage):
    result = []
    for path in sorted(stage.rglob("*"), key=lambda item: str(item).lower()):
        if path.is_file() and path.name != "DELIVERY_MANIFEST.json":
            result.append({
                "path": path.relative_to(stage).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            })
    return result


def build(field_runtime, output, package_name):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = output / package_name
    zip_path = output / (package_name + ".zip")
    if stage.exists():
        shutil.rmtree(str(stage))
    if zip_path.exists():
        zip_path.unlink()
    stage.mkdir()
    for name in SOURCE_DIRECTORIES:
        source = ROOT / name
        if source.is_dir():
            _copy_tree(source, stage / name)
    for name in ROOT_FILES:
        source = ROOT / name
        if source.is_file():
            shutil.copy2(str(source), str(stage / name))

    runtime = stage / "runtime"
    copy_runtime(field_runtime, runtime / "python38")
    configure_pth(runtime / "python38")
    (runtime / "service_runtime.local.bat").write_text(
        "@echo off\r\n"
        "set \"MAIN_APP_PYTHON=%~dp0python38\\python.exe\"\r\n"
        "set \"EFFECT_SERVICE_PYTHON=%~dp0python38\\python.exe\"\r\n"
        "set \"COST_EFFECTIVENESS_PYTHON=%~dp0python38\\python.exe\"\r\n"
        "set \"PRICE_SERVICE_PYTHON=%~dp0python38\\python.exe\"\r\n",
        encoding="ascii",
    )
    (stage / "DELIVERY_README.txt").write_text(
        "V22 Lock V17 ready-to-run delivery\n\n"
        "1. Extract this single ZIP to a short path such as D:\\ParameterDesignV22.\n"
        "2. Run CHECK_RUNTIME.bat; it must report PASS.\n"
        "3. Double-click START_ALL_SERVICES_WIN7.bat.\n"
        "4. Portal: http://127.0.0.1:7003/portal\n"
        "   Price: 18101; Effectiveness: 18102; Cost-effectiveness: 17000.\n\n"
        "All four services, especially the price service: CPython 3.8.10 + scikit-learn 0.24.1.\n",
        encoding="utf-8",
    )
    check = subprocess.run(
        [str((runtime / "python38" / "python.exe").resolve()),
         str((stage / "tools" / "verify_field_runtime.py").resolve())],
        cwd=str(stage), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    if check.returncode != 0:
        raise RuntimeError("Staged runtime verification failed:\n%s" % check.stdout)
    manifest = {
        "format_version": "parameter-design-v22-py38-sklearn0241-1.0",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "package_name": package_name,
        "entrypoint": "START_ALL_SERVICES_WIN7.bat",
        "services": {"portal": 7003, "price": 18101, "effectiveness": 18102, "cost_effectiveness": 17000},
        "runtime": {"python": "3.8.10", "scikit_learn": "0.24.1", "used_by": ["portal", "price", "effectiveness", "cost_effectiveness"]},
        "files": manifest_files(stage),
    }
    (stage / "DELIVERY_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for path in sorted(stage.rglob("*"), key=lambda item: str(item).lower()):
            if path.is_file():
                archive.write(str(path), path.relative_to(stage).as_posix())
    with zipfile.ZipFile(str(zip_path), "r") as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise RuntimeError("ZIP integrity failed: %s" % corrupt)
    if zip_path.stat().st_size >= MAX_ZIP_BYTES:
        raise RuntimeError("单个ZIP达到%.2f MiB，必须先精简，禁止分卷" % (zip_path.stat().st_size / 1024.0 / 1024.0))
    hashes = output / "SHA256SUMS.txt"
    hash_lines = ["%s  %s" % (sha256(zip_path), zip_path.name)]
    hashes.write_text("\n".join(hash_lines) + "\n", encoding="ascii")
    return {
        "stage": str(stage), "zip": str(zip_path), "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256(zip_path),
        "runtime_check": check.stdout,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--field-runtime", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--package-name", required=True)
    args = parser.parse_args(argv)
    result = build(args.field_runtime, args.output, args.package_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
