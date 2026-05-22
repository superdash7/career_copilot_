# -*- coding: utf-8 -*-
"""Unit-тесты: Next grade — narrative из RAG, delta из current+target."""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from next_grade_service import (
    retrieve_param_expectations,
    build_next_grade_narrative,
)


def test_param_expectations_from_atlas():
    """Ожидания по параметру берутся только из atlas."""
    atlas_map = {
        "Автономность": {
            "Описание": "Способность принимать решения.",
            "Младший": "Работает под руководством.",
            "Специалист": "Самостоятельно решает задачи.",
            "Старший": "Определяет задачи и подходы.",
        },
    }
    t = retrieve_param_expectations("Автономность", "Middle", atlas_map)
    assert t == "Самостоятельно решает задачи."


def test_narrative_uses_only_rag_fragments():
    """Narrative строится из текущего и целевого уровней."""
    atlas_map = {
        "Параметр A": {
            "Младший": "Текст младший.",
            "Специалист": "Текст специалист.",
            "Старший": "Текст старший.",
        },
    }
    summary = build_next_grade_narrative("Junior", "Senior", atlas_map)
    assert summary.target_level == "Senior"
    assert summary.current_level == "Junior"
    assert len(summary.param_expectations) == 1
    pe = summary.param_expectations[0]
    assert pe["target_text"] == "Текст старший."
    assert pe["current_text"] == "Текст младший."


if __name__ == "__main__":
    test_param_expectations_from_atlas()
    test_narrative_uses_only_rag_fragments()
    print("Next grade tests OK.")
