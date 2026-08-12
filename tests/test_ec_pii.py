"""EC-PII-* and EC-X-01 — PII gate short-circuits before classifier/retrieval."""

from __future__ import annotations

import pytest

from src.pipeline.intent_classifier import classify_intent
from src.pipeline.models import Intent
from src.pipeline.orchestrator import process_query
from src.pipeline.pii_guard import PII_REFUSAL_MESSAGE, check_pii


@pytest.mark.parametrize(
    "message",
    [
        "ABCDE1234F",
        "My PAN is ABCDE1234F",
        "1234 5678 9012",
        "user@example.com",
        "9876543210",
        "OTP is 482910",
        "1234567890123456",
    ],
    ids=["pan-alone", "pan-phrase", "aadhaar", "email", "phone", "otp", "account"],
)
def test_ec_pii_01_refuses_without_echo(message: str):
    result = check_pii(message)
    assert result.detected is True
    assert result.refusal_message == PII_REFUSAL_MESSAGE
    assert "ABCDE" not in (result.refusal_message or "")
    assert "9876543210" not in (result.refusal_message or "")


def test_ec_pii_02_refuses_entire_compound_message(no_llm_settings, mock_retriever):
    """PII + valid fact question → FR-11 only; no retrieval."""
    msg = "What is the expense ratio of Flexicap? My PAN is ABCDE1234F"
    result = process_query(msg, settings=no_llm_settings, retriever=mock_retriever)

    assert result.intent == Intent.PII
    assert result.short_circuit is True
    assert result.short_circuit_reason == "pii"
    assert result.chunks == []
    mock_retriever.retrieve_scheme.assert_not_called()
    mock_retriever.retrieve_general.assert_not_called()


def test_ec_x_01_pii_wins_over_scheme_and_advice(no_llm_settings, mock_retriever):
    msg = "HDFC Midcap 1Y return and should I buy? My PAN is ABCDE1234F"
    result = process_query(msg, settings=no_llm_settings, retriever=mock_retriever)

    assert result.intent == Intent.PII
    assert result.short_circuit_reason == "pii"
    mock_retriever.retrieve_scheme.assert_not_called()


def test_ec_pii_03_refusal_never_echoes_pan(no_llm_settings, mock_retriever):
    """EC-PII-03 — response must never confirm or partially echo PAN digits."""
    msg = "My PAN is ABCDE1234F — what is flexicap expense ratio?"
    result = process_query(msg, settings=no_llm_settings, retriever=mock_retriever)
    assert result.intent == Intent.PII
    blob = " ".join(
        [
            result.answer_text or "",
            result.refusal_message or "",
            result.original_message or "",
        ]
    )
    assert "ABCDE" not in blob
    assert "1234F" not in blob
    assert "I see your PAN" not in blob.lower()
    assert "ending in" not in blob.lower()


def test_ec_pii_04_no_raw_message_persisted_on_pii(no_llm_settings, mock_retriever):
    """EC-PII-04 — orchestrator must not keep raw PII-bearing message."""
    msg = "contact me at user@example.com about midcap"
    result = process_query(msg, settings=no_llm_settings, retriever=mock_retriever)
    assert result.intent == Intent.PII
    assert result.original_message == ""
    assert "user@example.com" not in (result.answer_text or "")
    assert "user@example.com" not in (result.refusal_message or "")


def test_pii_never_calls_classifier(no_llm_settings, monkeypatch):
    """Classifier must not run when PII is detected (orchestrator gate)."""
    called = {"n": 0}

    def _spy(msg, **kwargs):
        called["n"] += 1
        return classify_intent(msg, settings=no_llm_settings)

    monkeypatch.setattr("src.pipeline.orchestrator.classify_intent", _spy)
    process_query("PAN ABCDE1234F", settings=no_llm_settings)
    assert called["n"] == 0
