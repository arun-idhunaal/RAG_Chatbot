"""
INDmoney MF FAQ Chatbot — Streamlit UI (Phase 5 / FR-12).

Run from repo root:
  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure repo root is importable when launched via `streamlit run app/...`.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st

from app.render import (
    AssistantView,
    build_assistant_view,
    citations_markdown,
    linkify_urls,
)
from app.ui_copy import (
    DISCLAIMER,
    EXAMPLE_QUESTIONS,
    PII_USER_PLACEHOLDER,
    WELCOME_MESSAGE,
)
from src.config.settings import get_settings
from src.ops.health import CORPUS_UNAVAILABLE_MESSAGE, check_index_health
from src.ops.metrics import record_query_metric
from src.pipeline.models import Intent
from src.pipeline.orchestrator import process_query
from src.retrieval.retriever import Retriever

st.set_page_config(
    page_title="INDmoney MF FAQ",
    page_icon=":material/account_balance:",
    layout="centered",
)


def _apply_streamlit_secrets() -> None:
    """Map Community Cloud secrets → env so pydantic Settings picks them up."""
    try:
        secrets = st.secrets
    except Exception:  # noqa: BLE001 — local runs may have no secrets.toml
        return
    mapping = {
        "GROQ_API_KEY": "GROQ_API_KEY",
        "LLM_MODEL": "LLM_MODEL",
        "USE_LLM_CLASSIFIER": "USE_LLM_CLASSIFIER",
        "CHROMA_PERSIST_DIR": "CHROMA_PERSIST_DIR",
        "ALLOW_PLAYWRIGHT": "ALLOW_PLAYWRIGHT",
    }
    for secret_key, env_key in mapping.items():
        if secret_key in secrets and not os.environ.get(env_key):
            os.environ[env_key] = str(secrets[secret_key])
    get_settings.cache_clear()


_apply_streamlit_secrets()


def _init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None


@st.cache_resource(show_spinner="Loading retrieval index…")
def _get_retriever() -> Retriever:
    """Shared Retriever (embeddings + Chroma) — expensive; cache across sessions."""
    return Retriever(settings=get_settings())


@st.cache_data(ttl=60, show_spinner=False)
def _index_is_healthy() -> bool:
    """EC-X-04 — cold-start / empty Chroma fail closed (cached briefly)."""
    return check_index_health(run_sample_query=True).ok


def _bootstrap_index() -> tuple[bool, str]:
    """One-time ingest for Community Cloud cold start (may take several minutes)."""
    from src.ingestion.pipeline import run_ingest
    from src.ops.metrics import record_scrape_from_ingest_report

    settings = get_settings()
    # Playwright often unavailable on Community Cloud free hosts.
    if "ALLOW_PLAYWRIGHT" not in os.environ:
        os.environ["ALLOW_PLAYWRIGHT"] = "false"
        get_settings.cache_clear()
        settings = get_settings()

    report = run_ingest(settings=settings, save_raw=False)
    record_scrape_from_ingest_report(report, settings=settings)
    _index_is_healthy.clear()
    _get_retriever.clear()
    health = check_index_health(settings=settings, run_sample_query=True)
    return health.ok, report.summary()


def _unavailable_view() -> AssistantView:
    return AssistantView(
        intent="unavailable",
        fact_text=CORPUS_UNAVAILABLE_MESSAGE,
        refusal_text=None,
        citations=[],
        last_updated_from_sources=None,
        supported_schemes=[],
        is_mixed=False,
        is_pii=False,
    )


def _render_disclaimer() -> None:
    """EC-UI-02 — disclaimer always visible (banner + sidebar)."""
    st.info(DISCLAIMER, icon=":material/info:")


def _render_welcome() -> None:
    """EC-UI-01 — welcome + facts-only framing on load."""
    with st.chat_message("assistant"):
        st.markdown(WELCOME_MESSAGE)


def _render_example_buttons(*, key_prefix: str) -> str | None:
    """EC-UI-06 — clickable examples that enqueue a real pipeline query."""
    st.caption("Try an example")
    cols = st.columns(len(EXAMPLE_QUESTIONS))
    for i, question in enumerate(EXAMPLE_QUESTIONS):
        label = question if len(question) <= 48 else question[:45] + "…"
        if cols[i].button(
            label,
            key=f"{key_prefix}_ex_{i}",
            help=question,
            width="stretch",
        ):
            return question
    return None


def _render_assistant_view(view: AssistantView) -> None:
    """Render answer text, mixed blocks, citations, date stamp (EC-UI-03…05)."""
    if view.is_mixed and view.refusal_text:
        # EC-UI-04 — fact block and refusal visually distinct.
        with st.container(border=True):
            st.markdown("**Facts**")
            st.markdown(linkify_urls(view.fact_text))
            cites = citations_markdown(view.citations)
            if cites:
                st.markdown(cites)
            if view.last_updated_from_sources and (
                "Last updated from sources:" not in view.fact_text
            ):
                st.caption(f"Last updated from sources: {view.last_updated_from_sources}")

        st.warning(view.refusal_text, icon=":material/gavel:")
        return

    st.markdown(linkify_urls(view.fact_text))

    cites = citations_markdown(view.citations)
    if cites:
        st.markdown(cites)

    # Inline date when factual citations exist but stamp wasn't in body (EC-UI-03).
    if (
        view.last_updated_from_sources
        and view.citations
        and "Last updated from sources:" not in (view.fact_text or "")
    ):
        st.markdown(f"Last updated from sources: `{view.last_updated_from_sources}`")

    # EC-UI-05 — ensure FR-9 scheme list is readable even if copy omits bullets.
    if view.intent == Intent.UNSUPPORTED_SCHEME.value and view.supported_schemes:
        body_lower = (view.fact_text or "").lower()
        missing = [n for n in view.supported_schemes if n.lower() not in body_lower]
        if missing:
            st.markdown("**Supported schemes:**")
            for name in view.supported_schemes:
                st.markdown(f"- {name}")


def _run_pipeline(message: str) -> AssistantView:
    """Stateless backend call per message (FR-12) — no server-side user history."""
    # EC-X-04 — empty Chroma / cold start: fail closed, no hallucinated corpus.
    if not _index_is_healthy():
        record_query_metric(
            intent="unavailable",
            empty_hit=True,
            short_circuit=True,
        )
        return _unavailable_view()

    t0 = time.perf_counter()
    result = process_query(message, retriever=_get_retriever())
    latency_ms = (time.perf_counter() - t0) * 1000.0
    record_query_metric(
        intent=result.intent.value,
        empty_hit=bool(result.retrieval_empty or result.insufficient_context),
        citation_validation_failed=False,
        short_circuit=bool(result.short_circuit),
        latency_ms=latency_ms,
    )
    return build_assistant_view(result)


def _append_turn(user_text: str, view: AssistantView) -> None:
    display_user = PII_USER_PLACEHOLDER if view.is_pii else user_text
    st.session_state.messages.append({"role": "user", "content": display_user})
    st.session_state.messages.append(
        {"role": "assistant", "view": view.to_dict()}
    )


# --- Page layout ---
_init_state()

with st.sidebar:
    st.markdown(f"**{DISCLAIMER}**")
    st.divider()
    st.markdown("**Example questions**")
    side_pick = _render_example_buttons(key_prefix="side")
    if side_pick:
        st.session_state.pending_prompt = side_pick
        st.rerun()
    st.divider()
    if not _index_is_healthy():
        st.caption("Knowledge base empty — run a one-time source refresh.")
        if st.button(
            "Build / refresh index",
            icon=":material/cloud_download:",
            width="stretch",
            type="primary",
        ):
            with st.spinner("Scraping approved sources and building index… (first run is slow)"):
                ok, summary = _bootstrap_index()
            if ok:
                st.success("Index ready.")
            else:
                st.error("Index still unhealthy after refresh.")
            st.code(summary[:2000])
            st.rerun()
        st.divider()
    if st.button("Clear chat", icon=":material/delete:", width="stretch"):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.rerun()

st.title("INDmoney MF FAQ")
_render_disclaimer()

if not _index_is_healthy():
    st.error(CORPUS_UNAVAILABLE_MESSAGE, icon=":material/cloud_off:")

pending = st.session_state.pending_prompt

# Welcome + examples only when chat is empty and nothing is queued (EC-UI-01).
if not st.session_state.messages and not pending:
    _render_welcome()
    main_pick = _render_example_buttons(key_prefix="main")
    if main_pick:
        st.session_state.pending_prompt = main_pick
        st.rerun()

# Replay in-browser session messages (not persisted server-side).
for msg in st.session_state.messages:
    role = msg["role"]
    with st.chat_message(role):
        if role == "user":
            st.markdown(msg["content"])
        else:
            _render_assistant_view(AssistantView.from_dict(msg["view"]))

# Always mount chat input; examples enqueue via pending_prompt (EC-UI-06).
chat_prompt = st.chat_input(
    "Ask a facts-only mutual fund question…",
    submit_mode="disable",
)
if pending:
    prompt = pending
    st.session_state.pending_prompt = None
else:
    prompt = chat_prompt

if prompt:
    # Run pipeline before rendering user bubble so FR-11 never echoes PII.
    with st.spinner("Looking up approved sources…"):
        view = _run_pipeline(prompt)

    display_user = PII_USER_PLACEHOLDER if view.is_pii else prompt
    with st.chat_message("user"):
        st.markdown(display_user)
    with st.chat_message("assistant"):
        _render_assistant_view(view)

    _append_turn(prompt, view)
