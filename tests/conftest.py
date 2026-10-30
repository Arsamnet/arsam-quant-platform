"""Global deterministic test configuration."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolate_fx_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent operator/runtime FX_* variables from contaminating deterministic tests."""
    for name in tuple(os.environ):
        if name.upper().startswith("FX_"):
            monkeypatch.delenv(name, raising=False)


@pytest.fixture
def anyio_backend() -> str:
    """Run ASGI tests on the standard-library asyncio backend only."""
    return "asyncio"
