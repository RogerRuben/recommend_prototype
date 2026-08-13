#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export IPDEMO_AUTH_USERNAME="${IPDEMO_AUTH_USERNAME:-ab123}"
export IPDEMO_AUTH_PASSWORD="${IPDEMO_AUTH_PASSWORD:-ab123}"
exec "$PYTHON_BIN" tools/cloudflare_demo_launcher.py --mode quick
