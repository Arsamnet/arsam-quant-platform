#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/ and rerun." >&2
  exit 1
fi

uv sync --locked --all-extras
uv run pre-commit install
echo "Bootstrap complete. Copy .env.example to .env only when local overrides are needed."
