# -*- coding: utf-8 -*-
from __future__ import print_function
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "runtime" / "cloudflare_demo.json"


def stop_pid(pid):
    if not pid:
        return
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return
    if os.name == "nt":
        subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def main():
    if not STATE.is_file():
        print("未找到正在运行的Cloudflare演示状态文件。")
        return 0
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    stop_pid(data.get("tunnel_pid"))
    stop_pid(data.get("app_pid"))
    try:
        STATE.unlink()
    except OSError:
        pass
    print("已尝试关闭Cloudflare隧道和推荐系统。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
