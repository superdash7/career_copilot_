"""Загрузка данных: навыки, атлас-параметры, маппинги профессий."""

import json
import re
from pathlib import Path
from config import Config

# --- Маппинг

# Навыки: Junior→Basic(1), Middle/Senior→Proficiency(2), Lead/Expert→Advanced(3)
GRADE_TO_SKILL_LEVEL = {
    "Junior": 1,
    "Middle": 2,
    "Senior": 2,
    "Lead": 3,
    "Expert": 3,
}

# Параметры атласа: 5 уровней, совпадают с грейдами
GRADE_TO_PARAM_ORDINAL = {
    "Junior": 1,
    "Middle": 2,
    "Senior": 3,
    "Lead": 4,
    "Expert": 5,
}

LEVEL_TO_FIELD_KEY = {1: "Basic", 2: "Proficiency", 3: "Advanced"}

PARAM_ORDINAL_NAMES = {1: "Младший", 2: "Специалист", 3: "Старший", 4: "Ведущий", 5: "Эксперт"}
SKILL_LEVEL_NAMES = {0: "Нет", 1: "Basic", 2: "Proficiency", 3: "Advanced"}


def _to_display_role_name(internal_name):
    if not internal_name:
        return internal_name
    s = internal_name.strip()
    if s.startswith("Скиллсет "):
        s = s[len("Скиллсет "):].strip()
    overrides = {
        "Менеджер проекта в IT": "Менеджер проектов в IT",
        "Ручные тестировщики": "Ручной тестировщик",
        "Автотестировщики": "Автотестировщик",
        "Фронтенд разработчиков": "Фронтенд-разработчик",
        "ML-разработчиков": "ML-разработчик",
        "Android-разработчиков": "Android-разработчик",
        "iOS-разработчиков": "iOS-разработчик",
        "Тех. менеджер": "Технический менеджер",
    }
    s = overrides.get(s, s)
    s = re.sub(r'\s*\(.*?\)', '', s)
    s = re.sub(r'\s*\([^)]*$', '', s)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    return s


class DataLoader:
    def __init__(self):
        self.skills = self._load_json(Config.SKILLS_FILE)
        self.atlas_params = self._load_json(Config.ATLAS_FILE)

        self.skills_map = {s.get('Навык') or s.get('name'): s for s in self.skills}
        self.atlas_map = {a.get('Параметр') or a.get('Parameter'): a for a in self.atlas_params}

        internal_roles = set()
        for skill in self.skills:
            prof = skill.get('Профессия (лист)') or skill.get('Профессия') or skill.get('Привязка к профессии')
            if isinstance(prof, str):
                internal_roles.add(prof)
        self._internal_to_display = {internal: _to_display_role_name(internal) for internal in internal_roles}
        self._display_to_internals: dict[str, list[str]] = {}
        for internal, disp in self._internal_to_display.items():
            self._display_to_internals.setdefault(disp, []).append(internal)
        self._display_to_internal = {disp: internals[0] for disp, internals in self._display_to_internals.items()}

    @staticmethod
    def _load_json(path):
        path = Path(path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_role_requirements(self, role_name, grade):
        """Требования роли для заданного грейда.
        Навыки → ordinal 1-3 (Basic/Proficiency/Advanced).
        Параметры → ordinal 1-5 (по грейдам)."""
        if not role_name or not str(role_name).strip():
            return {}
        requirements = {}
        skill_level = GRADE_TO_SKILL_LEVEL.get(grade, 2)
        param_ordinal = GRADE_TO_PARAM_ORDINAL.get(grade, 2)

        role_set = {role_name}
        if role_name in self._display_to_internals:
            role_set = set(self._display_to_internals[role_name])

        for skill in self.skills:
            skill_name = skill.get('Навык') or skill.get('name')
            professions = (
                skill.get('Профессия (лист)') or
                skill.get('Профессия') or
                skill.get('Привязка к профессии') or
                []
            )
            if isinstance(professions, str):
                professions = [professions]
            if role_set & set(professions):
                requirements[skill_name] = skill_level

        for param in self.atlas_params:
            param_name = param.get('Параметр') or param.get('Parameter')
            if param_name:
                requirements[param_name] = param_ordinal

        return requirements

    def get_all_roles(self):
        return sorted(set(self._internal_to_display.values()))

    def get_internal_role_name(self, display_name):
        if not display_name:
            return None
        return self._display_to_internal.get(display_name.strip(), display_name)

    def get_internal_role_names(self, display_name):
        if not display_name:
            return []
        return self._display_to_internals.get(display_name.strip(), [display_name])

    def get_skills_for_role(self, role_name):
        internals = self.get_internal_role_names(role_name) if role_name else []
        if not internals:
            return []
        internal_set = set(internals)
        skill_names = set()
        for skill in self.skills:
            skill_name = skill.get('Навык') or skill.get('name')
            professions = (
                skill.get('Профессия (лист)') or
                skill.get('Профессия') or
                skill.get('Привязка к профессии') or
                []
            )
            if isinstance(professions, str):
                professions = [professions]
            if internal_set & set(professions):
                skill_names.add(skill_name)
        return sorted(skill_names)

    def get_skill_detail(self, skill_name, grade):
        skill_obj = self.skills_map.get(skill_name)
        if not skill_obj:
            return None
        target_level = GRADE_TO_SKILL_LEVEL.get(grade, 2)
        field_key = LEVEL_TO_FIELD_KEY.get(target_level, "Proficiency")

        description = (
            skill_obj.get(f"Skill level \\\\ Индикатор - {field_key}") or
            skill_obj.get(f"Skill level \\ Индикатор - {field_key}") or ""
        ).strip()
        tasks = (
            skill_obj.get(f"Пример задач на развитие \\\\ уровень {field_key}") or
            skill_obj.get(f"Пример задач на развитие \\ уровень {field_key}") or ""
        ).strip()

        if not description and not tasks:
            return None
        return {
            "skill_name": skill_name,
            "level_key": field_key,
            "description": description,
            "tasks": tasks,
        }
