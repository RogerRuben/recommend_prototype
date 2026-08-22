# -*- coding: utf-8 -*-
"""Build a relocatable CPython 3.8 runtime from the official embed package."""
from __future__ import print_function

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def prepare(archive, wheelhouse, output, requirements):
    archive = Path(archive).resolve()
    wheelhouse = Path(wheelhouse).resolve()
    output = Path(output).resolve()
    requirements = Path(requirements).resolve()
    if not archive.is_file():
        raise ValueError("Official Python embed archive is missing: %s" % archive)
    if not wheelhouse.is_dir():
        raise ValueError("Offline wheelhouse is missing: %s" % wheelhouse)
    if output.exists():
        shutil.rmtree(str(output))
    output.mkdir(parents=True)
    with zipfile.ZipFile(str(archive), "r") as source:
        source.extractall(str(output))
    pth = output / "python38._pth"
    if not pth.is_file() or not (output / "python.exe").is_file():
        raise ValueError("Archive is not the official CPython 3.8 embed x64 package")
    lines = pth.read_text(encoding="utf-8-sig").splitlines()
    normalized = [line for line in lines if line.strip() not in ("#import site", "import site", "Lib\\site-packages")]
    normalized.extend(["Lib\\site-packages", "import site"])
    pth.write_text("\n".join(normalized) + "\n", encoding="utf-8")
    site_packages = output / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    command = [
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-index", "--no-deps", "--only-binary=:all:", "--ignore-installed", "--no-compile",
        "--platform", "win_amd64", "--python-version", "3.8", "--implementation", "cp",
        "--abi", "cp38", "--target", str(site_packages), "--find-links", str(wheelhouse),
        "--requirement", str(requirements),
    ]
    subprocess.check_call(command, cwd=str(ROOT))
    subprocess.check_call([
        str(output / "python.exe"), str(ROOT / "tools" / "verify_model_environment.py"),
        "--profile", "runtime", "--smoke-current-models",
    ], cwd=str(ROOT))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--wheelhouse", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--requirements", default=str(ROOT / "requirements_offline_py38.txt"))
    args = parser.parse_args(argv)
    try:
        output = prepare(args.archive, args.wheelhouse, args.output, args.requirements)
        print("[PASS] Relocatable Python 3.8 runtime: %s" % output)
        return 0
    except Exception as exc:
        print("[FAIL] %s" % exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
