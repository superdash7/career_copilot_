
from openai import OpenAI
from pypdf import PdfReader
import json
from config import Config
from pydantic import BaseModel, ValidationError, Field
from typing import Dict, List, Optional, Any

from rag_service import get_skills_v2_candidates
from llm_observability import LLMCallMetrics, log_llm_call


class _ExtractSkillsResponse(BaseModel):
    skills: List[str] = Field(default_factory=list)


class _RerankResponse(BaseModel):
    match: str = ""
    confidence: Optional[float] = None


class _UnknownSkillResponse(BaseModel):
    is_skill: bool = False
    confidence: Optional[float] = None


class _LevelResponse(BaseModel):
    level: int = 1
    evidence: str = ""


class _BatchRerankItem(BaseModel):
    raw_skill: str = ""
    match: str = ""
    confidence: Optional[float] = None


class _BatchRerankResponse(BaseModel):
    results: List[_BatchRerankItem] = Field(default_factory=list)


class _BatchLevelItem(BaseModel):
    skill: str = ""
    level: int = 1
    evidence: str = ""


class _BatchLevelResponse(BaseModel):
    results: List[_BatchLevelItem] = Field(default_factory=list)


_BATCH_RERANK_LIMIT = 12
_BATCH_LEVEL_LIMIT = 10


class ResumeParser:
    def __init__(self):
        self._api_key = Config.OPENAI_API_KEY
        self.client = OpenAI(api_key=self._api_key) if self._api_key else None

    def extract_text(self, pdf_path):
        if pdf_path is None:
            return ""
        path = getattr(pdf_path, "name", pdf_path)
        if isinstance(path, bytes):
            path = path.decode("utf-8")
        text = ""
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        max_len = getattr(Config, "RESUME_TEXT_MAX_CHARS", 14000)
        if len(text) > max_len:
            text = text[:max_len] + "\n\n[Текст обрезан. Извлеки навыки из приведённой части.]"
        return text

    def _validate_payload(self, schema_cls: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            model = schema_cls(**(payload or {}))
            return model.model_dump()
        except ValidationError:
            return schema_cls().model_dump()

    def _run_json_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int = 1800,
        operation: str = "generic_json_chat",
        schema_cls: Optional[Any] = None,
        request_id: Optional[str] = None,
        use_light_model: bool = False,
    ) -> Dict:
        model = getattr(Config, "RESUME_PARSER_LIGHT_MODEL", "gpt-4o-mini") if use_light_model else getattr(Config, "RESUME_PARSER_MODEL", "gpt-4o")
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        start_ms = None
        if Config.LLM_OBSERVABILITY_ENABLED:
            import time as _time
            start_ms = int(_time.time() * 1000)
        last_error = None
        for _attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                raw = response.choices[0].message.content
                payload = json.loads(raw)
                if schema_cls is not None:
                    payload = self._validate_payload(schema_cls, payload)
                if Config.LLM_OBSERVABILITY_ENABLED:
                    import time as _time
                    latency = int(_time.time() * 1000) - int(start_ms or 0)
                    log_llm_call(
                        LLMCallMetrics(
                            component="resume_parser",
                            operation=operation,
                            model=model,
                            request_id=request_id,
                            success=True,
                            latency_ms=latency,
                            prompt_chars=prompt_chars,
                            completion_chars=len(raw or ""),
                        )
                    )
                return payload
            except Exception as e:
                last_error = e
                continue
        if Config.LLM_OBSERVABILITY_ENABLED:
            import time as _time
            latency = int(_time.time() * 1000) - int(start_ms or 0)
            log_llm_call(
                LLMCallMetrics(
                    component="resume_parser",
                    operation=operation,
                    model=model,
                    request_id=request_id,
                    success=False,
                    latency_ms=latency,
                    prompt_chars=prompt_chars,
                    completion_chars=0,
                    error=str(last_error),
                )
            )
        if schema_cls is not None:
            return schema_cls().model_dump()
        return {}

    def _legacy_parse_skills(self, resume_text, allowed_skills):
        """Старый монолитный extraction: extraction+normalization+level одним вызовом."""
        if not self.client:
            raise ValueError(
                "OPENAI_API_KEY не задан. Добавьте ключ в .env для распознавания навыков из PDF."
            )
        model = getattr(Config, "RESUME_PARSER_MODEL", "gpt-4o")
        skills_str = ", ".join(allowed_skills)

        system_prompt = f"""
Ты HR-аналитик. Извлеки навыки из резюме, сопоставь со списком: [{skills_str}].
Оцени уровень 1-3 (1-Junior, 2-Middle, 3-Senior).
Верни только JSON без комментариев: {{"skills": [{{"name": "название навыка", "level": число}}]}}
"""

        for attempt in range(2):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": resume_text}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                raw = response.choices[0].message.content
                data = json.loads(raw)
                if not isinstance(data, dict) or "skills" not in data:
                    data = {"skills": []}
                if not isinstance(data["skills"], list):
                    data["skills"] = []
                return data
            except json.JSONDecodeError:
                if attempt == 0:
                    system_prompt = "Верни строго JSON: {\"skills\": [{\"name\": \"навык\", \"level\": 1}]}. Без markdown и текста вокруг."
                    continue
                return {"skills": []}
            except Exception:
                if attempt == 1:
                    raise
                import time
                time.sleep(1)
        return {"skills": []}

    def _extract_raw_skills(self, resume_text: str, request_id: Optional[str] = None) -> List[str]:
        """Вызов 1: чистое извлечение навыков без уровней и без нормализации.
        Uses multiple few-shot examples for diverse role coverage."""
        system_prompt = (
            "Ты — HR-аналитик. Извлеки только навыки из резюме.\n"
            "Отвечай только валидным JSON: {\"skills\": [\"навык 1\", \"навык 2\"]}\n"
            "ПРАВИЛА:\n"
            "- НЕ извлекай должности (Product Manager, Team Lead, etc.)\n"
            "- НЕ извлекай компании (Яндекс, Google, Сбер)\n"
            "- НЕ извлекай города (Москва, Санкт-Петербург)\n"
            "- НЕ извлекай университеты (МГУ, МФТИ, HSE)\n"
            "- НЕ извлекай названия сертификатов и курсов\n"
            "- НЕ извлекай названия продуктов/команд/проектов как навыки\n"
            "- НЕ извлекай языки общения (русский, английский) — только языки программирования\n"
            "- Удали дубликаты\n"
            "- Короткие формулировки навыков (1–3 слова)\n"
            "- Извлекай как hard skills, так и soft skills"
        )
        result = self._run_json_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": (
                    "Резюме: Работал в Яндексе как Senior Product Manager в Москве. "
                    "Окончил МГУ. Использовал SQL, проводил A/B тесты, строил дашборды в DataLens."
                )},
                {"role": "assistant", "content": "{\"skills\": [\"SQL\", \"A/B тесты\", \"DataLens\"]}"},
                {"role": "user", "content": (
                    "Резюме: Backend-разработчик в Сбере, 4 года. Python, FastAPI, PostgreSQL, Redis. "
                    "Настраивал CI/CD в GitLab, писал юнит-тесты с pytest, деплоил в Kubernetes."
                )},
                {"role": "assistant", "content": "{\"skills\": [\"Python\", \"FastAPI\", \"PostgreSQL\", \"Redis\", \"CI/CD\", \"GitLab\", \"pytest\", \"Kubernetes\"]}"},
                {"role": "user", "content": (
                    "Резюме: UX/UI дизайнер, 3 года. Figma, проведение CustDev интервью, "
                    "создание дизайн-систем, прототипирование, работа с метриками (Amplitude)."
                )},
                {"role": "assistant", "content": "{\"skills\": [\"Figma\", \"CustDev\", \"Дизайн-системы\", \"Прототипирование\", \"Amplitude\"]}"},
                {"role": "user", "content": resume_text},
            ],
            temperature=0.0,
            max_tokens=1500,
            operation="extract_raw_skills",
            schema_cls=_ExtractSkillsResponse,
            request_id=request_id,
        )
        skills = result.get("skills", [])
        if not isinstance(skills, list):
            return []
        clean = []
        seen = set()
        for s in skills:
            name = str(s or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            clean.append(name)
        return clean

    def _batch_rerank_candidates(
        self,
        skills_with_candidates: List[Dict[str, Any]],
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Batch reranking: send multiple skills+candidates in one LLM call.
        Uses gpt-4o-mini for cost efficiency."""
        if not skills_with_candidates:
            return []

        items_json = []
        for item in skills_with_candidates[:_BATCH_RERANK_LIMIT]:
            raw = item["raw_skill"]
            cands = [
                {"name": c.get("name"), "score": round(c.get("score", 0), 3)}
                for c in item["candidates"][:5]
                if c.get("name")
            ]
            items_json.append({"raw_skill": raw, "candidates": cands})

        prompt = (
            "Для каждого навыка пользователя выбери лучший вариант из кандидатов или ответь none.\n\n"
            f"Навыки и кандидаты:\n{json.dumps(items_json, ensure_ascii=False)}\n\n"
            "Верни JSON:\n"
            "{\"results\": [{\"raw_skill\": \"...\", \"match\": \"название или none\", \"confidence\": 0.0-1.0}]}"
        )
        result = self._run_json_chat(
            messages=[
                {"role": "system", "content": "Отвечай только валидным JSON. Никакого markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=2000,
            operation="batch_rerank_candidates",
            request_id=request_id,
            use_light_model=True,
        )
        raw_results = result.get("results", [])
        if not isinstance(raw_results, list):
            return [{"match": None, "confidence": None} for _ in skills_with_candidates]

        by_raw = {}
        for r in raw_results:
            if not isinstance(r, dict):
                continue
            raw_skill = str(r.get("raw_skill", "")).strip()
            match = str(r.get("match", "")).strip()
            if match.lower() == "none":
                match = ""
            conf = r.get("confidence")
            try:
                conf = float(conf) if conf is not None else None
            except Exception:
                conf = None
            by_raw[raw_skill.lower()] = {"match": match or None, "confidence": conf}

        output = []
        for item in skills_with_candidates:
            raw = item["raw_skill"]
            found = by_raw.get(raw.lower(), {"match": None, "confidence": None})
            output.append(found)
        return output

    def _llm_rerank_candidate(
        self,
        raw_skill: str,
        candidates: List[Dict[str, float]],
        request_id: Optional[str] = None,
    ) -> Dict[str, Optional[float]]:
        """Вызов 2: LLM re-ranking по top-5 кандидатам из E5. Single-skill fallback."""
        candidate_names = [c.get("name", "") for c in candidates if c.get("name")]
        if not candidate_names:
            return {"match": None, "confidence": None}

        rich_candidates = []
        for c in candidates[:5]:
            rich_candidates.append(
                {
                    "name": c.get("name"),
                    "score": c.get("score"),
                    "dense_score": c.get("dense_score"),
                    "lexical_score": c.get("lexical_score"),
                }
            )

        prompt = (
            f"Навык пользователя: {raw_skill}\n"
            f"Кандидаты: {json.dumps(rich_candidates, ensure_ascii=False)}\n\n"
            "Выбери лучший вариант из списка или ответь none.\n"
            "Верни только JSON: {\"match\": \"название или none\", \"confidence\": число от 0 до 1}."
        )
        result = self._run_json_chat(
            messages=[
                {"role": "system", "content": "Отвечай только валидным JSON. Никакого markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=300,
            operation="llm_rerank_candidate",
            schema_cls=_RerankResponse,
            request_id=request_id,
            use_light_model=True,
        )
        match = str(result.get("match", "")).strip()
        if match.lower() == "none":
            match = ""
        confidence = result.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except Exception:
            confidence = None
        return {"match": (match or None), "confidence": confidence}

    @staticmethod
    def _extract_resume_evidence(raw_skill: str, resume_text: str, max_len: int = 220) -> str:
        """
        Возвращает короткий фрагмент резюме вокруг найденного raw_skill.
        Если точного вхождения нет — fallback на начало резюме.
        """
        text = (resume_text or "").strip()
        needle = (raw_skill or "").strip()
        if not text:
            return ""
        if not needle:
            return text[:max_len]
        lower_text = text.lower()
        lower_needle = needle.lower()
        idx = lower_text.find(lower_needle)
        if idx < 0:
            return text[:max_len]
        start = max(0, idx - max_len // 3)
        end = min(len(text), idx + len(needle) + (2 * max_len // 3))
        snippet = text[start:end].strip()
        return snippet[:max_len]

    def _classify_unknown_skill(self, raw_skill: str, resume_text: str, request_id: Optional[str] = None) -> Dict[str, Optional[float]]:
        """LLM-классификация неизвестного навыка: это действительно навык или шум."""
        prompt = (
            f"Фраза из резюме: {raw_skill}\n\n"
            "Определи, является ли это навыком.\n"
            "Верни JSON: {\"is_skill\": true/false, \"confidence\": число от 0 до 1}.\n"
            "Не относить к навыкам: должности, компании, города, университеты."
        )
        result = self._run_json_chat(
            messages=[
                {"role": "system", "content": "Отвечай строго валидным JSON без пояснений."},
                {"role": "user", "content": f"{prompt}\n\nКонтекст резюме:\n{resume_text[:1500]}"},
            ],
            temperature=0.0,
            max_tokens=250,
            operation="classify_unknown_skill",
            schema_cls=_UnknownSkillResponse,
            request_id=request_id,
            use_light_model=True,
        )
        is_skill = bool(result.get("is_skill"))
        confidence = result.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except Exception:
            confidence = None
        return {"is_skill": is_skill, "confidence": confidence}

    def _batch_assess_levels(
        self,
        skills_data: List[Dict[str, Any]],
        resume_text: str,
        allowed_skills: List[Dict],
        request_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Batch level assessment: evaluate multiple skills in one LLM call.
        Uses evidence snippets instead of full resume text for each skill."""
        if not skills_data:
            return []

        skill_blocks = []
        for item in skills_data[:_BATCH_LEVEL_LIMIT]:
            canonical = item["name"]
            raw = item.get("raw_name", canonical)
            levels = self._skill_level_texts(allowed_skills, canonical)
            evidence_snippet = self._extract_resume_evidence(raw, resume_text, max_len=300)
            block = {
                "skill": canonical,
                "basic": levels.get("basic", ""),
                "proficiency": levels.get("proficiency", ""),
                "advanced": levels.get("advanced", ""),
                "resume_context": evidence_snippet,
            }
            skill_blocks.append(block)

        prompt = (
            "Оцени уровень каждого навыка по шкале 0-3 на основе фрагмента резюме.\n"
            "0 = не упоминается, 1 = Basic, 2 = Proficiency, 3 = Advanced.\n\n"
            f"Навыки для оценки:\n{json.dumps(skill_blocks, ensure_ascii=False)}\n\n"
            "Верни JSON:\n"
            "{\"results\": [{\"skill\": \"название\", \"level\": число 0-3, \"evidence\": \"короткая цитата из резюме\"}]}"
        )
        result = self._run_json_chat(
            messages=[
                {"role": "system", "content": "Отвечай только валидным JSON. Уровень строго 0..3."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=2500,
            operation="batch_assess_levels",
            request_id=request_id,
            use_light_model=True,
        )
        raw_results = result.get("results", [])
        if not isinstance(raw_results, list):
            return [{"level": 1, "evidence": ""} for _ in skills_data]

        by_skill = {}
        for r in raw_results:
            if not isinstance(r, dict):
                continue
            skill = str(r.get("skill", "")).strip()
            level = r.get("level", 1)
            try:
                level = max(0, min(3, int(level)))
            except Exception:
                level = 1
            evidence = str(r.get("evidence", "")).strip()
            by_skill[skill.lower()] = {"level": level, "evidence": evidence}

        output = []
        for item in skills_data:
            canonical = item["name"]
            found = by_skill.get(canonical.lower(), {"level": 1, "evidence": ""})
            output.append(found)
        return output

    def _assess_level(
        self,
        canonical_skill: str,
        resume_text: str,
        skill_levels: Dict[str, str],
        request_id: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """Вызов 3: оценка уровня (0..3) с цитатой-доказательством. Single-skill fallback.
        Uses evidence snippet instead of full resume."""
        evidence_snippet = self._extract_resume_evidence(canonical_skill, resume_text, max_len=500)
        prompt = (
            f"Навык: {canonical_skill}\n\n"
            "Определи уровень по шкале:\n"
            f"- Basic: {skill_levels.get('basic', '')}\n"
            f"- Proficiency: {skill_levels.get('proficiency', '')}\n"
            f"- Advanced: {skill_levels.get('advanced', '')}\n\n"
            "Фрагмент резюме:\n"
            f"{evidence_snippet}\n\n"
            "Верни JSON: {\"level\": число 0..3, \"evidence\": \"короткая цитата из резюме\"}."
        )
        result = self._run_json_chat(
            messages=[
                {"role": "system", "content": "Отвечай только JSON. Уровень строго 0..3."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=400,
            operation="assess_level",
            schema_cls=_LevelResponse,
            request_id=request_id,
            use_light_model=True,
        )
        level = result.get("level")
        try:
            level = int(level)
        except Exception:
            level = 1
        level = max(0, min(3, level))
        evidence = str(result.get("evidence", "")).strip()
        return {"level": level, "evidence": evidence}

    @staticmethod
    def _skill_level_texts(allowed_skills: List[Dict], canonical_name: str) -> Dict[str, str]:
        for item in allowed_skills:
            name = (item.get("Навык") or item.get("name") or "").strip()
            if name != canonical_name:
                continue
            return {
                "basic": (
                    item.get("Skill level \\\\ Индикатор - Basic")
                    or item.get("Skill level \\ Индикатор - Basic")
                    or ""
                ),
                "proficiency": (
                    item.get("Skill level \\\\ Индикатор - Proficiency")
                    or item.get("Skill level \\ Индикатор - Proficiency")
                    or ""
                ),
                "advanced": (
                    item.get("Skill level \\\\ Индикатор - Advanced")
                    or item.get("Skill level \\ Индикатор - Advanced")
                    or ""
                ),
            }
        return {"basic": "", "proficiency": "", "advanced": ""}

    def parse_skills_v2(
        self,
        resume_text: str,
        allowed_skills: List[Dict],
        request_id: Optional[str] = None,
        retrieval_mode: Optional[str] = None,
    ) -> Dict:
        """Pipeline v2: extraction -> batch rerank -> classify unknown -> batch level assessment.
        Reduces LLM calls from O(N) per skill to O(1) batched calls."""
        raw_skills = self._extract_raw_skills(resume_text, request_id=request_id)
        if not raw_skills:
            return {"skills": [], "used_fallback": False}

        skills_with_candidates = []
        for raw_skill in raw_skills:
            candidates = get_skills_v2_candidates(raw_skill, top_k=5, retrieval_mode=retrieval_mode)
            skills_with_candidates.append({
                "raw_skill": raw_skill,
                "candidates": candidates,
            })

        has_candidates = [s for s in skills_with_candidates if s["candidates"]]
        no_candidates = [s for s in skills_with_candidates if not s["candidates"]]

        rerank_results = self._batch_rerank_candidates(has_candidates, request_id=request_id) if has_candidates else []

        matched_skills = []
        unmatched_skills = []

        for item, rerank in zip(has_candidates, rerank_results):
            raw_skill = item["raw_skill"]
            candidates = item["candidates"]
            matched_name = rerank.get("match")
            llm_conf = rerank.get("confidence")

            if not matched_name and candidates:
                top = candidates[0]
                if float(top.get("score", 0)) >= 0.75:
                    matched_name = top.get("name")

            if matched_name:
                matched_skills.append({
                    "raw_name": raw_skill,
                    "name": matched_name,
                    "llm_conf": llm_conf,
                    "candidates": candidates[:5],
                })
            else:
                unmatched_skills.append(raw_skill)

        for item in no_candidates:
            unmatched_skills.append(item["raw_skill"])

        result_skills = []

        for raw_skill in unmatched_skills:
            unknown = self._classify_unknown_skill(raw_skill, resume_text, request_id=request_id)
            if not unknown.get("is_skill"):
                continue
            evidence_quote = self._extract_resume_evidence(raw_skill, resume_text)
            result_skills.append({
                "raw_name": raw_skill,
                "name": raw_skill,
                "level": 1,
                "evidence": evidence_quote,
                "resume_evidence_span": evidence_quote,
                "llm_rerank_confidence": unknown.get("confidence"),
                "candidates": [],
                "is_unknown": True,
                "source_skill_id": None,
                "retrieval_mode": "llm_unknown",
                "retrieval_trace": {"candidates": []},
            })

        if matched_skills:
            level_results = self._batch_assess_levels(
                matched_skills, resume_text, allowed_skills, request_id=request_id
            )
            for item, level_info in zip(matched_skills, level_results):
                evidence_quote = (
                    (level_info.get("evidence") or "").strip()
                    or self._extract_resume_evidence(item["raw_name"], resume_text)
                )
                result_skills.append({
                    "raw_name": item["raw_name"],
                    "name": item["name"],
                    "level": level_info.get("level", 1),
                    "evidence": evidence_quote,
                    "resume_evidence_span": evidence_quote,
                    "llm_rerank_confidence": item["llm_conf"],
                    "candidates": item["candidates"],
                    "source_skill_id": item["name"],
                    "retrieval_mode": "hybrid_dense_lexical",
                    "retrieval_trace": {
                        "candidates": [
                            {
                                "name": c.get("name"),
                                "score": c.get("score"),
                                "dense_score": c.get("dense_score"),
                                "lexical_score": c.get("lexical_score"),
                            }
                            for c in item["candidates"][:5]
                        ]
                    },
                })

        dedup = {}
        for s in result_skills:
            key = s["name"]
            cur = dedup.get(key)
            if not cur or int(s.get("level", 0)) > int(cur.get("level", 0)):
                dedup[key] = s
        return {"skills": list(dedup.values()), "used_fallback": False}

    def parse_skills(
        self,
        resume_text,
        allowed_skills,
        request_id: Optional[str] = None,
        retrieval_mode: Optional[str] = None,
    ):
        """Совместимый интерфейс: сначала v2, при ошибке — legacy fallback."""
        if not self.client:
            raise ValueError(
                "OPENAI_API_KEY не задан. Добавьте ключ в .env для распознавания навыков из PDF."
            )

        try:
            return self.parse_skills_v2(
                resume_text,
                allowed_skills,
                request_id=request_id,
                retrieval_mode=retrieval_mode,
            )
        except Exception:
            legacy = self._legacy_parse_skills(
                resume_text,
                [s.get("Навык") or s.get("name") for s in allowed_skills],
            )
            return {"skills": legacy.get("skills", []), "used_fallback": True}
