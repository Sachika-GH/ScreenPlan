"""LLM API client. Supports OpenAI-compatible APIs (DeepSeek, etc.)."""
import sys
from typing import Optional

import requests

from config import (
    LLM_API_KEY,
    LLM_API_BASE,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)


def generate_plan(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call the LLM API and return the generated plan text."""
    if not LLM_API_KEY:
        print("[llm_client] ERROR: No API key configured", file=sys.stderr)
        return None

    url = f"{LLM_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return None
    except requests.exceptions.Timeout:
        print(f"[llm_client] Timeout ({LLM_TIMEOUT}s)", file=sys.stderr)
    except requests.exceptions.HTTPError as e:
        print(f"[llm_client] HTTP error: {e}", file=sys.stderr)
        if e.response is not None:
            try:
                body = e.response.text[:500]
                print(f"[llm_client] Body: {body}", file=sys.stderr)
            except Exception:
                pass
    except Exception as e:
        print(f"[llm_client] Error: {e}", file=sys.stderr)
    return None
