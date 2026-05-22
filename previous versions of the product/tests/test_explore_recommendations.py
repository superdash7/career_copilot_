# -*- coding: utf-8 -*-
"""Unit-тесты для сценария «Исследование возможностей»: дедуп, категоризация, лимиты."""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from explore_recommendations import (
    normalize_role_name,
    RoleMatch,
    build_explore_recommendations,
    ExploreViewModel,
)
from config import Config


def test_normalize_dedup_backend():
    """Пять «Бэкенд-разработчик» с разными грейдами нормализуются в одну роль."""
    assert normalize_role_name("Бэкенд-разработчик (Middle)") == "Бэкенд-разработчик"
    assert normalize_role_name("Бэкенд-разработчик (Senior)") == "Бэкенд-разработчик"
    assert normalize_role_name("бэкенд-разработчик") == "Бэкенд-разработчик"


def test_categorization_thresholds():
    """Роли попадают в closest / adjacent / far по порогам."""
    matches = [
        RoleMatch("Роль A", 0.20, [], [], ["s1"], []),
        RoleMatch("Роль B", 0.10, [], [], ["s2"], []),
        RoleMatch("Роль C", 0.02, [], [], ["s3"], []),
    ]
    vm = build_explore_recommendations(matches)
    assert len(vm.closest) >= 1 and any(c.title == "Роль A" for c in vm.closest)
    assert len(vm.adjacent) >= 1 and any(c.title == "Роль B" for c in vm.adjacent)
    assert len(vm.far) >= 1 and any(c.title == "Роль C" for c in vm.far)


def test_dedup_five_backends_one_card():
    """На входе 5 матчей «Бэкенд-разработчик», на выходе одна карточка."""
    matches = [
        RoleMatch("Бэкенд-разработчик (Junior)", 0.05, ["a"], [{"name": "SQL"}], ["SQL"], []),
        RoleMatch("Бэкенд-разработчик (Middle)", 0.08, ["b"], [{"name": "Python"}], ["Python"], []),
        RoleMatch("Бэкенд-разработчик (Senior)", 0.12, ["c"], [{"name": "Go"}], ["Go"], []),
        RoleMatch("Бэкенд-разработчик (Lead)", 0.10, ["d"], [], [], []),
        RoleMatch("Бэкенд-разработчик (Expert)", 0.03, ["e"], [], [], []),
    ]
    vm = build_explore_recommendations(matches)
    all_cards = vm.closest + vm.adjacent + vm.far
    backend_cards = [c for c in all_cards if "Бэкенд" in c.title or "бэкенд" in c.title.lower()]
    assert len(backend_cards) == 1
    assert backend_cards[0].match_score == 0.12  # max по группе


def test_limits_per_category():
    """В каждой категории не больше заданного числа карточек."""
    matches = [
        RoleMatch(f"Роль {i}", 0.25 - i * 0.02, [], [], [], [])
        for i in range(15)
    ]
    vm = build_explore_recommendations(matches)
    assert len(vm.closest) <= Config.EXPLORE_CLOSEST_MAX_ROLES
    assert len(vm.adjacent) <= Config.EXPLORE_ADJACENT_MAX_ROLES
    assert len(vm.far) <= Config.EXPLORE_FAR_MAX_ROLES


def test_match_label_no_raw_zero():
    """При низком совпадении не показывается «0%» в percent_text, а «<10%»."""
    m = RoleMatch("Роль", 0.02, [], [], [], [])
    vm = build_explore_recommendations([m])
    far = vm.far
    assert len(far) == 1
    assert far[0].percent_text == "<10%"
    assert "низкое" in far[0].match_label.lower()


if __name__ == "__main__":
    test_normalize_dedup_backend()
    test_categorization_thresholds()
    test_dedup_five_backends_one_card()
    test_limits_per_category()
    test_match_label_no_raw_zero()
    print("All tests passed.")
