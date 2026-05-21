"""Скрипт однократной сборки legacy RAG-индекса (MiniLM) в Qdrant.

Для полной переиндексации (legacy + skills_v2 E5) используйте:
    python3 scripts/reindex_qdrant.py
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from rag_service import build_index

if __name__ == "__main__":
    print("Построение RAG-индекса (навыки + параметры атласа)...")
    n = build_index(force_recreate=True)
    if n is not None:
        print(f"Готово. Загружено точек: {n}")
    else:
        print("Ошибка или Qdrant недоступен. Проверьте QDRANT_URL и QDRANT_API_KEY в .env")
