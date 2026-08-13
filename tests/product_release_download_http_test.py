# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import sys
import threading
from pathlib import Path

try:
    from http.server import ThreadingHTTPServer
    from urllib.request import urlopen
except ImportError:  # pragma: no cover - Python 2 compatibility is not used in delivery.
    from SocketServer import ThreadingMixIn
    from BaseHTTPServer import HTTPServer
    from urllib2 import urlopen

    class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.server import Handler


class _Releases(object):
    def get(self, release_id):
        return {
            "release_id": release_id,
            "product_code": "航空舱门锁",
            "data": {"products": [{"product_code": "航空舱门锁"}]},
        }


class _DataMaster(object):
    def export_snapshot(self, data):
        # The header failure happened before a real workbook body was written.
        return b"PK\x03\x04workbook-test"


class _App(object):
    auth_enabled = False
    auth_username = "admin"
    disable_admin = False
    product_releases = _Releases()
    data_master = _DataMaster()


class _QuietHandler(Handler):
    app = _App()

    def log_message(self, fmt, *args):
        return


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("PASS - " + message)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _QuietHandler)
    worker = threading.Thread(target=server.serve_forever)
    worker.daemon = True
    worker.start()
    try:
        url = "http://127.0.0.1:%d/api/admin/product-releases/maintenance/workbook?release_id=R-001" % server.server_port
        response = urlopen(url, timeout=10)
        try:
            body = response.read()
            lengths = response.headers.get_all("Content-Length")
            disposition = response.headers.get("Content-Disposition") or ""
            check(response.getcode() == 200 and body.startswith(b"PK\x03\x04"), "维护工作簿下载返回单个有效响应")
            check(lengths == [str(len(body))], "维护工作簿响应只包含一个Content-Length")
            disposition.encode("ascii")
            check("filename*=UTF-8''" in disposition and "%E8%88%AA" in disposition, "中文文件名使用ASCII安全的RFC5987响应头")
        finally:
            response.close()
        print(json.dumps({"status": "PASS", "checks": 3}, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


if __name__ == "__main__":
    main()
