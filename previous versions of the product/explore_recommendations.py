
"""
Сценарий «Исследование возможностей».
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from config import Config

ROLE_SYNONYMS = {
    "бэкенд-разработчик": "Бэкенд-разработчик",
    "backend developer": "Бэкенд-разработчик",
    "менеджер продукта": "Менеджер продукта",
    "менеджер проектов": "Менеджер проектов в IT",
    "менеджер проектов в it": "Менеджер проектов в IT",
    "product manager": "Менеджер продукта",
    "ручной тестировщик": "Ручной тестировщик",
    "автотестировщик": "Автотестировщик",
    "фронтенд-разработчик": "Фронтенд-разработчик",
    "ml-разработчик": "ML-разработчик",
    "data scientist": "ML-разработчик",
}


def normalize_role_name(role_title: str) -> str:
    """Нормализация для дедупа: lower, trim, опционально маппинг синонимов."""
    if not role_title:
        return ""
    t = role_title.split(" (")[0].strip().lower()
    t = " ".join(t.split())
    return ROLE_SYNONYMS.get(t, role_title.split(" (")[0].strip())


@dataclass
class RoleMatch:
    """Входной матч по одной роли"""
    role_title: str
    match_score: float  # 0..1
    why_match: List[str] = field(default_factory=list)
    matched_skills: List[Dict[str, Any]] = field(default_factory=list)  # [{"name": str, "snippet": str?}]
    key_skills: List[str] = field(default_factory=list)
    missing_skills: List[Dict[str, Any]] = field(default_factory=list)  # [{"name": str, "importance": str?}]
    internal_role: Optional[str] = None


@dataclass
class RoleCard:
    """Карточка роли для вывода"""
    title: str
    internal_role: Optional[str] = None
    match_score: float = 0.0
    match_label: str = ""       # "высокое / среднее / низкое совпадение"
    percent_text: str = ""     # "25%" или "<10%"
    reasons: List[str] = field(default_factory=list)   # 3–5
    add_skills: List[str] = field(default_factory=list)  # 3
    key_skills: List[str] = field(default_factory=list)  # до 8
    track_labels: List[str] = field(default_factory=list)  # метки кластеров по key_skills/add_skills


@dataclass
class ExploreViewModel:
    """Модель выдачи Explore: три категории"""
    closest: List[RoleCard] = field(default_factory=list)
    adjacent: List[RoleCard] = field(default_factory=list)
    far: List[RoleCard] = field(default_factory=list)


def _match_label(score: float) -> str:
    if score >= 0.15:
        return "высокое совпадение"
    if score >= 0.05:
        return "среднее совпадение"
    return "низкое совпадение (потребуется усиленная прокачка)"


def _percent_text(score: float) -> str:
    p = round(score * 100)
    if p < 10:
        return "<10%"
    return f"{p}%"


def _skill_track_labels(skill_names: List[str]) -> List[str]:
    """Уникальные метки кластеров для списка навыков (из skill_clusters.json)."""
    try:
        from pathlib import Path
        from config import Config
        import json
        path = Path(Config.SKILLS_FILE)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        path = path.parent / "skill_clusters.json"
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        skills_map = data.get("skills") or {}
        labels_map = {str(k): v for k, v in (data.get("labels") or {}).items()}
        seen = set()
        out = []
        for name in skill_names:
            cid = skills_map.get(name)
            if cid is not None:
                lbl = labels_map.get(str(cid), "")
                if lbl and lbl not in seen:
                    seen.add(lbl)
                    out.append(lbl)
        return out[:5]
    except Exception:
        return []


def build_explore_recommendations(matches: List[RoleMatch]) -> ExploreViewModel:
  
    if not matches:
        return ExploreViewModel()

    # Дедуп по нормализованному названию
    by_key: Dict[str, List[RoleMatch]] = {}
    for m in matches:
        key = normalize_role_name(m.role_title)
        if not key:
            continue
        by_key.setdefault(key, []).append(m)

    cards: List[RoleCard] = []
    for key, group in by_key.items():
        # Берём лучший match_score в группе
        best = max(group, key=lambda x: x.match_score)
        # Объединяем поля
        all_why = []
        for m in group:
            all_why.extend(m.why_match)
        reasons = list(dict.fromkeys(all_why))[: Config.EXPLORE_REASONS_TOP_N]

        all_matched = []
        for m in group:
            for s in m.matched_skills:
                name = s.get("name") if isinstance(s, dict) else str(s)
                if name and not any(x.get("name") == name for x in all_matched if isinstance(x, dict)):
                    all_matched.append(s if isinstance(s, dict) else {"name": name})
        matched_skills = all_matched[:5]

        all_missing = []
        for m in group:
            for s in m.missing_skills:
                name = s.get("name") if isinstance(s, dict) else str(s)
                if name and not any(x.get("name") == name for x in all_missing if isinstance(x, dict)):
                    all_missing.append(s if isinstance(s, dict) else {"name": name})
        missing_sorted = sorted(
            all_missing,
            key=lambda x: ({"high": 0, "medium": 1, "low": 2}.get((x or {}).get("importance", ""), 2),
                          (x or {}).get("name", "")),
        )
        add_skills = [ (x.get("name") or str(x)) for x in missing_sorted[: Config.EXPLORE_ADD_SKILLS_TOP_N] ]

        all_key = []
        for m in group:
            for s in m.key_skills:
                if s and s not in all_key:
                    all_key.append(s)
        key_skills = all_key[: Config.EXPLORE_KEY_SKILLS_TOP_N]

        title = group[0].role_title.split(" (")[0].strip() if group else key
        internal = next((m.internal_role for m in group if m.internal_role), None)
        score = best.match_score

        card = RoleCard(
            title=title,
            internal_role=internal,
            match_score=score,
            match_label=_match_label(score),
            percent_text=_percent_text(score),
            reasons=reasons[:5],
            add_skills=add_skills[:3],
            key_skills=key_skills[:8],
        )
        cards.append(card)

    # Сортируем по score desc
    cards.sort(key=lambda c: -c.match_score)

    closest_min = Config.EXPLORE_CLOSEST_MIN
    adjacent_min = Config.EXPLORE_ADJACENT_MIN

    closest = [c for c in cards if c.match_score >= closest_min][: Config.EXPLORE_CLOSEST_MAX_ROLES]
    adjacent = [c for c in cards if adjacent_min <= c.match_score < closest_min][: Config.EXPLORE_ADJACENT_MAX_ROLES]
    far = [c for c in cards if c.match_score < adjacent_min][: Config.EXPLORE_FAR_MAX_ROLES]

    return ExploreViewModel(closest=closest, adjacent=adjacent, far=far)
