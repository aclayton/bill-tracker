"""OpenRouter-compatible LLM callable for bill-tracker.

Reads OPENROUTER_API_KEY from the environment (set by Hermes).
Falls back to loading OPENAI_API_KEY for other providers.
"""

from __future__ import annotations

import json
import os
from typing import Callable


def openrouter_call(prompt: str, model: str) -> str:
    """Call an OpenRouter-compatible LLM and return the raw response text.

    Uses the OpenAI-compatible chat completions endpoint.
    Reads OPENROUTER_API_KEY from environment.

    Args:
        prompt: The system/user prompt to send.
        model: Model identifier (e.g. "google/gemini-3-flash-preview").

    Returns:
        Raw response text from the model.

    Raises:
        RuntimeError: If no API key is configured or the API call fails.
    """
    # Read API key: prefer OPENROUTER_API_KEY, fall back to OPENAI_API_KEY
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No API key found. Set OPENROUTER_API_KEY or OPENAI_API_KEY in the environment. "
            "Hermes sets this automatically when you configure an OpenRouter key."
        )

    base_url = os.environ.get(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )

    try:
        from urllib import request, error
    except ImportError:
        raise RuntimeError("Python urllib not available")

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.1,
    }).encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/aclayton/bill-tracker",
        "X-Title": "bill-tracker",
    }

    url = f"{base_url.rstrip('/')}/chat/completions"

    try:
        req = request.Request(url, data=payload, headers=headers, method="POST")
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(
            f"LLM API returned HTTP {e.code}: {body[:500]}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"LLM API call failed: {e}") from e

    try:
        data = json.loads(body)
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(
            f"Failed to parse LLM response: {e}\nResponse: {body[:500]}"
        ) from e


def create_llm_call(model: str) -> Callable[[str, str], str]:
    """Create an LLM callable wired to OpenRouter.

    Args:
        model: The model to use (passed through to the callable).

    Returns:
        A callable suitable for passing to classify_email, parse_bill, etc.
    """
    def llm_call(prompt: str, _model: str = "") -> str:
        return openrouter_call(prompt, model)
    return llm_call