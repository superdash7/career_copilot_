# -*- coding: utf-8 -*-
"""Unit-тесты: Switch — baseline_level = target-1, match по baseline."""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from switch_profession_service import (
    get_baseline_target_level,
    build_switch_comparison,
    GRADE_SEQUENCE,
)


def test_baseline_one_level_below():
    """baseline_level = target_level - 1."""
    assert get_baseline_target_level("Middle") == "Junior"
    assert get_baseline_target_level("Senior") == "Middle"
    assert get_baseline_target_level("Junior") == "Junior"
    assert get_baseline_target_level(None) == "Junior"


def test_switch_comparison_uses_baseline():
    """Сравнение считается по baseline_skillset."""
    class MockLoader:
        atlas_map = {}
        def get_role_requirements(self, role, level):
            if level == "Junior":
                return {"SQL": 1, "Python": 1, "Excel": 1}
            return {}
    loader = MockLoader()
    user_skills = {"SQL": 2}
    vm = build_switch_comparison(user_skills, "SomeRole", "Middle", loader)
    assert vm.baseline_level == "Junior"
    assert vm.match_score == 1 / 3
    assert any(m["name"] == "SQL" for m in vm.matched_skills)
    assert any(m["name"] == "Python" for m in vm.missing_skills)


if __name__ == "__main__":
    test_baseline_one_level_below()
    test_switch_comparison_uses_baseline()
    print("Switch profession tests OK.")
