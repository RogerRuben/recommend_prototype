# -*- coding: utf-8 -*-
"""Small stdlib-only health/port probe used by the Windows launchers."""
from __future__ import print_function

import argparse
import json
import socket
import sys
try:
    from urllib.request import urlopen
except ImportError:  # pragma: no cover - Python 2 bootstrap compatibility
    from urllib2 import urlopen


def check(host, port, expected_service, timeout=1.0):
    occupied = False
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        occupied = sock.connect_ex((host, port)) == 0
    finally:
        sock.close()
    if not occupied:
        return 1, "not listening"
    try:
        response = urlopen("http://%s:%s/health" % (host, port), timeout=timeout)
        payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return 2, "port is occupied but /health is unavailable: %s" % exc
    actual = str(payload.get("service") or payload.get("service_name") or "")
    if actual != expected_service:
        return 2, "port is occupied by %r, expected %r" % (actual or "unknown service", expected_service)
    return 0, "ready"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--service", required=True)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    code, message = check(args.host, args.port, args.service)
    if not args.quiet:
        print("[%s] %s:%s %s: %s" % ("OK" if code == 0 else "ERROR", args.host, args.port, args.service, message))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
