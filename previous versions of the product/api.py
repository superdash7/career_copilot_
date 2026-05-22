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

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Инициализация модулей (как в main)
from data_loader import DataLoader
from resume_parser import ResumeParser
from gap_analyzer import GapAnalyzer
from scenario_handler import ScenarioHandler
from output_formatter import OutputFormatter

data = DataLoader()
parser = ResumeParser()
analyzer = GapAnalyzer()
scenarios = ScenarioHandler(data)
formatter = OutputFormatter(data)

GRADE_MAP = {
    "Младший (Junior)": "Junior",
    "Специалист (Middle)": "Middle",
    "Старший (Senior)": "Senior",
    "Ведущий (Lead)": "Lead",
    "Эксперт (Expert)": "Expert",
}

app = FastAPI(title="AI Career Pathfinder API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            skills_list = list(data.skills_map.keys())
            result = parser.parse_skills(text, skills_list)
            try:
                from rag_service import map_to_canonical_skill
                for s in result.get("skills", []):
                    can = map_to_canonical_skill(s.get("name") or "")
                    if can:
                        s["name"] = can
            except Exception:
                pass
            level_mapping = {1: 1, 2: 1.5, 3: 2}
            out = [{"name": s.get("name", ""), "level": level_mapping.get(s.get("level"), 1)} for s in result.get("skills", [])]
            return {"skills": out}
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
    from explore_recommendations import RoleMatch
    try:
        from rag_service import get_rag_why_role_bullets
    except Exception:
        get_rag_why_role_bullets = lambda u, r, **kw: []
    matches = []
    for opp in opps:
        role_title = opp.get("role", "")
        internal = opp.get("internal_role")
        reqs = data.get_role_requirements(internal, "Middle") if internal else {}
        skill_keys = [k for k in reqs.keys() if k not in data.atlas_map]
        matched = [{"name": s} for s in user_skills if s in reqs][:5]
        missing = [{"name": s} for s in skill_keys if s not in user_skills][:3]
        why = get_rag_why_role_bullets(user_skills, role_title, top_k=5)
        score = (opp.get("match", 0) or 0) / 100.0
        matches.append(RoleMatch(
            role_title=role_title,
            match_score=score,
            why_match=why,
            matched_skills=matched,
            key_skills=skill_keys[:8],
            missing_skills=missing,
            internal_role=internal,
        ))
    return matches


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
        return {
            "title": c.title, "match": round(c.match_score * 100),
            "category": category, "match_label": c.match_label,
            "missing": c.add_skills[:5], "key_skills": c.key_skills[:8],
            "reasons": c.reasons[:5],
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
            try:
                from rag_service import rank_opportunities
                opps = rank_opportunities(user_skills, opps, data)
            except Exception:
                pass
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

    grade_key = GRADE_MAP.get(req.grade, "Middle")
    grade_sequence = ["Junior", "Middle", "Senior", "Lead", "Expert"]
    idx = grade_sequence.index(grade_key) if grade_key in grade_sequence else 1
    target_grade = grade_sequence[min(idx + 1, len(grade_sequence) - 1)]

    skill_details = []
    for name in req.selected_skills[:10]:
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
    prompt = f"""Пользователь выбрал навыки для развития: {', '.join(req.selected_skills)}.
Профессия: {req.profession}, грейд: {req.grade}, цель: {target}, сценарий: {req.scenario}.

Данные по навыкам:
{skill_context}

Сгенерируй РОВНО три JSON-блока. Отвечай ТОЛЬКО валидным JSON без markdown.

{{
  "tasks": [
    {{"skill": "название навыка", "items": ["конкретная задача 1", "конкретная задача 2"]}}
  ],
  "communication": ["рекомендация по развитию через общение 1", "рекомендация 2", "рекомендация 3"],
  "learning": ["конкретная книга/курс/ресурс 1", "ресурс 2", "ресурс 3"]
}}

Правила:
- tasks: для КАЖДОГО выбранного навыка 2-3 конкретные задачи, опираясь на данные выше
- communication: 3-5 рекомендаций по менторству, code review, обратной связи
- learning: 3-5 конкретных книг, курсов или ресурсов на русском или английском
- Отвечай на русском
- Только JSON, без пояснений"""

    import json as _json
    last_error = None
    for attempt in range(3):
        try:
            response = gen.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Отвечай только валидным JSON. Без markdown, без пояснений."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            result = _json.loads(response.choices[0].message.content)
            if "tasks" not in result:
                result["tasks"] = []
            if "communication" not in result:
                result["communication"] = []
            if "learning" not in result:
                result["learning"] = []
            return result
        except Exception as e:
            last_error = e
            import time; time.sleep(1)

    raise HTTPException(status_code=500, detail=f"Ошибка генерации: {last_error}")


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


import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("career-pathfinder")

@app.on_event("startup")
async def on_startup():
    port = os.environ.get("PORT", "?")
    fe = "YES" if FRONTEND_DIR.is_dir() else "NO"
    logger.info(f"=== Career Pathfinder started === PORT={port}, frontend={fe}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting uvicorn on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
