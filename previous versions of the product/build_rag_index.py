"""Скрипт однократной сборки RAG-индекса (навыки + атлас) в Qdrant. Запуск: python build_rag_index.py"""

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
