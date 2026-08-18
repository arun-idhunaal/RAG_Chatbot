"""Phase 7 FastAPI contract tests (PII no-echo, EC-X-04, /v1/chat DTO)."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.dto import pipeline_result_to_chat_response
from src.config.schemes import list_canonical_names
from src.ops.health import CORPUS_UNAVAILABLE_MESSAGE, HealthStatus
from src.pipeline.models import Citation, Intent, PipelineResult
from src.ui_copy import DISCLAIMER, EXAMPLE_QUESTIONS, PII_USER_PLACEHOLDER, WELCOME_MESSAGE


def _ok_health() -> HealthStatus:
    return HealthStatus(
        ok=True,
        scheme_count=10,
        general_count=5,
        schemes_present=["icici_flexicap_dg"],
        sample_query_ok=True,
    )


def _fail_health() -> HealthStatus:
    return HealthStatus(
        ok=False,
        scheme_count=0,
        general_count=0,
        schemes_present=[],
        sample_query_ok=False,
        reason="empty_collections",
    )


def test_health_ok(mock_retriever: MagicMock, no_llm_settings):
    app = create_app(
        settings=no_llm_settings,
        retriever=mock_retriever,
        health_fn=_ok_health,
        load_retriever=False,
    )
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["corpus_available"] is True


def test_health_fail_closed_ec_x_04(mock_retriever: MagicMock, no_llm_settings):
    app = create_app(
        settings=no_llm_settings,
        retriever=mock_retriever,
        health_fn=_fail_health,
        load_retriever=False,
    )
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is False
        assert body["corpus_available"] is False
        assert CORPUS_UNAVAILABLE_MESSAGE in (body.get("message") or "")

        chat = client.post("/v1/chat", json={"message": "What is an exit load?"})
        assert chat.status_code == 200
        payload = chat.json()
        assert payload["corpus_available"] is False
        assert payload["intent"] == "unavailable"
        assert CORPUS_UNAVAILABLE_MESSAGE in payload["answer_text"]
        mock_retriever.retrieve_general.assert_not_called()
        mock_retriever.retrieve_scheme.assert_not_called()


def test_chat_pii_never_echoed(mock_retriever: MagicMock, no_llm_settings):
    app = create_app(
        settings=no_llm_settings,
        retriever=mock_retriever,
        health_fn=_ok_health,
        load_retriever=False,
    )
    with TestClient(app) as client:
        secret = "PAN ABCDE1234F please"
        res = client.post("/v1/chat", json={"message": secret})
        assert res.status_code == 200
        dumped = res.text
        assert "ABCDE1234F" not in dumped
        assert "original_message" not in res.json()
        body = res.json()
        assert body["intent"] == "pii"
        mock_retriever.retrieve_scheme.assert_not_called()


def test_ui_config_has_fr12_copy_and_five_schemes(mock_retriever: MagicMock, no_llm_settings):
    app = create_app(
        settings=no_llm_settings,
        retriever=mock_retriever,
        health_fn=_ok_health,
        load_retriever=False,
    )
    with TestClient(app) as client:
        res = client.get("/v1/ui-config")
        assert res.status_code == 200
        body = res.json()
        assert body["disclaimer"] == DISCLAIMER
        assert body["welcome_message"] == WELCOME_MESSAGE
        assert body["example_questions"] == list(EXAMPLE_QUESTIONS)
        assert body["pii_user_placeholder"] == PII_USER_PLACEHOLDER
        names = [s["canonical_name"] for s in body["schemes"]]
        assert names == list_canonical_names()
        assert len(names) == 5


def test_dto_omits_chunk_text():
    result = PipelineResult(
        intent=Intent.SCHEME_SPECIFIC_FACTUAL,
        original_message="secret user text",
        answer_text="The expense ratio is 0.5%.",
        citations=[
            Citation(
                title="Flexicap",
                url="https://www.indmoney.com/mutual-funds/icici-prudential-flexicap-fund-direct-growth",
            )
        ],
        last_updated_from_sources="2026-08-12",
    )
    dto = pipeline_result_to_chat_response(result)
    dumped = dto.model_dump()
    assert "original_message" not in dumped
    assert "chunks" not in dumped
    assert dumped["citations"][0]["url"].startswith("https://")
    assert dumped["last_updated_from_sources"] == "2026-08-12"
    assert "Last updated from sources: 2026-08-12" in dumped["answer_text"]


def test_admin_ingest_hidden_without_token(mock_retriever: MagicMock, no_llm_settings):
    app = create_app(
        settings=no_llm_settings,
        retriever=mock_retriever,
        health_fn=_ok_health,
        load_retriever=False,
    )
    with TestClient(app) as client:
        res = client.post("/v1/admin/ingest")
        assert res.status_code == 404


def test_admin_ingest_requires_bearer(mock_retriever: MagicMock, tmp_path, monkeypatch):
    from src.config.settings import Settings

    monkeypatch.setattr("src.api.app.try_start_ingest", lambda *a, **k: True)

    settings = Settings(
        chroma_persist_dir=tmp_path / "chroma",
        raw_html_dir=tmp_path / "raw",
        audit_log_dir=tmp_path / "audit",
        metrics_log_dir=tmp_path / "metrics",
        use_llm_classifier=False,
        groq_api_key="",
        ingest_token="test-token",
        auto_ingest_on_empty=False,
    )
    app = create_app(
        settings=settings,
        retriever=mock_retriever,
        health_fn=_ok_health,
        load_retriever=False,
    )
    with TestClient(app) as client:
        denied = client.post("/v1/admin/ingest")
        assert denied.status_code == 401
        wrong = client.post(
            "/v1/admin/ingest",
            headers={"Authorization": "Bearer nope"},
        )
        assert wrong.status_code == 401
        ok = client.post(
            "/v1/admin/ingest",
            headers={"Authorization": "Bearer test-token"},
        )
        assert ok.status_code == 202
        body = ok.json()
        assert body["accepted"] is True

