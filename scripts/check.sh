#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
uv run pre-commit run --all-files
