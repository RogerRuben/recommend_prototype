#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
: "${IPDEMO_HOST:=127.0.0.1}"
: "${IPDEMO_PORT:=8080}"
exec python3 run_app.py --host "$IPDEMO_HOST" --port "$IPDEMO_PORT" --port-span 0 --no-browser
