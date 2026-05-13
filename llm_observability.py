"""Наблюдаемость для LLM-вызовов: структурированный JSON-лог, точный подсчёт токенов."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

_tiktoken_encoders: Dict[str, Any] = {}


def _get_tiktoken_encoder(model: str) -> Any:
    """Lazy-load tiktoken encoder for accurate token counting."""
    if model in _tiktoken_encoders:
        return _tiktoken_encoders[model]
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        _tiktoken_encoders[model] = enc
        return enc
    except ImportError:
        _tiktoken_encoders[model] = None
        return None


def estimate_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken if available, else heuristic.
    Russian text averages ~2.5 chars/token with tiktoken, not 4."""
    if not text:
        return 0
    enc = _get_tiktoken_encoder(model)
    if enc is not None:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    chars = len(text.strip())
    has_cyrillic = any("\u0400" <= c <= "\u04ff" for c in text[:200])
    chars_per_token = 2.5 if has_cyrillic else 3.5
    return max(1, int(chars / chars_per_token))


def estimate_tokens_from_text(text: str) -> int:
    """Backward-compatible alias."""
    return estimate_tokens(text)


@dataclass
class LLMCallMetrics:
    component: str
    operation: str
    model: str
    request_id: Optional[str]
    success: bool
    latency_ms: int
    prompt_chars: int
    completion_chars: int
    error: Optional[str] = None


def log_llm_call(metrics: LLMCallMetrics) -> None:
    prompt_tokens = estimate_tokens("x" * metrics.prompt_chars, metrics.model)
    completion_tokens = estimate_tokens("x" * metrics.completion_chars, metrics.model)
    total_tokens = prompt_tokens + completion_tokens

    payload: Dict[str, Any] = {
        "event": "llm_call",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "component": metrics.component,
        "operation": metrics.operation,
        "model": metrics.model,
        "request_id": metrics.request_id,
        "success": metrics.success,
        "latency_ms": metrics.latency_ms,
        "prompt_chars": metrics.prompt_chars,
        "completion_chars": metrics.completion_chars,
        "prompt_tokens_est": prompt_tokens,
        "completion_tokens_est": completion_tokens,
        "total_tokens_est": total_tokens,
    }
    if metrics.error:
        payload["error"] = metrics.error
    print(json.dumps(payload, ensure_ascii=False))


def now_ms() -> int:
    return int(time.time() * 1000)
