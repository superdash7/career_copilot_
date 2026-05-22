"""config

    https://colab.research.google.com/drive/1-hlyVAHTgHqOVi31tGnf20gqV6hApg8a
"""

import os
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent
_env_file = _PROJECT_DIR / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        for line in _env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    RESUME_PARSER_MODEL = os.getenv("RESUME_PARSER_MODEL", "gpt-4o")
    RESUME_TEXT_MAX_CHARS = int(os.getenv("RESUME_TEXT_MAX_CHARS", "14000"))
    DATA_DIR = _PROJECT_DIR / "data"
    SKILLS_FILE = DATA_DIR / "clean_skills.json"
    ATLAS_FILE = DATA_DIR / "atlas_params_clean.json"
    ROLES_FILE = DATA_DIR / "roles.json"
    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

    # RAG
    RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "career_pathfinder_rag")
    EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "20"))
    RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.35"))

    # NLP: маппинг «свой навык» → канонический
    SKILL_MAP_SIMILARITY_THRESHOLD = float(os.getenv("SKILL_MAP_SIMILARITY_THRESHOLD", "0.72"))
    # Семантический мэтчинг навыков при gap-анализе
    SKILL_MATCH_THRESHOLD = float(os.getenv("SKILL_MATCH_THRESHOLD", "0.72"))
    SKILL_SUGGESTIONS_TOP_K = int(os.getenv("SKILL_SUGGESTIONS_TOP_K", "5"))
    SUGGESTIONS_MIN_SCORE = float(os.getenv("SUGGESTIONS_MIN_SCORE", "0.35"))

    # Explore: категории по доле совпадения (0..1)
    EXPLORE_CLOSEST_MIN = float(os.getenv("EXPLORE_CLOSEST_MIN", "0.15"))   # >= 15% → ближайшие
    EXPLORE_ADJACENT_MIN = float(os.getenv("EXPLORE_ADJACENT_MIN", "0.05")) # 5–15% → смежные
    EXPLORE_CLOSEST_MAX_ROLES = int(os.getenv("EXPLORE_CLOSEST_MAX", "3"))
    EXPLORE_ADJACENT_MAX_ROLES = int(os.getenv("EXPLORE_ADJACENT_MAX", "3"))
    EXPLORE_FAR_MAX_ROLES = int(os.getenv("EXPLORE_FAR_MAX", "5"))
    EXPLORE_REASONS_TOP_N = 5
    EXPLORE_ADD_SKILLS_TOP_N = 3
    EXPLORE_KEY_SKILLS_TOP_N = 8

    LEVEL_MAP = {1: "Basic", 2: "Proficiency", 3: "Advanced"}
