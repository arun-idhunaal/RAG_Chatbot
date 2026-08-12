"""PII detection gate (FR-11). Runs before classifier, retrieval, or logging."""

from __future__ import annotations

import re

from src.pipeline.models import PIICheckResult

# FR-11 refusal — fixed copy; never echo detected PII.
PII_REFUSAL_MESSAGE = (
    "I can't process messages that contain personal or sensitive information "
    "(such as PAN, Aadhaar, bank details, OTP, email, or phone numbers). "
    "Please ask a facts-only question without sharing personal details."
)

# Indian PAN: 5 letters + 4 digits + 1 letter (case-insensitive).
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)

# Aadhaar: 12 digits, optionally spaced (4-4-4).
_AADHAAR = re.compile(r"\b(?:\d{4}[\s-]?\d{4}[\s-]?\d{4}|\d{12})\b")

# Email addresses.
_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)

# Indian mobile: +91 optional, leading 6-9, 10 digits total.
_PHONE = re.compile(
    r"(?:\+91[\s-]?)?[6-9]\d{9}\b|"
    r"\b(?:\+91[\s-]?)?\(?[6-9]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"
)

# OTP-like: standalone 4–8 digit codes near OTP keywords.
_OTP_CONTEXT = re.compile(
    r"\b(?:otp|one[\s-]?time[\s-]?password|verification[\s-]?code)\b",
    re.IGNORECASE,
)
_OTP_CODE = re.compile(r"\b\d{4,8}\b")

# Bank / account numbers: 9–18 consecutive digits (conservative).
_ACCOUNT = re.compile(r"\b\d{9,18}\b")


def check_pii(message: str) -> PIICheckResult:
    """Return detected=True when PII is present; never log or echo the message."""
    if not message or not message.strip():
        return PIICheckResult(detected=False)

    text = message.strip()

    if _PAN.search(text):
        return PIICheckResult(detected=True, refusal_message=PII_REFUSAL_MESSAGE)
    if _AADHAAR.search(text):
        return PIICheckResult(detected=True, refusal_message=PII_REFUSAL_MESSAGE)
    if _EMAIL.search(text):
        return PIICheckResult(detected=True, refusal_message=PII_REFUSAL_MESSAGE)
    if _PHONE.search(text):
        return PIICheckResult(detected=True, refusal_message=PII_REFUSAL_MESSAGE)
    if _ACCOUNT.search(text):
        return PIICheckResult(detected=True, refusal_message=PII_REFUSAL_MESSAGE)
    if _OTP_CONTEXT.search(text) and _OTP_CODE.search(text):
        return PIICheckResult(detected=True, refusal_message=PII_REFUSAL_MESSAGE)

    return PIICheckResult(detected=False)
