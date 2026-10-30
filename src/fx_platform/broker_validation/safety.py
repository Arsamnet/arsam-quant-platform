"""Defense-in-depth lexical scan for forbidden executable MQL5 trade APIs."""

import re
from pathlib import Path

_FORBIDDEN_PATTERNS = (
    re.compile(r"\bOrderSend(?:Async)?\s*\("),
    re.compile(r"\bCTrade\b"),
    re.compile(r"\b(?:Buy|Sell|PositionOpen|PositionClose|OrderDelete|OrderModify)\s*\("),
)
_MAX_PROBE_BYTES = 1_000_000
_NON_CODE = re.compile(
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/',
    re.DOTALL,
)


def forbidden_trade_api_matches(source: str) -> tuple[str, ...]:
    """Return forbidden executable tokens after removing comments and string literals."""
    executable = _strip_comments_and_strings(source)
    matches = {
        match.group(0).strip()
        for pattern in _FORBIDDEN_PATTERNS
        for match in pattern.finditer(executable)
    }
    return tuple(sorted(matches))


def scan_read_only_probe(path: Path) -> tuple[str, ...]:
    """Scan one bounded UTF-8 probe source; this is not formal verification."""
    if path.stat().st_size > _MAX_PROBE_BYTES:
        raise ValueError("MQL5 probe exceeds the one-megabyte scan limit")
    return forbidden_trade_api_matches(path.read_text(encoding="utf-8"))


def validate_mql5_execution_boundary(
    mt5_root: Path,
    allowed_execution_guard: Path,
) -> tuple[str, ...]:
    """Require exactly one reviewed OrderSend boundary and no trade API elsewhere."""
    violations: list[str] = []
    allowed_path = allowed_execution_guard.resolve()
    order_send_count = 0
    for path in sorted(mt5_root.rglob("*.mq5")):
        if path.stat().st_size > _MAX_PROBE_BYTES:
            violations.append(f"{path}: exceeds one-megabyte scan limit")
            continue
        matches = forbidden_trade_api_matches(path.read_text(encoding="utf-8"))
        if path.resolve() == allowed_path:
            order_send_matches = tuple(value for value in matches if value.startswith("OrderSend("))
            source = path.read_text(encoding="utf-8")
            order_send_count += len(
                _FORBIDDEN_PATTERNS[0].findall(_strip_comments_and_strings(source))
            )
            unexpected = tuple(value for value in matches if value not in order_send_matches)
            if unexpected:
                violations.append(f"{path}: unexpected trade APIs: {', '.join(unexpected)}")
        elif matches:
            violations.append(f"{path}: forbidden trade APIs: {', '.join(matches)}")
    if order_send_count != 1:
        violations.append(
            "reviewed execution guard must contain exactly one OrderSend call; "
            f"found {order_send_count}"
        )
    return tuple(violations)


def _strip_comments_and_strings(source: str) -> str:
    def replace_non_code(match: re.Match[str]) -> str:
        value = match.group(0)
        return "\n" * value.count("\n") + " " * (len(value) - value.count("\n"))

    return _NON_CODE.sub(replace_non_code, source)
