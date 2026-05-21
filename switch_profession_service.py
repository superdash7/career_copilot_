
"""
Сценарий «Смена профессии»
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

GRADE_SEQUENCE = ["Junior", "Middle", "Senior", "Lead", "Expert"]


def get_baseline_target_level(target_level: Optional[str]) -> str:
    """
    Уровень для сравнения и выбора навыков: на один ниже целевого.
    Если target_level не задан — минимальный (Junior).
    """
    if not target_level or target_level not in GRADE_SEQUENCE:
        return "Junior"
    idx = GRADE_SEQUENCE.index(target_level)
    return GRADE_SEQUENCE[max(0, idx - 1)]


@dataclass
class SwitchViewModel:
    """Модель сравнения для смены профессии (всё детерминированно + RAG snippets)."""
    baseline_level: str
    match_score: float  # 0..1
    matched_skills: List[Dict[str, Any]] = field(default_factory=list)  # [{name, snippet}]
    missing_skills: List[Dict[str, Any]] = field(default_factory=list)  # [{name, importance?}]
    key_skills: List[str] = field(default_factory=list)  # топ навыков baseline
    suggested_tracks: List[str] = field(default_factory=list)  # 2–3 трека по категориям


def retrieve_skill_snippets(skill_names: List[str], max_len: int = 120) -> Dict[str, str]:
    """Краткие описания навыков из RAG (1–2 строки)."""
    result = {}
    try:
        from rag_service import retrieve
        for name in skill_names:
            hits = retrieve(name, top_k=1, score_threshold=0.4)
            if hits:
                p = (hits[0].get("payload") or {})
                text = (p.get("text") or "").strip()
                if text:
                    result[name] = (text[:max_len] + "…") if len(text) > max_len else text
    except Exception:
        pass
    return result


def _get_gap_explanation(name: str) -> str:
    """Краткое RAG-объяснение для разрыва по навыку (1–2 предложения)."""
    try:
        from rag_service import get_rag_explanation_for_gap
        return get_rag_explanation_for_gap(name, is_skill=True) or ""
    except Exception:
        return ""


def _load_skill_clusters() -> tuple:
    """Загружает skill_clusters.json. Возвращает (skill_name -> cluster_id, cluster_id -> label) или ({}, {})."""
    try:
        from pathlib import Path
        from config import Config
        import json
        path = Path(Config.SKILLS_FILE)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        path = path.parent / "skill_clusters.json"
        if not path.exists():
            return {}, {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        skills_map = data.get("skills") or {}
        labels = {str(k): v for k, v in (data.get("labels") or {}).items()}
        return skills_map, labels
    except Exception:
        return {}, {}


def _suggested_tracks_by_cluster(missing_names: List[str], fallback_tracks: List[str]) -> List[str]:
    """Формирует 2–3 трека по кластерам навыков; при отсутствии кластеров возвращает fallback_tracks."""
    skill_to_cid, cid_to_label = _load_skill_clusters()
    if not skill_to_cid or not missing_names:
        return fallback_tracks[:3]
    by_cluster: Dict[int, List[str]] = {}
    for n in missing_names:
        cid = skill_to_cid.get(n)
        if cid is not None:
            by_cluster.setdefault(cid, []).append(n)
    tracks = []
    for cid, names in sorted(by_cluster.items(), key=lambda x: -len(x[1]))[:3]:
        label = cid_to_label.get(str(cid), f"Трек {cid}")
        tracks.append(f"{label}: {', '.join(names[:4])}")
    return tracks[:3] if tracks else fallback_tracks[:3]


def build_switch_comparison(
    user_skills: Dict[str, int],
    target_role: str,
    target_level: Optional[str],
    data_loader,
) -> SwitchViewModel:
    """
    Детерминированно: baseline_level, match_score по baseline_skillset,
    matched_skills top 8 (с snippets из RAG), missing_skills top 12.
    """
    # Нормализуем навыки пользователя
    try:
        from gap_analyzer import _normalize_skill_set
        norm = _normalize_skill_set(user_skills)
    except Exception:
        norm = dict(user_skills)

    baseline = get_baseline_target_level(target_level)
    reqs = data_loader.get_role_requirements(target_role, baseline)
    if not reqs:
        return SwitchViewModel(baseline_level=baseline, match_score=0.0)

    skill_reqs = {k: v for k, v in reqs.items() if k not in data_loader.atlas_map}
    total = len(skill_reqs) or 1

    # Exact match
    matched_names = [s for s in skill_reqs if s in norm and norm.get(s, 0) >= skill_reqs[s]]
    matched_set = set(matched_names)

    # Semantic match for unmatched skills
    user_skill_names = [n for n in norm if n not in data_loader.atlas_map]
    unmatched_reqs = [s for s in skill_reqs if s not in matched_set]
    try:
        from rag_service import semantic_match_skills
        sem_map = semantic_match_skills(user_skill_names, unmatched_reqs)
        for u_name, r_name in sem_map.items():
            if r_name not in matched_set and norm.get(u_name, 0) >= skill_reqs.get(r_name, 1):
                matched_names.append(r_name)
                matched_set.add(r_name)
    except Exception:
        pass

    missing_names = [s for s in skill_reqs if s not in matched_set]
    match_score = len(matched_names) / total

    matched_top = matched_names[:8]
    missing_top = missing_names[:12]
    snippets = retrieve_skill_snippets(matched_top + missing_top)
    matched_skills = [{"name": n, "snippet": snippets.get(n, "")} for n in matched_top]
    missing_skills = []
    for i, n in enumerate(missing_top):
        item = {"name": n, "importance": "must-have" if i < 6 else "nice-to-have"}
        if i < 8:
            item["explanation"] = _get_gap_explanation(n)
        missing_skills.append(item)

    key_skills = list(skill_reqs.keys())[:12]
    fallback_tracks = []
    if missing_top:
        fallback_tracks.append(f"Фокус на ключевых: {', '.join(missing_top[:4])}")
    if len(missing_top) > 4:
        fallback_tracks.append(f"Дополнительно: {', '.join(missing_top[4:8])}")
    if len(fallback_tracks) < 2 and key_skills:
        fallback_tracks.append(f"Базовый уровень роли ({baseline}): {', '.join(key_skills[:5])}")
    suggested_tracks = _suggested_tracks_by_cluster(missing_top, fallback_tracks)

    return SwitchViewModel(
        baseline_level=baseline,
        match_score=match_score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        key_skills=key_skills[:8],
        suggested_tracks=suggested_tracks[:3],
    )


def build_switch_rag_context(
    focus_skill_names: List[str],
    target_role: str,
    baseline_level: str,
    data_loader,
) -> str:
    """Контекст для LLM: только выбранные навыки + краткие описания из RAG, без выдуманного."""
    snippets = retrieve_skill_snippets(focus_skill_names, max_len=150)
    parts = [f"Целевая роль: {target_role}, уровень сравнения: {baseline_level}."]
    for name in focus_skill_names:
        s = snippets.get(name, "")
        parts.append(f"- {name}: {s}" if s else f"- {name}")
    return "\n".join(parts)
