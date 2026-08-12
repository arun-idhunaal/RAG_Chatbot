"""In-scope and out-of-scope fact-type tags (Architecture §3.3)."""

from __future__ import annotations

FACT_TYPES: frozenset[str] = frozenset(
    {
        "expense_ratio",
        "exit_load",
        "min_sip",
        "lock_in",
        "riskometer",
        "benchmark",
        "statement_download",
    }
)

OUT_OF_SCOPE_FACT_TYPE = "out_of_scope"

# Keywords that indicate performance / returns content (EC-ING-05).
PERFORMANCE_KEYWORDS: tuple[str, ...] = (
    "cagr",
    "absolute return",
    "annualised return",
    "annualized return",
    "trailing return",
    "historical return",
    "returns vs",
    "vs benchmark",
    "versus benchmark",
    "outperform",
    "underperform",
    "1y return",
    "3y return",
    "5y return",
    "1 year return",
    "3 year return",
    "5 year return",
    "performance chart",
    "nav chart",
    "fund performance",
    "past performance",
)

# Patterns used to tag in-scope fact types on chunks.
FACT_TYPE_PATTERNS: dict[str, tuple[str, ...]] = {
    "expense_ratio": ("expense ratio", "total expense ratio", "ter", "expense ratio (direct)"),
    "exit_load": ("exit load", "exitload", "redemption load"),
    "min_sip": ("minimum sip", "min sip", "sip amount", "min. sip", "minimum investment"),
    "lock_in": ("lock-in", "lock in", "lockin", "elss lock"),
    "riskometer": ("riskometer", "risk-o-meter", "risk level", "very high risk", "high risk", "moderate risk"),
    "benchmark": ("benchmark", "benchmark index", "tracks the"),
    "statement_download": (
        "download statement",
        "account statement",
        "capital gain statement",
        "capital gains statement",
        "how to download",
    ),
}
