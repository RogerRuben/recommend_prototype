# -*- coding: utf-8 -*-
"""Launch the recommendation system and Cloudflare Tunnel as one foreground job.

Quick mode creates a temporary trycloudflare.com URL. Token mode runs a
remotely-managed tunnel configured in the Cloudflare dashboard.

The launcher uses only the Python standard library so it can accompany the
existing recommendation package without adding pip dependencies.
"""
from __future__ import print_function

import argparse
import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
try:
    from urllib.request import urlopen
except ImportError:  # pragma: no cover
    from urllib2 import urlopen

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
LOGS = ROOT / "logs"
URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.I)


class DemoLauncher(object):
    def __init__(self, args):
        self.args = args
        self.app_process = None
        self.tunnel_process = None
        self.stop_requested = False
        self.public_url = None
        self.port = None
        self.state_path = RUNTIME / "cloudflare_demo.json"
        self.app_log_path = LOGS / "cloudflare_app.log"
        self.tunnel_log_path = LOGS / "cloudflare_tunnel.log"
        RUNTIME.mkdir(exist_ok=True)
        LOGS.mkdir(exist_ok=True)

    def find_cloudflared(self):
        candidates = []
        if self.args.cloudflared:
            candidates.append(Path(self.args.cloudflared))
        env_path = os.environ.get("CLOUDFLARED_EXE")
        if env_path:
            candidates.append(Path(env_path))
        candidates.extend([
            ROOT / "deploy" / "cloudflare" / ("cloudflared.exe" if os.name == "nt" else "cloudflared"),
            ROOT / ("cloudflared.exe" if os.name == "nt" else "cloudflared"),
        ])
        found = shutil.which("cloudflared")
        if found:
            candidates.append(Path(found))
        for candidate in candidates:
            if candidate and candidate.is_file():
                return str(candidate.resolve())
        raise RuntimeError(
            "未找到cloudflared。Windows请先运行 INSTALL_CLOUDFLARED_WINDOWS.bat；"
            "Linux请安装cloudflared，或设置CLOUDFLARED_EXE。"
        )

    def resolve_token(self):
        token = os.environ.get("CLOUDFLARE_TUNNEL_TOKEN", "").strip()
        if token:
            return token
        token_file = Path(self.args.token_file) if self.args.token_file else ROOT / "deploy" / "cloudflare" / "tunnel_token.txt"
        if token_file.is_file():
            token = token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise RuntimeError(
                "稳定隧道缺少Token。请设置CLOUDFLARE_TUNNEL_TOKEN，或将Token写入"
                " deploy/cloudflare/tunnel_token.txt。不要把Token提交到公共仓库。"
            )
        return token

    def start_app(self):
        last_port = RUNTIME / "last_port.txt"
        running = RUNTIME / "running.json"
        for path in (last_port, running):
            try:
                path.unlink()
            except OSError:
                pass
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["IPDEMO_OPEN_BROWSER"] = "0"
        env["IPDEMO_AUTH_ENABLED"] = "1"
        env["IPDEMO_AUTH_USERNAME"] = self.args.username
        env["IPDEMO_AUTH_PASSWORD"] = self.args.password
        if not self.args.read_write:
            env["IPDEMO_DEMO_READ_ONLY"] = "1"
            env.pop("IPDEMO_DISABLE_ADMIN", None)
        command = [
            sys.executable, str(ROOT / "run_app.py"),
            "--host", "127.0.0.1",
            "--port", str(self.args.port),
            "--port-span", str(self.args.port_span),
            "--no-browser",
        ]
        app_log = open(str(self.app_log_path), "w", encoding="utf-8")
        self.app_process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=app_log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + self.args.startup_timeout
        while time.time() < deadline:
            if self.app_process.poll() is not None:
                raise RuntimeError("推荐系统启动失败，请查看 %s" % self.app_log_path)
            if last_port.is_file():
                try:
                    self.port = int(last_port.read_text(encoding="ascii").strip())
                    with urlopen("http://127.0.0.1:%d/api/health" % self.port, timeout=2) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                    if payload.get("status") == "ok":
                        return
                except Exception:
                    pass
            time.sleep(0.3)
        raise RuntimeError("推荐系统在%d秒内未就绪，请查看 %s" % (self.args.startup_timeout, self.app_log_path))

    def _read_tunnel_output(self, stream, log_file):
        for line in iter(stream.readline, ""):
            if not line:
                break
            log_file.write(line)
            log_file.flush()
            clean = line.rstrip()
            print(clean)
            match = URL_PATTERN.search(line)
            if match and not self.public_url:
                self.public_url = match.group(0)
                self.write_state()
                print("\n" + "=" * 72)
                print("Cloudflare演示地址：%s" % self.public_url)
                print("当前模式：%s" % ("登录后可写公开模式（不推荐）" if self.args.read_write else "登录后全站可见、服务器端只读"))
                print("演示账号：%s" % self.args.username)
                print("演示密码：%s" % self.args.password)
                print("按 Ctrl+C 可同时关闭推荐系统和隧道。")
                print("=" * 72 + "\n")
                if self.args.open_browser:
                    try:
                        webbrowser.open(self.public_url)
                    except Exception:
                        pass

    def start_tunnel(self):
        cloudflared = self.find_cloudflared()
        if self.args.mode == "quick":
            command = [
                cloudflared, "tunnel", "--no-autoupdate",
                "--url", "http://127.0.0.1:%d" % self.port,
            ]
        else:
            token = self.resolve_token()
            command = [cloudflared, "tunnel", "--no-autoupdate", "run", "--token", token]
        env = os.environ.copy()
        self.tunnel_process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
        )
        tunnel_log = open(str(self.tunnel_log_path), "w", encoding="utf-8")
        reader = threading.Thread(target=self._read_tunnel_output, args=(self.tunnel_process.stdout, tunnel_log))
        reader.daemon = True
        reader.start()
        if self.args.mode == "quick":
            deadline = time.time() + self.args.tunnel_timeout
            while time.time() < deadline and not self.public_url:
                if self.tunnel_process.poll() is not None:
                    raise RuntimeError("Cloudflare隧道启动失败，请查看 %s" % self.tunnel_log_path)
                time.sleep(0.2)
            if not self.public_url:
                raise RuntimeError("未在%d秒内获得trycloudflare.com地址，请查看 %s" % (self.args.tunnel_timeout, self.tunnel_log_path))
        else:
            print("稳定Cloudflare Tunnel已启动。公开域名由Cloudflare控制台中的Public Hostname决定。")
            self.write_state()
        return reader, tunnel_log

    def write_state(self):
        payload = {
            "mode": self.args.mode,
            "public_url": self.public_url,
            "local_url": "http://127.0.0.1:%d" % self.port if self.port else None,
            "port": self.port,
            "read_only": not self.args.read_write,
            "auth_enabled": True,
            "username": self.args.username,
            "app_pid": self.app_process.pid if self.app_process else None,
            "tunnel_pid": self.tunnel_process.pid if self.tunnel_process else None,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def stop(self):
        if self.stop_requested:
            return
        self.stop_requested = True
        for process in (self.tunnel_process, self.app_process):
            if process is None or process.poll() is not None:
                continue
            try:
                process.terminate()
            except Exception:
                pass
        deadline = time.time() + 5
        for process in (self.tunnel_process, self.app_process):
            if process is None:
                continue
            while process.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if process.poll() is None:
                try:
                    process.kill()
                except Exception:
                    pass
        try:
            self.state_path.unlink()
        except OSError:
            pass

    def run(self):
        print("正在启动推荐系统……")
        self.start_app()
        print("本地推荐系统已就绪：http://127.0.0.1:%d" % self.port)
        reader, tunnel_log = self.start_tunnel()
        self.write_state()
        try:
            while True:
                if self.app_process.poll() is not None:
                    raise RuntimeError("推荐系统进程已退出，请查看 %s" % self.app_log_path)
                if self.tunnel_process.poll() is not None:
                    raise RuntimeError("Cloudflare隧道进程已退出，请查看 %s" % self.tunnel_log_path)
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n正在关闭Cloudflare演示和推荐系统……")
        finally:
            tunnel_log.close()
            self.stop()


def build_parser():
    parser = argparse.ArgumentParser(description="一键启动推荐系统和Cloudflare Tunnel")
    parser.add_argument("--mode", choices=("quick", "token"), default="quick")
    parser.add_argument("--cloudflared", default="")
    parser.add_argument("--token-file", default="")
    parser.add_argument("--port", type=int, default=17891)
    parser.add_argument("--port-span", type=int, default=10)
    parser.add_argument("--startup-timeout", type=int, default=40)
    parser.add_argument("--tunnel-timeout", type=int, default=45)
    parser.add_argument("--open-browser", action="store_true")
    parser.add_argument("--read-write", action="store_true", help="登录后允许数据库写入与方案保存；风险较高，不建议用于Quick Tunnel")
    parser.add_argument("--username", default=os.environ.get("IPDEMO_AUTH_USERNAME", "ab123"), help="演示登录账号")
    parser.add_argument("--password", default=os.environ.get("IPDEMO_AUTH_PASSWORD", "ab123"), help="演示登录密码")
    return parser


def main():
    args = build_parser().parse_args()
    launcher = DemoLauncher(args)
    atexit.register(launcher.stop)
    try:
        launcher.run()
        return 0
    except Exception as exc:
        print("[ERROR] %s" % exc)
        launcher.stop()
        return 1


if __name__ == "__main__":
    sys.exit(main())
