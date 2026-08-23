"""Multi-provider free-tier LLM wrapper with deterministic fallback.

Provider order (all OpenAI-compatible JSON-mode APIs):
  1. Cerebras  (CEREBRAS_API_KEY)   ~30K TPM free
  2. Groq      (GROQ_API_KEY)       fast, ~6K TPM free
  3. Gemini    (GEMINI_API_KEY)     tertiary, tiny free quota

If no key is set (or all providers fail), returns None and callers fall back
to deterministic heuristics — the demo always works offline.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx

PROVIDERS = [
    {
        "name": "cerebras",
        "key_env": "CEREBRAS_API_KEY",
        "base_url": "https://api.cerebras.ai/v1",
        "model": "gpt-oss-120b",
    },
    {
        "name": "groq",
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    {
        "name": "gemini",
        "key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.5-flash",
    },
]

TIMEOUT = 60.0


def available_providers() -> list[str]:
    return [p["name"] for p in PROVIDERS if os.environ.get(p["key_env"])]


def chat_json(system: str, user: str, max_tokens: int = 1500) -> Optional[dict]:
    """Send a chat completion requesting JSON; return parsed dict or None."""
    for p in PROVIDERS:
        key = os.environ.get(p["key_env"])
        if not key:
            continue
        try:
            resp = httpx.post(
                f"{p['base_url']}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": p["model"],
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {"type": "json_object"},
                    "max_completion_tokens": max_tokens,
                    "temperature": 0.1,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return _parse_json(content)
        except Exception:
            continue  # try next provider (rate limit, outage, bad key)
    return None


def _parse_json(text: str) -> Optional[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None
