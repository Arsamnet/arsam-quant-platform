"""Non-sensitive configuration check for the interactive Windows demo node."""

import argparse
import sys
from collections.abc import Sequence

from fx_platform import __version__
from fx_platform.config import Settings


def main(argv: Sequence[str] | None = None) -> None:
    """Validate startup settings and print only reviewed, non-secret state."""
    parser = argparse.ArgumentParser(description="Validate guarded demo-node configuration")
    parser.add_argument("--health-url", action="store_true")
    arguments = parser.parse_args(argv)
    settings = Settings()
    if arguments.health_url:
        sys.stdout.write(f"http://{settings.bind_host}:{settings.bind_port}\n")
        return
    lines = [
        f"PLATFORM VERSION: {__version__}",
        f"TRADING MODE: {settings.trading_mode.value.upper()}",
        "EXECUTION SWITCH: " + ("ENABLED" if settings.demo_execution_enabled else "DISABLED"),
        "LIVE MODE: FORBIDDEN",
        f"API: {settings.bind_host}:{settings.bind_port}",
        f"NODE: {settings.active_node_id}",
    ]
    if settings.demo_execution_enabled:
        lines.extend(
            (
                f"DEMO MAX VOLUME: {settings.demo_max_volume}",
                f"DEMO MAX OPEN POSITIONS: {settings.demo_max_open_positions}",
            )
        )
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
