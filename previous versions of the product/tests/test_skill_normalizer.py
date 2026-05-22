# -*- coding: utf-8 -*-
"""Тесты для skill_normalizer: нормализация и разрешение синонимов."""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))


def test_normalize_for_search_basic():
    """Нормализация: lower, trim, схлопывание пробелов."""
    from skill_normalizer import normalize_for_search
    assert normalize_for_search("  Анализ   данных  ") != ""
    assert "  " not in normalize_for_search("  a  b  ")


def test_resolve_to_canonical_from_file():
    """resolve_to_canonical возвращает канонический навык по словарю data/skill_synonyms.json."""
    from skill_normalizer import resolve_to_canonical
    canonical_set = {"Python", "Управление проектами", "SQL", "Excel", "Коммуникация"}
    # Синонимы из реального skill_synonyms.json
    assert resolve_to_canonical("питон", canonical_set) == "Python"
    assert resolve_to_canonical("Пайтон", canonical_set) == "Python"
    assert resolve_to_canonical("управление проектами", canonical_set) == "Управление проектами"
    assert resolve_to_canonical("эксель", canonical_set) == "Excel"
    assert resolve_to_canonical("несуществующий навык xyz", canonical_set) is None
    # Результат должен быть из canonical_set
    assert resolve_to_canonical("питон", {"Python"}) == "Python"
    assert resolve_to_canonical("питон", set()) is None
