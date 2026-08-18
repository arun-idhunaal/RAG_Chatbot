"""Groq LLM client for classifier and later pipeline stages."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.config.settings import Settings, get_settings


class LLMError(RuntimeError):
    """Raised when the LLM call fails."""


# Groq retired llama-3.3-70b-versatile on 2026-08-16 (developer/free tier).
_DEPRECATED_MODEL_ALIASES = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
}


def resolve_llm_model(model: str) -> str:
    return _DEPRECATED_MODEL_ALIASES.get(model.strip(), model.strip())


@lru_cache
def _groq_client(api_key: str):
    from groq import Groq

    return Groq(api_key=api_key)


def chat_json(
    *,
    system_prompt: str,
    user_content: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Call Groq chat completions with JSON object response format."""
    settings = settings or get_settings()
    if not settings.groq_api_key:
        raise LLMError("GROQ_API_KEY is not configured.")

    model = resolve_llm_model(settings.llm_model)
    try:
        client = _groq_client(settings.groq_api_key)
        response = client.chat.completions.create(
            model=model,
            temperature=settings.llm_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        import json

        return json.loads(raw)
    except LLMError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"Groq LLM call failed: {exc}") from exc


def llm_available(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.use_llm_classifier and settings.groq_api_key)
