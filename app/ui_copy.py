"""Static UI copy for FR-12 (welcome, disclaimer, example questions)."""

from __future__ import annotations

# EC-UI-02 / FR-12 — persistent always-visible disclaimer.
DISCLAIMER = "Facts-only. No investment advice."

# EC-UI-01 — welcome with facts-only framing on first load.
WELCOME_MESSAGE = (
    "Welcome to the INDmoney MF FAQ chatbot for ICICI Prudential schemes.\n\n"
    "I answer **facts only** from approved public sources — expense ratio, exit load, "
    "minimum SIP, lock-in, riskometer, benchmark, and general MF definitions. "
    "I do **not** give investment advice, recommendations, or performance figures.\n\n"
    "Ask a question below, or try one of the examples."
)

# Architecture §7 / EC-UI-06 — real pipeline queries (scheme, general, comparison).
EXAMPLE_QUESTIONS: tuple[str, ...] = (
    "What is the expense ratio of ICICI Prudential Flexicap Fund?",
    "What is an exit load?",
    "Which of these 5 has the lowest expense ratio?",
)

# Shown in chat instead of raw user text when FR-11 fires (never echo PII).
PII_USER_PLACEHOLDER = "[Message not shown — personal information detected]"
