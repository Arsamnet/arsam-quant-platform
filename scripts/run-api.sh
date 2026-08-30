#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ "${FX_TRADING_MODE:-paper}" != "paper" ]; then
  echo "Only FX_TRADING_MODE=paper is supported." >&2
  exit 1
fi

exec uv run uvicorn fx_platform.api.main:app --host 127.0.0.1 --port 8000
