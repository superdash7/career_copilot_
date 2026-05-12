"""Утилиты confidence-оценки навыков для API/eval."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from rapidfuzz import fuzz


def compute_skill_confidence(
    *,
    raw_name: str,
    canonical_name: str,
    llm_rerank_confidence: Any = None,
    is_unknown: bool = False,
) -> Tuple[float, str]:
    """
    Confidence bands:
    1) exact match -> 1.0
    2) fuzzy ratio > 85 -> 0.9
    3) vector + llm rerank -> 0.6..0.95
    4) llm unknown classification -> 0.5
    """
    raw_name = (raw_name or "").strip()
    canonical_name = (canonical_name or "").strip()
    if not canonical_name:
        return 0.5, "llm_unknown"

    if raw_name and canonical_name and raw_name.lower() == canonical_name.lower():
        return 1.0, "exact"

    ratio = fuzz.ratio(raw_name.lower(), canonical_name.lower()) if raw_name and canonical_name else 0.0
    if ratio > 85:
        return 0.9, "fuzzy"

    if is_unknown:
        return 0.5, "llm_unknown"

    try:
        llm_conf = float(llm_rerank_confidence) if llm_rerank_confidence is not None else 0.75
    except Exception:
        llm_conf = 0.75
    return max(0.6, min(0.95, llm_conf)), "vector_llm"


def get_skill_confidence(skill: Dict[str, Any]) -> Tuple[float, str]:
    raw_name = (skill.get("raw_name") or skill.get("name") or "").strip()
    canonical_name = (skill.get("name") or "").strip()
    return compute_skill_confidence(
        raw_name=raw_name,
        canonical_name=canonical_name,
        llm_rerank_confidence=skill.get("llm_rerank_confidence"),
        is_unknown=bool(skill.get("is_unknown")),
    )
