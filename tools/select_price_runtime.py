# -*- coding: utf-8 -*-
"""Select the first Python interpreter that passes the real price-model smoke."""
from __future__ import print_function

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path


def candidate_pythons(root, environ=None, which=None):
    env = environ if environ is not None else os.environ
    find_python = which if which is not None else (lambda: shutil.which("python"))
    root = Path(root).resolve()
    raw = [
        env.get("PRICE_SERVICE_PYTHON"),
        str(root / "runtime" / "venvs" / "price_runtime" / "Scripts" / "python.exe"),
        str(root / "runtime" / "venvs" / "model_runtime38" / "Scripts" / "python.exe"),
        str(Path(env["CONDA_PREFIX"]) / "python.exe") if env.get("CONDA_PREFIX") else None,
        find_python(),
    ]
    result, seen = [], set()
    for value in raw:
        if not value:
            continue
        normalized = os.path.normcase(os.path.abspath(os.path.expandvars(value)))
        if normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return result


def select_runtime(root, model, candidates=None, runner=None):
    root = Path(root).resolve()
    probe = root / "tools" / "check_price_runtime.py"
    candidates = list(candidates if candidates is not None else candidate_pythons(root))
    run = runner if runner is not None else subprocess.run
    attempts = []
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if not path.is_file():
            attempts.append({"python": str(path), "ok": False, "output": "Interpreter not found"})
            continue
        completed = run(
            [str(path), str(probe), "--model", str(model)],
            cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        attempt = {"python": str(path.resolve()), "ok": completed.returncode == 0,
                   "output": completed.stdout or ""}
        attempts.append(attempt)
        if attempt["ok"]:
            return attempt["python"], attempts
    return None, attempts


def _write_report(path, selected, attempts):
    lines = ["Price service startup", "", "Started:",
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "", "Runtime candidates:"]
    for index, attempt in enumerate(attempts, 1):
        lines.extend([
            "", "[%d] %s" % (index, attempt["python"]),
            "Runtime smoke: %s" % ("PASS" if attempt["ok"] else "FAIL"),
            attempt["output"].rstrip(),
        ])
    if selected:
        lines.extend(["", "Selected Python:", selected, "", "Runtime smoke:", "PASS"])
    else:
        lines.extend(["", "Selected Python:", "None", "", "Runtime smoke:", "FAIL",
                      "", "Reason:", "No candidate Python can run the native price model."])
    Path(path).write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--model", required=True)
    parser.add_argument("--log", required=True)
    parser.add_argument("--result-file", required=True)
    args = parser.parse_args(argv)
    selected, attempts = select_runtime(args.root, args.model)
    _write_report(args.log, selected, attempts)
    result = Path(args.result_file)
    if not selected:
        if result.exists():
            result.unlink()
        return 1
    result.write_text(selected + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
