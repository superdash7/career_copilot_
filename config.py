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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}

class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "4320"))  # 3 days
    # Backward-compatible aliases used in API code.
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", JWT_SECRET)
    JWT_ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_TTL_MINUTES", str(JWT_EXPIRE_MINUTES)))
    JWT_REFRESH_TOKEN_TTL_MINUTES = int(os.getenv("JWT_REFRESH_TOKEN_TTL_MINUTES", "43200"))  # 30 days
    # Backward-compatible alias
    JWT_REFRESH_EXPIRE_MINUTES = int(os.getenv("JWT_REFRESH_EXPIRE_MINUTES", str(JWT_REFRESH_TOKEN_TTL_MINUTES)))
    AUTH_RATE_LIMIT_WINDOW_SEC = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SEC", "60"))
    AUTH_RATE_LIMIT_MAX_ATTEMPTS = int(os.getenv("AUTH_RATE_LIMIT_MAX_ATTEMPTS", "10"))
    # Per-endpoint aliases (same default window budget)
    AUTH_LOGIN_RATE_LIMIT = int(os.getenv("AUTH_LOGIN_RATE_LIMIT", str(AUTH_RATE_LIMIT_MAX_ATTEMPTS)))
    AUTH_REGISTER_RATE_LIMIT = int(os.getenv("AUTH_REGISTER_RATE_LIMIT", str(AUTH_RATE_LIMIT_MAX_ATTEMPTS)))
    LLM_OBSERVABILITY_ENABLED = _env_bool("LLM_OBSERVABILITY_ENABLED", False)
    RESUME_PARSER_MODEL = os.getenv("RESUME_PARSER_MODEL", "gpt-4o")
    RESUME_PARSER_LIGHT_MODEL = os.getenv("RESUME_PARSER_LIGHT_MODEL", "gpt-4o-mini")
    PLAN_GENERATOR_MODEL = os.getenv("PLAN_GENERATOR_MODEL", "gpt-4o")
    PLAN_CONTEXT_MAX_CHARS = int(os.getenv("PLAN_CONTEXT_MAX_CHARS", "12000"))
    RESUME_TEXT_MAX_CHARS = int(os.getenv("RESUME_TEXT_MAX_CHARS", "14000"))
    # Shipped JSON lives in ./data/ in the image. If a Railway volume is mounted on
    # /app/data, that directory hides the image files — use duplicate at ./_data_shipped
    # (created in Dockerfile) for read-only reference data.
    _data_candidate = _PROJECT_DIR / "data"
    _data_shipped = _PROJECT_DIR / "_data_shipped"
    if (_data_shipped / "clean_skills.json").is_file() and not (_data_candidate / "clean_skills.json").is_file():
        DATA_DIR = _data_shipped
    else:
        DATA_DIR = _data_candidate
    DB_PATH = Path(os.getenv("DB_PATH", str(_PROJECT_DIR / "data" / "app.db")))
    SKILLS_FILE = DATA_DIR / "clean_skills.json"
    ATLAS_FILE = DATA_DIR / "atlas_params_clean.json"
    ROLES_FILE = DATA_DIR / "roles.json"
    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

    # RAG
    RAG_COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "career_pathfinder_rag")
    EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    EMBED_MODEL_NAME_V2 = os.getenv("EMBED_MODEL_NAME_V2", "intfloat/multilingual-e5-large-instruct")
    SKILLS_V2_COLLECTION_NAME = os.getenv("SKILLS_V2_COLLECTION_NAME", "skills_v2")
    SKILLS_V2_TOP_K = int(os.getenv("SKILLS_V2_TOP_K", "5"))
    SKILLS_V2_SCORE_THRESHOLD = float(os.getenv("SKILLS_V2_SCORE_THRESHOLD", "0.5"))
    SKILLS_RETRIEVAL_MODE = os.getenv("SKILLS_RETRIEVAL_MODE", "hybrid_rerank")
    SKILLS_HYBRID_DENSE_WEIGHT = float(os.getenv("SKILLS_HYBRID_DENSE_WEIGHT", "0.7"))
    SKILLS_HYBRID_LEXICAL_WEIGHT = float(os.getenv("SKILLS_HYBRID_LEXICAL_WEIGHT", "0.3"))
    SKILLS_HYBRID_MIN_SCORE = float(os.getenv("SKILLS_HYBRID_MIN_SCORE", "0.3"))
    SKILLS_HYBRID_RRF_K = float(os.getenv("SKILLS_HYBRID_RRF_K", "60.0"))
    SKILLS_HYBRID_RERANK_TOP_N = int(os.getenv("SKILLS_HYBRID_RERANK_TOP_N", "20"))
    SKILLS_CROSS_ENCODER_MODEL = os.getenv("SKILLS_CROSS_ENCODER_MODEL", "")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "20"))
    RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.35"))

    # NLP: маппинг «свой навык» → канонический
    SKILL_MAP_SIMILARITY_THRESHOLD = float(os.getenv("SKILL_MAP_SIMILARITY_THRESHOLD", "0.72"))
    # Семантический мэтчинг навыков при gap-анализе
    SKILL_MATCH_THRESHOLD = float(os.getenv("SKILL_MATCH_THRESHOLD", "0.72"))
    SKILL_SUGGESTIONS_TOP_K = int(os.getenv("SKILL_SUGGESTIONS_TOP_K", "5"))
    SUGGESTIONS_MIN_SCORE = float(os.getenv("SUGGESTIONS_MIN_SCORE", "0.35"))

    # Explore: семантика в explore_opportunities (E5-large на каждую роль×грейд очень медленно)
    EXPLORE_FAST_EMBEDDINGS = _env_bool("EXPLORE_FAST_EMBEDDINGS", True)
    # Уже есть semantic_score из explore_opportunities; повторный rank_opportunities — лишний прогон энкодера
    EXPLORE_SKIP_SECOND_RANK = _env_bool("EXPLORE_SKIP_SECOND_RANK", True)

    # Explore: категории по доле совпадения (0..1)
    EXPLORE_CLOSEST_MIN = float(os.getenv("EXPLORE_CLOSEST_MIN", "0.15"))   # >= 15% → ближайшие
    EXPLORE_ADJACENT_MIN = float(os.getenv("EXPLORE_ADJACENT_MIN", "0.05")) # 5–15% → смежные
    EXPLORE_CLOSEST_MAX_ROLES = int(os.getenv("EXPLORE_CLOSEST_MAX", "3"))
    EXPLORE_ADJACENT_MAX_ROLES = int(os.getenv("EXPLORE_ADJACENT_MAX", "3"))
    EXPLORE_FAR_MAX_ROLES = int(os.getenv("EXPLORE_FAR_MAX", "5"))
    EXPLORE_REASONS_TOP_N = 5
    EXPLORE_ADD_SKILLS_TOP_N = 3
    EXPLORE_KEY_SKILLS_TOP_N = 8
    # Explore: фокусный план по выбранным gap-навыкам (мин/макс)
    EXPLORE_PLAN_MIN_SELECTED_SKILLS = int(os.getenv("EXPLORE_PLAN_MIN_SELECTED_SKILLS", "4"))
    EXPLORE_PLAN_MAX_SELECTED_SKILLS = int(os.getenv("EXPLORE_PLAN_MAX_SELECTED_SKILLS", "10"))

    LEVEL_MAP = {1: "Basic", 2: "Proficiency", 3: "Advanced"}
