
"""
Сценарий «Переход на следующий грейд»
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Маппинг грейда в ключи атласа (Младший, Специалист, ...)
GRADE_TO_ATLAS_LEVEL = {
    "Junior": "Младший",
    "Middle": "Специалист",
    "Senior": "Старший",
    "Lead": "Ведущий",
    "Expert": "Эксперт",
}


@dataclass
class ParamExpectation:
    """Ожидание по параметру на уровне (из RAG/атласа)."""
    param_name: str
    level_key: str
    expectation_text: str
    description: str = ""


@dataclass
class ExpectationsSummary:
    """Сводка ожиданий по параметрам: target + delta vs current (все тексты из RAG)."""
    target_level: str
    current_level: str
    param_expectations: List[Dict[str, Any]] = field(default_factory=list)
    # каждый элемент: param_name, target_text, current_text, delta_note


def retrieve_params_for_role(data_loader) -> List[str]:
    """Список параметров атласа (общий для всех ролей)."""
    return list(data_loader.atlas_map.keys())


def retrieve_param_expectations(param_name: str, level: str, atlas_map: Dict) -> Optional[str]:
    """Текст ожиданий по параметру на уровне — только из atlas (RAG source)."""
    if param_name not in atlas_map:
        return None
    param = atlas_map[param_name]
    atlas_key = GRADE_TO_ATLAS_LEVEL.get(level) or level
    return (param.get(atlas_key) or param.get("Описание") or "").strip() or None


def retrieve_role_skills(data_loader, role_name: str, level: str) -> Dict[str, int]:
    """Навыки по роли и уровню (без параметров атласа)."""
    reqs = data_loader.get_role_requirements(role_name, level)
    return {k: v for k, v in reqs.items() if k not in data_loader.atlas_map}


def build_next_grade_narrative(
    current_grade: str,
    target_grade: str,
    atlas_map: Dict,
) -> ExpectationsSummary:
    """
    Описание «что значит следующий грейд»: для каждого параметра — ожидание на target_level
    и delta vs current.
    """
    current_key = GRADE_TO_ATLAS_LEVEL.get(current_grade, "Специалист")
    target_key = GRADE_TO_ATLAS_LEVEL.get(target_grade, "Старший")
    param_expectations = []
    for param_name in retrieve_params_for_role_from_map(atlas_map):
        target_text = retrieve_param_expectations(param_name, target_grade, atlas_map)
        current_text = retrieve_param_expectations(param_name, current_grade, atlas_map)
        desc = (atlas_map.get(param_name) or {}).get("Описание") or (atlas_map.get(param_name) or {}).get("Description") or ""
        delta_note = ""
        if current_text and target_text:
            delta_note = f"Сейчас: {current_text} → Цель: {target_text}"
        param_expectations.append({
            "param_name": param_name,
            "target_text": target_text or "",
            "current_text": current_text or "",
            "delta_note": delta_note,
            "description": desc,
        })
    return ExpectationsSummary(
        target_level=target_grade,
        current_level=current_grade,
        param_expectations=param_expectations,
    )


def retrieve_params_for_role_from_map(atlas_map: Dict) -> List[str]:
    return list(atlas_map.keys())


def build_skill_support(
    priority_param_names: List[str],
    role_name: str,
    target_grade: str,
    data_loader,
    top_per_param: int = 5,
) -> Dict[str, List[str]]:
    """
    Навыки-помощники по приоритетным параметрам. Группируем навыки роли по параметрам
    через RAG-запрос «навыки для параметра X» или отдаём топ навыков роли на каждый параметр.
    У нас нет явного skill->param mapping, поэтому: для каждого param делаем RAG retrieve
    «параметр X навыки развитие» и берём топ skill names из payload; если пусто — берём
    общий список навыков роли и распределяем по порядку.
    """
    role_skills = list(retrieve_role_skills(data_loader, role_name, target_grade).keys())
    result = {p: [] for p in priority_param_names}
    try:
        from rag_service import retrieve
        for param in priority_param_names:
            hits = retrieve(f"Параметр {param} навыки развитие компетенции", top_k=8, score_threshold=0.25)
            seen = set()
            for h in (hits or []):
                p = (h.get("payload") or {})
                if p.get("type") == "skill":
                    name = (p.get("name") or "").strip()
                    if name and name not in seen and name in role_skills:
                        seen.add(name)
                        result[param].append(name)
                        if len(result[param]) >= top_per_param:
                            break
    except Exception:
        pass
    # Добиваем из общих навыков роли, если по параметру мало
    for param in priority_param_names:
        for s in role_skills:
            if s not in result[param] and len(result[param]) < top_per_param:
                result[param].append(s)
            if len(result[param]) >= top_per_param:
                break
    return result


def build_next_grade_rag_context(
    atlas_gaps: List[Dict],
    skill_gaps: List[Dict],
    target_grade: str,
    atlas_map: Dict,
    data_loader,
    role_name: str,
) -> str:
    """
    Контекст для LLM: только факты из RAG — ожидания по параметрам на target_level,
    delta, список поддерживающих навыков. Без выдуманных параметров/навыков.
    """
    parts = []
    target_key = GRADE_TO_ATLAS_LEVEL.get(target_grade, "Старший")
    priority_params = [g["name"] for g in atlas_gaps[:6]]
    for param_name in priority_params:
        text = retrieve_param_expectations(param_name, target_grade, atlas_map)
        if text:
            parts.append(f"[Параметр: {param_name}] Ожидание на целевом уровне: {text[:400]}")
    support = build_skill_support(priority_params, role_name, target_grade, data_loader, top_per_param=5)
    for param, skills in support.items():
        if skills:
            parts.append(f"[Навыки для параметра {param}]: {', '.join(skills[:5])}")
    skill_names = [g["name"] for g in skill_gaps[:10]]
    if skill_names:
        parts.append(f"[Приоритетные навыки для развития]: {', '.join(skill_names)}")
    return "\n\n".join(parts) if parts else ""
