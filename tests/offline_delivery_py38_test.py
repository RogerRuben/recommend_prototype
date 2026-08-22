# -*- coding: utf-8 -*-
"""Offline customer package must be deterministic, no-index and model-compatible."""
from __future__ import print_function

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.build_offline_delivery_py38 import requirement_names, validate_wheelhouse  # noqa: E402


def main():
    requirements = ROOT / "requirements_offline_py38.txt"
    names = requirement_names(requirements)
    assert names == [
        "numpy", "scipy", "pandas", "scikit_learn", "joblib", "threadpoolctl",
        "openpyxl", "et_xmlfile", "python_dateutil", "pytz", "six",
    ]
    manifest = json.loads((ROOT / "services/price_service/model/price_native_bundle.pkl.manifest.json").read_text(encoding="utf-8"))
    training = manifest["training_environment"]
    locked = requirements.read_text(encoding="utf-8")
    assert "numpy==%s" % training["numpy"] in locked
    assert "scikit-learn==%s" % training["scikit_learn"] in locked
    assert "joblib==%s" % training["joblib"] in locked
    assert "xgboost" not in locked.lower()

    with tempfile.TemporaryDirectory(prefix="offline_wheels_", dir=str(ROOT)) as folder:
        wheelhouse = Path(folder)
        binary = {"numpy", "scipy", "pandas", "scikit_learn"}
        for name in names:
            tag = "cp38-cp38-win_amd64" if name in binary else "py3-none-any"
            (wheelhouse / ("%s-1.0-%s.whl" % (name, tag))).write_bytes(b"wheel")
        wheels = validate_wheelhouse(wheelhouse, requirements)
        assert len(wheels) == len(names)

    installer = (ROOT / "INSTALL_OFFLINE_RUNTIME_WIN7.bat").read_text(encoding="utf-8")
    starter = (ROOT / "START_OFFLINE_WIN7.bat").read_text(encoding="utf-8")
    builder = (ROOT / "tools/build_offline_delivery_py38.py").read_text(encoding="utf-8")
    assert "--no-index" in installer and "--find-links" in installer
    assert "sys.version_info[:2]==(3,8)" in installer
    assert "--smoke-current-models" in installer
    assert "START_ALL_SERVICES_WIN7.bat" in starter
    assert "runtime / \"service_runtime.local.bat\"" in builder
    assert "PRICE_SERVICE_PYTHON=%~dp0python38" in builder
    assert 'pth_lines.insert(1, "..\\\\..")' in builder
    assert "IPDemo_V21_1_1_Offline_" in builder
    prepare = (ROOT / "tools/prepare_embedded_python38.py").read_text(encoding="utf-8")
    assert "--no-index" in prepare and "--ignore-installed" in prepare
    start_all = (ROOT / "START_ALL_SERVICES_WIN7.bat").read_text(encoding="utf-8")
    assert "runtime\\python38\\python.exe" in start_all
    assert "path is too long" in start_all
    print("PASS offline CPython 3.8 delivery contracts")


if __name__ == "__main__":
    main()
