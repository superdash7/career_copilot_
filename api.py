"""
REST API для AI Career Pathfinder (для подключения отдельного фронтенда).
Запуск: uvicorn api:app --reload --host 127.0.0.1 --port 8000
"""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if os.getcwd() != str(PROJECT_DIR):
    os.chdir(PROJECT_DIR)

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import hashlib
import uuid
import json
import jwt
import bcrypt

# Инициализация модулей (как в main)
from data_loader import DataLoader
from resume_parser import ResumeParser
from gap_analyzer import GapAnalyzer
from scenario_handler import ScenarioHandler
from output_formatter import OutputFormatter
from confidence_utils import get_skill_confidence
from db import get_db_connection, init_db
from config import Config
from rate_limiter import check_rate_limit_or_raise

data = DataLoader()
parser = ResumeParser()
analyzer = GapAnalyzer()
scenarios = ScenarioHandler(data)
formatter = OutputFormatter(data)
auth_scheme = HTTPBearer(auto_error=False)

GRADE_MAP = {
    "Младший (Junior)": "Junior",
    "Специалист (Middle)": "Middle",
    "Старший (Senior)": "Senior",
    "Ведущий (Lead)": "Lead",
    "Эксперт (Expert)": "Expert",
}

import logging as _logging
_logging.basicConfig(level=_logging.INFO)
_logger = _logging.getLogger("career-pathfinder")


@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()

    if Config.JWT_SECRET == "change-me-in-production":
        _logger.warning(
            "JWT_SECRET is using the default value! "
            "Set JWT_SECRET environment variable in production."
        )

    db_path = str(Config.DB_PATH)
    _logger.info(f"DB path: {db_path}")
    if not Config.DB_PATH.exists():
        _logger.warning(f"DB file does not exist yet: {db_path}")

    port = os.environ.get("PORT", "?")
    fe_dir = PROJECT_DIR / "frontend" / "dist"
    fe = "YES" if fe_dir.is_dir() else "NO"
    _logger.info(f"=== Career Pathfinder started === PORT={port}, frontend={fe}")

    yield


app = FastAPI(title="AI Career Pathfinder API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _create_access_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=Config.JWT_ACCESS_TOKEN_TTL_MINUTES)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def _create_refresh_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=Config.JWT_REFRESH_TOKEN_TTL_MINUTES)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(payload, Config.JWT_SECRET, algorithm=Config.JWT_ALGORITHM)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _store_refresh_token(user_id: str, refresh_token: str) -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=Config.JWT_REFRESH_TOKEN_TTL_MINUTES)
    token_hash = _hash_token(refresh_token)
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO refresh_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, now.isoformat(), expires_at.isoformat()),
        )
        conn.commit()


def _revoke_refresh_token(refresh_token: str) -> None:
    token_hash = _hash_token(refresh_token)
    with get_db_connection() as conn:
        conn.execute("DELETE FROM refresh_tokens WHERE token_hash = ?", (token_hash,))
        conn.commit()


def _is_refresh_token_active(refresh_token: str) -> bool:
    token_hash = _hash_token(refresh_token)
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT expires_at FROM refresh_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
    if row is None:
        return False
    expires_at = row["expires_at"] or ""
    try:
        exp_dt = datetime.fromisoformat(expires_at)
    except Exception:
        return False
    return exp_dt > datetime.now(timezone.utc)


def _get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, email, created_at, experience_level, pain_point, development_hours_per_week "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "created_at": row["created_at"],
        "experience_level": row["experience_level"],
        "pain_point": row["pain_point"],
        "development_hours_per_week": row["development_hours_per_week"],
    }


def _get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(auth_scheme),
) -> Dict[str, Any]:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    token = credentials.credentials
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Неверный тип токена")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Недействительный токен")
    user = _get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Пользователь не найден",
                "code": "USER_NOT_FOUND",
            },
        )
    return user


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class OnboardingRequest(BaseModel):
    experience_level: str
    pain_point: str
    development_hours_per_week: int


class AnalysisCreateRequest(BaseModel):
    scenario: str
    current_role: Optional[str] = None
    target_role: Optional[str] = None
    skills_json: Dict[str, Any] = {}
    result_json: Dict[str, Any] = {}


class ProgressPatchRequest(BaseModel):
    skill_name: str
    status: str


def _serialize_analysis_row(row: Any) -> Dict[str, Any]:
    skills_json = row["skills_json"] or "{}"
    result_json = row["result_json"] or "{}"
    try:
        skills = json.loads(skills_json)
    except Exception:
        skills = {}
    try:
        result = json.loads(result_json)
    except Exception:
        result = {}
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "scenario": row["scenario"],
        "current_role": row["current_role"],
        "target_role": row["target_role"],
        "skills_json": skills,
        "result_json": result,
        "created_at": row["created_at"],
    }


def _recommend_scenario_from_pain_point(pain_point: str) -> str:
    mapping = {
        "рост": "Следующий грейд",
        "смена": "Смена профессии",
        "стагнация": "Исследование возможностей",
        "неопределённость": "Исследование возможностей",
    }
    return mapping.get((pain_point or "").strip().lower(), "Исследование возможностей")


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    check_rate_limit_or_raise(
        f"register:{(req.email or '').strip().lower()}",
        limit=Config.AUTH_REGISTER_RATE_LIMIT,
        window_sec=Config.AUTH_RATE_LIMIT_WINDOW_SEC,
    )
    email = (req.email or "").strip().lower()
    password = req.password or ""
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="Введите корректный email")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Пароль должен быть не короче 8 символов")

    with get_db_connection() as conn:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, _hash_password(password), _utc_now_iso()),
        )
        conn.commit()

    token = _create_access_token(user_id=user_id, email=email)
    refresh_token = _create_refresh_token(user_id=user_id, email=email)
    _store_refresh_token(user_id, refresh_token)
    user = _get_user_by_id(user_id)
    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@app.post("/api/auth/login")
def login(req: LoginRequest):
    email = (req.email or "").strip().lower()
    check_rate_limit_or_raise(
        f"login:{email}",
        limit=Config.AUTH_LOGIN_RATE_LIMIT,
        window_sec=Config.AUTH_RATE_LIMIT_WINDOW_SEC,
    )
    password = req.password or ""
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if row is None or not _verify_password(password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    token = _create_access_token(user_id=row["id"], email=row["email"])
    refresh_token = _create_refresh_token(user_id=row["id"], email=row["email"])
    _store_refresh_token(row["id"], refresh_token)
    user = _get_user_by_id(row["id"])
    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@app.post("/api/auth/refresh")
def refresh_access_token(req: RefreshRequest):
    token = (req.refresh_token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Требуется refresh_token")
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=[Config.JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Недействительный refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Неверный тип токена")
    if not _is_refresh_token_active(token):
        raise HTTPException(status_code=401, detail="Refresh token неактивен")
    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=401, detail="Некорректный refresh token")
    access = _create_access_token(user_id=user_id, email=email)
    new_refresh = _create_refresh_token(user_id=user_id, email=email)
    _store_refresh_token(user_id, new_refresh)
    _revoke_refresh_token(token)
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}


@app.post("/api/auth/logout")
def logout(req: LogoutRequest):
    token = (req.refresh_token or "").strip()
    if token:
        _revoke_refresh_token(token)
    return {"ok": True}


@app.get("/api/auth/me")
def me(current_user: Dict[str, Any] = Depends(_get_current_user)):
    return {"user": current_user}


@app.get("/api/share/{analysis_id}")
def get_shared_analysis(analysis_id: str):
    """
    Публичный read-only доступ к результату анализа по его ID.
    Используется для шаринга карточки результата.
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, scenario, current_role, target_role, result_json, created_at "
            "FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Публичный результат не найден")

    try:
        result_json = json.loads(row["result_json"] or "{}")
    except Exception:
        raise HTTPException(status_code=404, detail="Публичный результат не найден")

    markdown = result_json.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        raise HTTPException(status_code=404, detail="Публичный результат не найден")

    out: Dict[str, Any] = {
        "analysis_id": row["id"],
        "markdown": markdown,
        "scenario": row["scenario"],
        "current_role": row["current_role"],
        "target_role": row["target_role"],
        "created_at": row["created_at"],
    }
    if isinstance(result_json.get("role_titles"), list):
        out["role_titles"] = result_json.get("role_titles")
    if isinstance(result_json.get("analysis"), dict):
        out["analysis"] = result_json.get("analysis")
    return out


@app.patch("/api/auth/onboarding")
def save_onboarding(
    req: OnboardingRequest,
    current_user: Dict[str, Any] = Depends(_get_current_user),
):
    experience_level = (req.experience_level or "").strip()
    pain_point = (req.pain_point or "").strip().lower()
    hours = int(req.development_hours_per_week or 0)

    if not experience_level:
        raise HTTPException(status_code=400, detail="Укажите уровень опыта")
    if len(experience_level) > 80:
        raise HTTPException(status_code=400, detail="Слишком длинное значение опыта")
    if pain_point not in {"рост", "смена", "стагнация", "неопределённость"}:
        raise HTTPException(status_code=400, detail="Некорректная болевая точка")
    if hours < 1 or hours > 40:
        raise HTTPException(status_code=400, detail="Укажите время развития в диапазоне 1-40 часов в неделю")

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE users SET experience_level = ?, pain_point = ?, development_hours_per_week = ? WHERE id = ?",
            (experience_level, pain_point, hours, current_user["id"]),
        )
        conn.commit()

    user = _get_user_by_id(current_user["id"])
    return {
        "user": user,
        "recommended_scenario": _recommend_scenario_from_pain_point(pain_point),
    }


@app.get("/api/analyses")
def get_analyses(current_user: Dict[str, Any] = Depends(_get_current_user)):
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, scenario, current_role, target_role, skills_json, result_json, created_at "
            "FROM analyses WHERE user_id = ? ORDER BY created_at DESC",
            (current_user["id"],),
        ).fetchall()
    return {"items": [_serialize_analysis_row(row) for row in rows]}


@app.post("/api/analyses")
def create_analysis(
    req: AnalysisCreateRequest,
    current_user: Dict[str, Any] = Depends(_get_current_user),
):
    analysis_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO analyses (id, user_id, scenario, current_role, target_role, skills_json, result_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                analysis_id,
                current_user["id"],
                req.scenario,
                req.current_role,
                req.target_role,
                json.dumps(req.skills_json, ensure_ascii=False),
                json.dumps(req.result_json, ensure_ascii=False),
                _utc_now_iso(),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, user_id, scenario, current_role, target_role, skills_json, result_json, created_at "
            "FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()
    return {"item": _serialize_analysis_row(row)}


@app.get("/api/analyses/{analysis_id}")
def get_analysis_detail(
    analysis_id: str,
    current_user: Dict[str, Any] = Depends(_get_current_user),
):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, user_id, scenario, current_role, target_role, skills_json, result_json, created_at "
            "FROM analyses WHERE id = ? AND user_id = ?",
            (analysis_id, current_user["id"]),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Анализ не найден")
    return {"item": _serialize_analysis_row(row)}


@app.get("/api/progress")
def get_progress(current_user: Dict[str, Any] = Depends(_get_current_user)):
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_id, skill_name, status, updated_at "
            "FROM progress WHERE user_id = ? ORDER BY updated_at DESC",
            (current_user["id"],),
        ).fetchall()
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "skill_name": row["skill_name"],
                "status": row["status"],
                "updated_at": row["updated_at"],
            }
        )
    return {"items": items}


@app.patch("/api/progress")
def patch_progress(
    req: ProgressPatchRequest,
    current_user: Dict[str, Any] = Depends(_get_current_user),
):
    status = (req.status or "").strip()
    if status not in {"todo", "in_progress", "done"}:
        raise HTTPException(status_code=400, detail="Некорректный статус прогресса")
    skill_name = (req.skill_name or "").strip()
    if not skill_name:
        raise HTTPException(status_code=400, detail="Укажите skill_name")

    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM progress WHERE user_id = ? AND skill_name = ?",
            (current_user["id"], skill_name),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE progress SET status = ?, updated_at = ? WHERE id = ?",
                (status, _utc_now_iso(), existing["id"]),
            )
            progress_id = existing["id"]
        else:
            progress_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO progress (id, user_id, skill_name, status, updated_at) VALUES (?, ?, ?, ?, ?)",
                (progress_id, current_user["id"], skill_name, status, _utc_now_iso()),
            )
        conn.commit()
        row = conn.execute(
            "SELECT id, user_id, skill_name, status, updated_at FROM progress WHERE id = ?",
            (progress_id,),
        ).fetchone()
    return {
        "item": {
            "id": row["id"],
            "user_id": row["user_id"],
            "skill_name": row["skill_name"],
            "status": row["status"],
            "updated_at": row["updated_at"],
        }
    }


@app.get("/api/professions")
def get_professions():
    """Список профессий для выбора."""
    try:
        return {"professions": data.get_all_roles()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/skills-for-role")
def get_skills_for_role(profession: str):
    """Навыки скиллсета для данной профессии."""
    if not profession:
        return {"skills": []}
    return {"skills": data.get_skills_for_role(profession)}


@app.get("/api/skills-by-category")
def get_skills_by_category(profession: str):
    """
    Навыки с разбивкой по категориям для ручного выбора.
    Возвращает: {"categories": [{"name": str, "skills": [str, ...]}, ...]}
    """
    if not profession:
        return {"categories": []}
    try:
        categories = data.get_skills_by_category_for_role(profession)
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/suggest-skills")
def suggest_skills(q: str = ""):
    """Подсказки навыков по строке (синонимы + RAG)."""
    if not q or len(q.strip()) < 2:
        return {"suggestions": []}
    suggestions = []
    try:
        from skill_normalizer import resolve_to_canonical, get_canonical_skills_set
        canonical_set = get_canonical_skills_set()
        by_syn = resolve_to_canonical(q.strip(), canonical_set)
        if by_syn:
            suggestions.append(by_syn)
    except Exception:
        pass
    try:
        from rag_service import suggest_skills as rag_suggest
        for s in rag_suggest(q.strip()):
            if s and s not in suggestions:
                suggestions.append(s)
    except Exception:
        pass
    return {"suggestions": suggestions[:8]}


@app.post("/api/analyze-resume")
async def analyze_resume(file: UploadFile = File(...)):
    """Загрузка PDF, извлечение навыков. Возвращает список [{name, level}]."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Нужен PDF файл")
    if not parser.client:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY не задан")
    try:
        contents = await file.read()
        tmp = Path(PROJECT_DIR) / "_tmp_resume.pdf"
        tmp.write_bytes(contents)
        try:
            text = parser.extract_text(tmp)
            if not text or not text.strip():
                return {"skills": [], "error": "Не удалось извлечь текст из PDF"}
            skills_dicts = data.skills
            canonical_names = [s.get("Навык") or s.get("name") for s in skills_dicts]
            result = parser.parse_skills(text, skills_dicts)

            level_mapping = {0: 0, 1: 1, 2: 1.5, 3: 2}

            out = []
            for s in result.get("skills", []):
                raw_name = (s.get("raw_name") or s.get("name") or "").strip()
                name = (s.get("name") or "").strip()
                if not name:
                    continue

                confidence, band = get_skill_confidence(s)
                alternatives = []

                cands = s.get("candidates") or []
                for c in cands[:3]:
                    cname = (c.get("name") or "").strip()
                    cscore = c.get("score")
                    if not cname:
                        continue
                    try:
                        cscore = float(cscore) if cscore is not None else None
                    except Exception:
                        cscore = None
                    alternatives.append({"name": cname, "score": cscore})

                out.append(
                    {
                        "raw_name": raw_name,
                        "name": name,
                        "level": level_mapping.get(s.get("level"), 1),
                        "confidence": confidence,
                        "confidence_band": band,
                        "alternatives": alternatives,
                        "evidence": s.get("evidence", ""),
                        "resume_evidence_span": s.get("resume_evidence_span", ""),
                        "source_skill_id": s.get("source_skill_id"),
                        "retrieval_mode": s.get("retrieval_mode"),
                        "retrieval_trace": s.get("retrieval_trace", {}),
                    }
                )

            return {
                "skills": out,
                "used_fallback": bool(result.get("used_fallback", False)),
                "version": "v2",
            }
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PlanRequest(BaseModel):
    profession: str
    grade: str  # ключ из GRADE_MAP, например "Специалист (Middle)"
    skills: List[dict]  # [{"name": str, "level": float}]
    scenario: str  # "Следующий грейд" | "Смена профессии" | "Исследование возможностей"
    target_profession: Optional[str] = None


def _skills_table_to_user_skills(skills: List[dict]) -> dict:
    """Конвертирует навыки фронтенда (float 0..2) во внутренние уровни (1..3) с нормализацией имён.
    Маппинг по спецификации: 0-0.5→Basic(1), 1-1.5→Proficiency(2), 2→Advanced(3).
    Навык на уровне 0 «Нет навыка» = пользователь явно указал отсутствие → Basic(1)."""
    raw = {}
    for item in skills:
        name = (item.get("name") or "").strip()
        if not name or name == "Навык" or name.startswith("⚠️"):
            continue
        try:
            level = float(item.get("level", 1))
        except (TypeError, ValueError):
            continue
        if level != level:
            continue
        if level <= 0.5:
            internal_level = 1   # Basic
        elif level <= 1.5:
            internal_level = 2   # Proficiency
        else:
            internal_level = 3   # Advanced
        raw[name] = internal_level

    try:
        from skill_normalizer import resolve_to_canonical, get_canonical_skills_set
        canonical_set = get_canonical_skills_set()
        normalized = {}
        for name, level in raw.items():
            canonical = resolve_to_canonical(name, canonical_set)
            key = canonical if canonical else name
            if key not in normalized or level > normalized[key]:
                normalized[key] = level
        return normalized
    except Exception:
        return raw


def _dedupe_opportunities(opportunities):
    by_internal = {}
    for opp in opportunities:
        internal = opp.get("internal_role")
        if not internal:
            continue
        cur = (opp.get("semantic_score", 0), opp.get("match", 0))
        if internal not in by_internal or cur > (by_internal[internal].get("semantic_score", 0), by_internal[internal].get("match", 0)):
            by_internal[internal] = dict(opp)
    result = list(by_internal.values())
    result.sort(key=lambda x: (-x.get("semantic_score", 0), -x.get("match", 0)))
    for o in result:
        if " (" in o.get("role", ""):
            o["role"] = o["role"].split(" (")[0].strip()
    return result[:30]


def _build_role_matches(opps, user_skills):
    """Строит RoleMatch для explore; RAG why_match запрашивается параллельно (раньше — N последовательных HTTP)."""
    from concurrent.futures import ThreadPoolExecutor
    from explore_recommendations import RoleMatch
    try:
        from rag_service import get_rag_why_role_bullets
    except Exception:
        get_rag_why_role_bullets = lambda u, r, **kw: []

    def _one(opp: Dict[str, Any]) -> RoleMatch:
        role_title = opp.get("role", "")
        internal = opp.get("internal_role")
        reqs = data.get_role_requirements(internal, "Middle") if internal else {}
        skill_keys = [k for k in reqs.keys() if k not in data.atlas_map]
        matched = [
            {"name": s}
            for s in skill_keys
            if user_skills.get(s, 0) >= reqs.get(s, 0)
        ][:5]
        missing = [{"name": s} for s in skill_keys if user_skills.get(s, 0) < reqs.get(s, 0)]
        why = get_rag_why_role_bullets(
            user_skills, role_title, top_k=5, atlas_keys=set(data.atlas_map.keys())
        )
        score = (opp.get("match", 0) or 0) / 100.0
        return RoleMatch(
            role_title=role_title,
            match_score=score,
            why_match=why,
            matched_skills=matched,
            key_skills=skill_keys[:8],
            missing_skills=missing,
            internal_role=internal,
        )

    if not opps:
        return []
    # Sequential-ish RAG: many parallel retrieves still serialize on embed lock and overload Qdrant.
    max_workers = min(2, max(1, len(opps)))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_one, opps))


def _build_growth_analysis(structured, current_grade, target_grade):
    from data_loader import PARAM_ORDINAL_NAMES, SKILL_LEVEL_NAMES
    radar = []
    for g in structured.get("atlas_gaps", []):
        radar.append({"param": g["name"], "current": g["current"], "target": g["required"],
                       "current_label": PARAM_ORDINAL_NAMES.get(g["current"], ""), "target_label": PARAM_ORDINAL_NAMES.get(g["required"], "")})
    for s in structured.get("atlas_strong", []):
        radar.append({"param": s["name"], "current": s["level"], "target": s["level"],
                       "current_label": PARAM_ORDINAL_NAMES.get(s["level"], ""), "target_label": PARAM_ORDINAL_NAMES.get(s["level"], "")})
    skill_gaps = []
    for g in structured.get("skill_gaps", []):
        detail = data.get_skill_detail(g["name"], target_grade)
        skill_gaps.append({
            "name": g["name"], "current": g["current"], "required": g["required"], "delta": g["delta"],
            "level_key": detail["level_key"] if detail else "",
            "description": (detail["description"] if detail else ""),
            "tasks": (detail["tasks"] if detail else ""),
        })
    skill_strong = [{"name": s["name"], "level": s["level"]} for s in structured.get("skill_strong", [])]
    return {
        "scenario": "growth",
        "current_grade": current_grade,
        "target_grade": target_grade,
        "match_percent": structured.get("match_percent", 0),
        "radar_data": radar,
        "skill_gaps": skill_gaps[:20],
        "skill_strong": skill_strong[:15],
    }


def _build_switch_analysis(switch_vm, from_role, to_role):
    transferable = [{"name": m.get("name", ""), "snippet": m.get("snippet", "")} for m in switch_vm.matched_skills]
    gaps = []
    for m in switch_vm.missing_skills:
        detail = data.get_skill_detail(m.get("name", ""), "Middle")
        gaps.append({
            "name": m.get("name", ""),
            "importance": m.get("importance", ""),
            "level_key": detail["level_key"] if detail else "",
            "description": (detail["description"] if detail else ""),
            "tasks": (detail["tasks"] if detail else ""),
        })
    return {
        "scenario": "switch",
        "from_role": from_role,
        "to_role": to_role,
        "match_percent": int(switch_vm.match_score * 100),
        "baseline_level": switch_vm.baseline_level,
        "transferable": transferable,
        "gaps": gaps,
        "suggested_tracks": switch_vm.suggested_tracks,
    }


def _build_explore_analysis(view_model):
    def card_to_dict(c, category):
        summary = ". ".join(c.reasons[:3]).strip()
        summary = summary[:220]
        return {
            "title": c.title, "match": round(c.match_score * 100),
            "category": category, "match_label": c.match_label,
            "missing": c.missing_skills, "key_skills": c.key_skills[:8],
            "reasons": c.reasons[:5],
            "summary": summary,
        }
    roles = []
    for c in view_model.closest:
        roles.append(card_to_dict(c, "closest"))
    for c in view_model.adjacent:
        roles.append(card_to_dict(c, "adjacent"))
    for c in view_model.far:
        roles.append(card_to_dict(c, "far"))
    return {"scenario": "explore", "roles": roles}


@app.post("/api/plan")
def build_plan_api(req: PlanRequest):
    """Построение плана. Возвращает { markdown, role_titles?, analysis? }."""
    if not req.skills:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы один навык")
    if not req.profession:
        raise HTTPException(status_code=400, detail="Выберите профессию")
    if req.scenario == "Смена профессии" and not req.target_profession:
        raise HTTPException(status_code=400, detail="Выберите целевую профессию")

    skills_table = [[s.get("name"), s.get("level", 1)] for s in req.skills]
    user_skills = _skills_table_to_user_skills(req.skills)
    if not user_skills:
        raise HTTPException(status_code=400, detail="В списке нет корректных навыков")

    grade_key = GRADE_MAP.get(req.grade, "Middle")
    atlas_param_names = list(data.atlas_map.keys())
    role_titles = []

    # Проставляем atlas-параметры по текущему грейду (5-level ordinal)
    from data_loader import GRADE_TO_PARAM_ORDINAL
    current_param_ordinal = GRADE_TO_PARAM_ORDINAL.get(grade_key, 2)
    for param_name in atlas_param_names:
        if param_name not in user_skills:
            user_skills[param_name] = current_param_ordinal

    try:
        analysis = {}

        if req.scenario == "Следующий грейд":
            profession_internal = data.get_internal_role_name(req.profession)
            reqs, role_name = scenarios.next_grade(profession_internal, grade_key, user_skills)
            structured = analyzer.analyze_structured(
                user_skills, reqs, atlas_param_names, data.atlas_map
            )
            grade_sequence = ["Junior", "Middle", "Senior", "Lead", "Expert"]
            current_index = grade_sequence.index(grade_key) if grade_key in grade_sequence else 1
            next_index = min(current_index + 1, len(grade_sequence) - 1)
            target_grade = grade_sequence[next_index]
            md = formatter.format_next_grade(
                structured, role_name, req.profession,
                current_grade=grade_key, target_grade=target_grade, profession_internal=profession_internal,
            )
            analysis = _build_growth_analysis(structured, grade_key, target_grade)

        elif req.scenario == "Смена профессии":
            target_internal = data.get_internal_role_name(req.target_profession)
            try:
                from switch_profession_service import build_switch_comparison
                switch_vm = build_switch_comparison(user_skills, target_internal, "Middle", data)
                role_name = f"{req.target_profession} ({switch_vm.baseline_level} → Middle)"
                md = formatter.format_change_profession(switch_vm, role_name, req.target_profession)
                analysis = _build_switch_analysis(switch_vm, req.profession, req.target_profession)
            except Exception:
                reqs, role_name = scenarios.change_profession(target_internal, user_skills)
                structured = analyzer.analyze_structured(
                    user_skills, reqs, atlas_param_names, data.atlas_map
                )
                md = formatter.format_change_profession_legacy(structured, role_name, req.target_profession)

        else:
            opps = scenarios.explore_opportunities(user_skills)
            # semantic_score уже посчитан в explore_opportunities; повторный rank — лишняя загрузка MiniLM
            if not getattr(Config, "EXPLORE_SKIP_SECOND_RANK", True):
                try:
                    from rag_service import rank_opportunities
                    opps = rank_opportunities(user_skills, opps, data)
                except Exception:
                    pass
            else:
                opps.sort(
                    key=lambda x: (-x.get("semantic_score", 0), -x.get("match", 0), x.get("role", ""))
                )
            opps = _dedupe_opportunities(opps)
            matches = _build_role_matches(opps, user_skills)
            from explore_recommendations import build_explore_recommendations
            view_model = build_explore_recommendations(matches)
            role_titles = [c.title for c in view_model.closest + view_model.adjacent + view_model.far]
            md = formatter.format_explore(view_model, user_skills)
            analysis = _build_explore_analysis(view_model)

        out = {"markdown": md}
        if role_titles:
            out["role_titles"] = role_titles
        if analysis:
            out["analysis"] = analysis
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class FocusedPlanRequest(BaseModel):
    profession: str
    grade: str
    scenario: str
    target_profession: Optional[str] = None
    selected_skills: List[str]


@app.post("/api/focused-plan")
def focused_plan_api(req: FocusedPlanRequest):
    """Генерирует фокусный план по выбранным навыкам. Возвращает {tasks, communication, learning}."""
    if not req.selected_skills:
        raise HTTPException(status_code=400, detail="Выберите хотя бы один навык")
    if req.scenario == "Исследование возможностей":
        n = len(req.selected_skills)
        lo = Config.EXPLORE_PLAN_MIN_SELECTED_SKILLS
        hi = Config.EXPLORE_PLAN_MAX_SELECTED_SKILLS
        if n < lo or n > hi:
            raise HTTPException(
                status_code=400,
                detail=f"Для плана выберите от {lo} до {hi} навыков",
            )

    grade_key = GRADE_MAP.get(req.grade, "Middle")
    grade_sequence = ["Junior", "Middle", "Senior", "Lead", "Expert"]
    idx = grade_sequence.index(grade_key) if grade_key in grade_sequence else 1
    target_grade = grade_sequence[min(idx + 1, len(grade_sequence) - 1)]

    skill_details = []
    if req.scenario == "Исследование возможностей":
        cap = Config.EXPLORE_PLAN_MAX_SELECTED_SKILLS
        selected_skills = req.selected_skills[:cap]
    else:
        selected_skills = req.selected_skills[:10]
    for name in selected_skills:
        detail = data.get_skill_detail(name, target_grade)
        if detail:
            skill_details.append(detail)
        else:
            skill_details.append({"skill_name": name, "level_key": "", "description": "", "tasks": ""})

    from plan_generator import PlanGenerator
    gen = PlanGenerator()
    if not gen.client:
        return {
            "tasks": [{"skill": s["skill_name"], "items": [s["tasks"] or "Практика в рабочих задачах"]} for s in skill_details],
            "communication": ["Обсудите приоритеты с руководителем", "Запросите обратную связь от коллег"],
            "learning": ["Изучите материалы по выбранным навыкам"],
        }

    skill_context = ""
    for s in skill_details:
        block = f"Навык: {s['skill_name']}"
        if s.get("description"):
            block += f"\nОписание уровня ({s['level_key']}): {s['description']}"
        if s.get("tasks"):
            block += f"\nЗадачи на развитие: {s['tasks']}"
        skill_context += block + "\n\n"

    target = req.target_profession or req.profession
    return gen.generate_focused_plan_json(
        selected_skills=selected_skills,
        profession=req.profession,
        grade=req.grade,
        scenario=req.scenario,
        target_name=target,
        skill_context=skill_context,
    )


@app.get("/health")
def health():
    return {"status": "ok"}




FRONTEND_DIR = PROJECT_DIR / "frontend" / "dist"

if FRONTEND_DIR.is_dir():
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        index = FRONTEND_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return {"detail": "Not found"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    _logger.info(f"Starting uvicorn on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
