"""Global deterministic test configuration."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run ASGI tests on the standard-library asyncio backend only."""
    return "asyncio"
