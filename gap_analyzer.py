# -*- coding: utf-8 -*-
"""Анализ разрывов с семантическим мэтчингом навыков."""

from data_loader import PARAM_ORDINAL_NAMES, SKILL_LEVEL_NAMES


def _normalize_skill_set(user_skills: dict, canonical_set: set = None) -> dict:
    """Нормализует ключи user_skills через skill_normalizer."""
    if not user_skills:
        return {}
    try:
        from skill_normalizer import resolve_to_canonical, get_canonical_skills_set
        if canonical_set is None:
            canonical_set = get_canonical_skills_set()
        normalized = {}
        for name, level in user_skills.items():
            canonical = resolve_to_canonical(name, canonical_set)
            key = canonical if canonical else name
            if key not in normalized or level > normalized[key]:
                normalized[key] = level
        return normalized
    except Exception:
        return dict(user_skills)


def _build_semantic_map(user_names: list, required_names: list) -> dict:
    """Строит семантический маппинг user→required через embeddings."""
    try:
        from rag_service import semantic_match_skills
        return semantic_match_skills(user_names, required_names)
    except Exception:
        return {}


def level_display(value: int, is_atlas: bool) -> str:
    if is_atlas:
        return PARAM_ORDINAL_NAMES.get(value, str(value))
    return SKILL_LEVEL_NAMES.get(value, str(value))


def calculate_match_percent(strong_count: int, total_count: int) -> float:
    """match% = strong / total * 100. Safe from division by zero."""
    if total_count <= 0:
        return 0.0
    return round((strong_count / total_count) * 100, 1)


def classify_skill_gap(delta: int) -> dict:
    """
    delta = required_level - current_level
    <= 0 -> Strong (mastered)
    == 1 -> Moderate gap, Priority 2
    >= 2 -> Critical gap, Priority 1
    """
    if delta <= 0:
        return {"class": "strong", "priority": None, "in_recommendations": False}
    elif delta == 1:
        return {"class": "moderate", "priority": 2, "in_recommendations": True}
    else:
        return {"class": "critical", "priority": 1, "in_recommendations": True}


class GapAnalyzer:
    @staticmethod
    def analyze(user_skills, target_requirements):
        norm = _normalize_skill_set(user_skills)
        missing, gaps, strong = [], [], []

        for skill, req_level in target_requirements.items():
            curr_level = norm.get(skill, 0)
            if curr_level == 0:
                missing.append((skill, req_level))
            elif curr_level < req_level:
                gaps.append((skill, curr_level, req_level))
            else:
                strong.append((skill, curr_level))

        legacy_match_percent = int(calculate_match_percent(len(strong), len(target_requirements)))

        # В базовом analyze нет доступа к DataLoader, поэтому weighted=legacy.
        return {
            "match_percent": legacy_match_percent,
            "match_percent_legacy": legacy_match_percent,
            "weighted_match_percent": legacy_match_percent,
            "missing": missing,
            "gaps": gaps,
            "strong": strong,
        }

    @staticmethod
    def analyze_structured(user_skills, target_requirements, atlas_param_names, atlas_map):
        norm = _normalize_skill_set(user_skills)

        # Separate atlas params from skills in requirements
        skill_reqs = {k: v for k, v in target_requirements.items() if k not in atlas_param_names}
        param_reqs = {k: v for k, v in target_requirements.items() if k in atlas_param_names}

        # Build semantic map: user_skill_name → matched_required_skill_name
        user_skill_names = [n for n in norm if n not in atlas_param_names]
        required_skill_names = list(skill_reqs.keys())
        sem_map = _build_semantic_map(user_skill_names, required_skill_names)

        # Resolve user levels for required skills (exact + semantic)
        def get_user_level(req_name):
            if req_name in norm:
                return norm[req_name]
            for u_name, matched_r in sem_map.items():
                if matched_r == req_name:
                    return norm.get(u_name, 0)
            return 0

        atlas_gaps, atlas_strong = [], []
        skill_gaps, skill_strong = [], []

        # Atlas params (exact match only — names are controlled)
        for name, req_level in param_reqs.items():
            curr = norm.get(name, 0)
            delta = req_level - curr
            if curr >= req_level:
                atlas_strong.append({"name": name, "level": curr})
            else:
                why = ""
                if name in atlas_map:
                    desc = (atlas_map[name].get("Описание") or atlas_map[name].get("Description") or "")
                    why = desc or "Важно для целевого грейда."
                atlas_gaps.append({
                    "name": name, "current": curr, "required": req_level,
                    "delta": delta, "priority": 1 if delta >= 2 else (2 if delta >= 1 else 3),
                    "is_atlas": True, "why": why or "Важно для целевого грейда.",
                })

        # Skills (exact + semantic)
        for name, req_level in skill_reqs.items():
            curr = get_user_level(name)
            delta = req_level - curr
            if curr >= req_level:
                skill_strong.append({"name": name, "level": curr})
            else:
                skill_gaps.append({
                    "name": name, "current": curr, "required": req_level,
                    "delta": delta, "priority": 1 if delta >= 2 else (2 if delta >= 1 else 3),
                    "is_atlas": False,
                })

        atlas_gaps.sort(key=lambda x: (-x["delta"], x["name"]))
        skill_gaps.sort(key=lambda x: (-x["delta"], x["name"]))

        total = len(target_requirements)
        strong_count = len(atlas_strong) + len(skill_strong)
        legacy_match_percent = int((strong_count / total) * 100) if total else 0

        # Weighted match: считаем только по навыкам (не atlas-параметрам).
        # Вес навыка: Stable=2, Trending=3, неизвестно=1.
        skill_weights = {}
        try:
            from data_loader import DataLoader
            dl = DataLoader()
            for s_name in skill_reqs:
                skill_weights[s_name] = dl.get_skill_weight(s_name)
        except Exception:
            for s_name in skill_reqs:
                skill_weights[s_name] = 1

        required_weight_sum = sum(skill_weights.get(s_name, 1) for s_name in skill_reqs)
        matched_weight_sum = sum(
            skill_weights.get(s_name, 1)
            for s_name in skill_reqs
            if get_user_level(s_name) >= skill_reqs[s_name]
        )
        if required_weight_sum > 0:
            weighted_match_percent = int((matched_weight_sum / required_weight_sum) * 100)
        else:
            weighted_match_percent = legacy_match_percent

        return {
            "match_percent": weighted_match_percent,
            "match_percent_legacy": legacy_match_percent,
            "weighted_match_percent": weighted_match_percent,
            "atlas_gaps": atlas_gaps,
            "atlas_strong": atlas_strong,
            "skill_gaps": skill_gaps,
            "skill_strong": skill_strong,
            "missing": [(g["name"], g["required"]) for g in atlas_gaps + skill_gaps if g["current"] == 0],
            "gaps": [(g["name"], g["current"], g["required"]) for g in atlas_gaps + skill_gaps if g["current"] > 0],
            "strong": [(s["name"], s["level"]) for s in atlas_strong + skill_strong],
        }
