"""Shared LLM calling utilities with client caching.

Provides a reusable LLM caller that avoids recreating API clients
on every call. Used by both MemoryQueryAgent and AgenticRetriever.

Clients are cached **per API key** so that different sessions (each
carrying their own key via thread-local storage) get their own client
instance while still benefiting from reuse within the same key.
"""

from __future__ import annotations

import logging
from typing import Callable

from cognifold.service.llm_keys import get_api_key

logger = logging.getLogger(__name__)

# Module-level cached clients keyed by API key value.
# This ensures different sessions with different keys each get a
# correctly-configured client, while sessions sharing the same key
# reuse the same instance.
_openai_clients: dict[str, object] = {}
_gemini_clients: dict[str, object] = {}


def _get_openai_client() -> object | None:
    """Get or create a cached OpenAI client for the current API key."""
    openai_key = get_api_key("OPENAI_API_KEY")
    if not openai_key:
        return None

    cached = _openai_clients.get(openai_key)
    if cached is not None:
        return cached

    try:
        from openai import OpenAI

        client = OpenAI(api_key=openai_key)
        _openai_clients[openai_key] = client
        return client
    except Exception as e:
        logger.debug("Failed to create OpenAI client: %s", e)
        return None


def _get_gemini_client() -> object | None:
    """Get or create a cached Gemini client for the current API key."""
    google_key = get_api_key("GOOGLE_API_KEY") or get_api_key("GEMINI_API_KEY")
    if not google_key:
        return None

    cached = _gemini_clients.get(google_key)
    if cached is not None:
        return cached

    try:
        from google import genai

        client = genai.Client(api_key=google_key)
        _gemini_clients[google_key] = client
        return client
    except Exception as e:
        logger.debug("Failed to create Gemini client: %s", e)
        return None


def call_llm(
    prompt: str,
    system_prompt: str | None = None,
    *,
    model: str | None = None,
    reasoning_effort: str | None = None,
    max_tokens: int = 500,
) -> str:
    """Call LLM with cached client instances.

    Tries OpenAI first, then Gemini. Caches clients at module level
    to avoid repeated instantiation overhead.

    Args:
        prompt: The prompt to send.
        system_prompt: Optional system-level instruction (e.g. language).
        model: Override model name. Accepts "openai:<name>" prefix or
            raw name. When None, falls back to the legacy default
            "gpt-4o" for the OpenAI path.
        reasoning_effort: For gpt-5/o1/o3 reasoning models, pass through
            "low"/"medium"/"high". Ignored on non-reasoning models.
            When None and model is reasoning-class, defaults to "high".
        max_tokens: Output token budget. For reasoning models the call
            uses max_completion_tokens = max(max_tokens, 24576) instead.

    Returns:
        LLM response text.

    Raises:
        RuntimeError: If no LLM API key is available.
    """
    openai_model = "gpt-4o"
    if model:
        openai_model = model.split(":", 1)[1] if model.startswith("openai:") else model

    is_reasoning = (
        openai_model.startswith("o1") or openai_model.startswith("o3") or "gpt-5" in openai_model
    )

    # Try OpenAI first
    openai_client = _get_openai_client()
    if openai_client is not None:
        try:
            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            kwargs: dict = {
                "model": openai_model,
                "messages": messages,
            }
            if is_reasoning:
                kwargs["reasoning_effort"] = reasoning_effort or "high"
                kwargs["max_completion_tokens"] = max(max_tokens, 24576)
            else:
                kwargs["temperature"] = 0.0
                kwargs["max_tokens"] = max_tokens
            response = openai_client.chat.completions.create(**kwargs)  # type: ignore[union-attr]
            return response.choices[0].message.content or ""  # type: ignore[union-attr]
        except Exception as e:
            logger.debug("OpenAI call failed: %s", e)

    # Try Gemini
    gemini_client = _get_gemini_client()
    if gemini_client is not None:
        try:
            full_prompt = (
                f"[System Instructions]\n{system_prompt}\n\n{prompt}" if system_prompt else prompt
            )
            response = gemini_client.models.generate_content(  # type: ignore[union-attr]
                model="gemini-3-flash-preview",
                contents=full_prompt,
            )
            return response.text if response.text else ""  # type: ignore[union-attr]
        except Exception as e:
            logger.debug("Gemini call failed: %s", e)

    raise RuntimeError(
        "No LLM API key available (set OPENAI_API_KEY or GOOGLE_API_KEY, "
        "or provide keys via the session)"
    )


def make_llm_caller(custom_caller: Callable[[str], str] | None = None) -> Callable[[str], str]:
    """Create an LLM caller, using custom callable or the shared cached caller.

    Args:
        custom_caller: Optional custom callable. If provided, returned as-is.

    Returns:
        A callable(prompt) -> response.
    """
    if custom_caller is not None:
        return custom_caller
    return call_llm
