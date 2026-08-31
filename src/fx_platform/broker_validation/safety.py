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


def _strip_comments_and_strings(source: str) -> str:
    def replace_non_code(match: re.Match[str]) -> str:
        value = match.group(0)
        return "\n" * value.count("\n") + " " * (len(value) - value.count("\n"))

    return _NON_CODE.sub(replace_non_code, source)
