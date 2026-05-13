"""Переиндексация Qdrant коллекций для Career Copilot.

Запуск:
    python3 scripts/reindex_qdrant.py

Скрипт пересоздаёт:
1) legacy RAG-коллекцию (MiniLM) для fallback;
2) skills_v2 коллекцию (E5) для нормализации навыков.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from rag_service import build_index, build_skills_v2_index  # noqa: E402


def main() -> int:
    print("Запуск переиндексации Qdrant...")

    print("1/2 Legacy MiniLM индекс (fallback)...")
    legacy_count = build_index(force_recreate=True)
    if legacy_count is None:
        print("⚠️ Не удалось обновить legacy индекс.")
    else:
        print(f"✅ Legacy индекс обновлён. Точек: {legacy_count}")

    print("2/2 E5 индекс skills_v2...")
    skills_v2_count = build_skills_v2_index(force_recreate=True)
    if skills_v2_count is None:
        print("❌ Не удалось обновить skills_v2 индекс.")
        return 1
    print(f"✅ skills_v2 индекс обновлён. Точек: {skills_v2_count}")

    print("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
