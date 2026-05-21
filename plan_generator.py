
"""Генерация плана развития через LLM."""

import json
import time
from pydantic import BaseModel, Field, ValidationError
from typing import Any, Dict, List, Optional, Tuple
from config import Config
from llm_observability import LLMCallMetrics, log_llm_call

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

MAX_TOKENS_RESPONSE = 6144
PLAN_PATCH_MAX_TOKENS = 4096
FOCUSED_PLAN_MAX_TOKENS = 3000

REQUIRED_PLAN_SECTIONS = [
    "Приоритизация",
    "Развитие",
    "Взаимодействие",
    "Книги",
    "Метрики",
]


def _missing_plan_sections(content: str) -> List[str]:
    low = (content or "").lower()
    return [s for s in REQUIRED_PLAN_SECTIONS if s.lower() not in low]


class _FocusedTaskItem(BaseModel):
    skill: str = ""
    items: List[str] = Field(default_factory=list)


class _FocusedPlanResponse(BaseModel):
    tasks: List[_FocusedTaskItem] = Field(default_factory=list)
    communication: List[str] = Field(default_factory=list)
    learning: List[str] = Field(default_factory=list)


class PlanGenerator:
    def __init__(self):
        self._api_key = Config.OPENAI_API_KEY
        self.client = OpenAI(api_key=self._api_key) if (OpenAI and self._api_key) else None

    @staticmethod
    def _system_policy() -> str:
        return (
            "Ты — карьерный коуч с 10-летним опытом в IT.\n"
            "Ты работаешь со специалистами разных уровней и строишь практичные планы развития.\n\n"
            "Критические правила:\n"
            "1) Используй ТОЛЬКО информацию из переданного контекста.\n"
            "2) Если данных недостаточно, явно пиши: 'Требуется уточнение'.\n"
            "3) Все практические задачи должны быть выполнимы за 1–4 часа.\n"
            "4) В блоке обучения рекомендуй только книги (автор + название + конкретные главы). "
            "Не рекомендуй курсы, тренинги, буткемпы и подписки.\n"
            "5) Не выдумывай навыки, роли, факты или достижения пользователя.\n"
            "6) Отвечай на русском языке.\n\n"
            "Принцип 70/20/10:\n"
            "- tasks (70%): конкретные практические задачи с глагол + объект + контекст + измеримый результат\n"
            "- communication (20%): менторство, нетворкинг, peer review, 1-on-1\n"
            "- learning (10%): конкретные книги с авторами и главами\n\n"
            "ЗАПРЕЩЕНО в tasks: абстрактные советы типа 'изучите X', 'практикуйтесь', 'читайте про Y'.\n"
            "ОБЯЗАТЕЛЬНО: каждая задача — отдельное действие с измеримым результатом."
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        return " ".join((text or "").split()).strip()

    @staticmethod
    def _cut_text(text: str, limit: int) -> str:
        text = (text or "").strip()
        if limit <= 0 or not text:
            return ""
        if len(text) <= limit:
            return text
        cut = text[:limit].rstrip()
        last_space = cut.rfind(" ")
        if last_space > int(limit * 0.7):
            cut = cut[:last_space]
        return cut.rstrip()

    def _build_context_block(
        self,
        *,
        step1_markdown: str = "",
        context: str = "",
        rag_context: str = "",
        skill_context: str = "",
        strong_skills: Optional[List[str]] = None,
        gap_summary: Optional[Dict[str, Any]] = None,
        max_chars: Optional[int] = None,
    ) -> str:
        """
        Собирает контекст с приоритетным усечением до заданного лимита.
        Приоритет секций:
        1) Структурированные gap-данные
        2) Описания навыков/уровней
        3) Уже сильные навыки пользователя
        4) RAG-контекст
        5) Диагностика в markdown
        6) Доп. инструкции
        """
        max_len = int(max_chars or Config.PLAN_CONTEXT_MAX_CHARS or 4000)
        sections: List[Tuple[str, str]] = []
        if gap_summary:
            sections.append(
                (
                    "СТРУКТУРИРОВАННЫЙ_GAP_JSON",
                    json.dumps(gap_summary, ensure_ascii=False, indent=2),
                )
            )
        if skill_context and skill_context.strip():
            sections.append(("ОПИСАНИЯ_НАВЫКОВ", skill_context.strip()))
        if strong_skills:
            sections.append(
                (
                    "УЖЕ_СИЛЬНЫЕ_НАВЫКИ",
                    ", ".join([s for s in strong_skills if str(s).strip()][:25]),
                )
            )
        if rag_context and rag_context.strip():
            sections.append(("RAG_КОНТЕКСТ", rag_context.strip()))
        if step1_markdown and step1_markdown.strip():
            sections.append(("ДИАГНОСТИКА_MARKDOWN", step1_markdown.strip()))
        if context and context.strip():
            sections.append(("ДОП_КОНТЕКСТ", context.strip()))

        if not sections:
            return ""

        out_parts: List[str] = []
        remaining = max_len
        for title, raw_text in sections:
            prefix = "" if not out_parts else "\n\n"
            header = f"[{title}]\n"
            body_limit = remaining - len(prefix) - len(header)
            if body_limit <= 0:
                break
            body = self._cut_text(raw_text, body_limit)
            if not body:
                continue
            block = f"{prefix}{header}{body}"
            out_parts.append(block)
            remaining -= len(block)
            if remaining <= 0:
                break

        return "".join(out_parts).strip()

    @staticmethod
    def _normalize_focused_json(result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = _FocusedPlanResponse(**(result or {})).model_dump()
        except ValidationError:
            result = _FocusedPlanResponse().model_dump()
        tasks = result.get("tasks") if isinstance(result.get("tasks"), list) else []
        normalized_tasks = []
        for item in tasks:
            if not isinstance(item, dict):
                continue
            skill = str(item.get("skill") or "").strip()
            if not skill:
                continue
            raw_items = item.get("items") if isinstance(item.get("items"), list) else []
            task_items = [str(x).strip() for x in raw_items if str(x).strip()]
            if not task_items:
                task_items = ["Требуется уточнение"]
            normalized_tasks.append({"skill": skill, "items": task_items[:4]})

        communication = result.get("communication")
        if not isinstance(communication, list):
            communication = []
        communication = [str(x).strip() for x in communication if str(x).strip()][:6]
        if not communication:
            communication = ["Требуется уточнение"]

        learning = result.get("learning")
        if not isinstance(learning, list):
            learning = []
        learning = [str(x).strip() for x in learning if str(x).strip()][:6]
        if not learning:
            learning = ["Требуется уточнение"]

        return {
            "tasks": normalized_tasks,
            "communication": communication,
            "learning": learning,
        }

    def generate_plan_702010(
        self,
        scenario_type,
        step1_markdown,
        target_name,
        context="",
        rag_context="",
        skill_context="",
        strong_skills=None,
        gap_summary=None,
    ):
        if not self.client:
            return self._fallback_plan(target_name)

        context_block = self._build_context_block(
            step1_markdown=step1_markdown,
            context=context,
            rag_context=rag_context,
            skill_context=skill_context,
            strong_skills=strong_skills or [],
            gap_summary=gap_summary or {},
            max_chars=Config.PLAN_CONTEXT_MAX_CHARS,
        )

        prompt = f"""Цель: {target_name}
Сценарий: {scenario_type}

КОНТЕКСТ (ограниченный бюджет, до {Config.PLAN_CONTEXT_MAX_CHARS} символов):
{context_block or "Требуется уточнение"}

ЗАДАЧА: составь персональный план развития строго по данным из КОНТЕКСТА.

СТРУКТУРА ОТВЕТА:

## Приоритизация
Из всех разрывов выбери 5-7 самых критичных навыков/параметров и кратко объясни почему именно они.

## Развитие параметров роли
Для каждого приоритетного параметра роли (если есть в контексте) — конкретные действия с ожидаемым результатом.

## Развитие по навыкам
Для каждого приоритетного навыка — 2-3 конкретных действия с ожидаемым результатом. Опирайся на примеры задач из контекста.

## Взаимодействие и обратная связь
Конкретные форматы: менторство, code review, 1-on-1, ретроспективы, калибровки. Привяжи к навыкам.

## Книги
Для каждого приоритетного навыка предложи только книги.
Не предлагай курсы, тренинги, буткемпы и подписки.

## Метрики и чекпоинты
Как измерить прогресс. Точки пересмотра: 4 / 8 / 12 недель.

ПРАВИЛА:
- Отвечай на русском языке
- Не повторяй диагностику, сразу план
- Не предлагай изучать навыки из списка «уже освоил»
- Не обрывай текст, не используй «…»
- Опирайся ТОЛЬКО на данные из контекста
- Если данных недостаточно, пиши «Требуется уточнение»"""

        last_error = None
        prompt_chars = len(prompt)
        start_ms = int(time.time() * 1000)
        system_msg = {"role": "system", "content": self._system_policy()}
        user_msg = {"role": "user", "content": prompt}
        messages: List[Dict[str, str]] = [system_msg, user_msg]
        content = ""

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=Config.PLAN_GENERATOR_MODEL,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=MAX_TOKENS_RESPONSE,
                )
                content = response.choices[0].message.content.strip()
                break
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(0.35 * (attempt + 1))

        if not content.strip():
            if Config.LLM_OBSERVABILITY_ENABLED:
                log_llm_call(
                    LLMCallMetrics(
                        component="plan_generator",
                        operation="generate_plan_702010",
                        model=Config.PLAN_GENERATOR_MODEL,
                        request_id=None,
                        success=False,
                        latency_ms=int(time.time() * 1000) - start_ms,
                        prompt_chars=prompt_chars,
                        completion_chars=0,
                        error=str(last_error),
                    )
                )
            return self._fallback_plan(target_name) + f"\n\n*(Ошибка генерации: {last_error})*"

        # Неполный ответ: дорого заново слать весь контекст — дополняем коротким follow-up в том же чате.
        for _patch_round in range(2):
            missing_sections = _missing_plan_sections(content)
            if not missing_sections:
                break
            messages.append({"role": "assistant", "content": content})
            patch_prompt = (
                "В предыдущем ответе не хватает обязательных разделов (по ключевым словам в заголовках ##): "
                + ", ".join(missing_sections)
                + ".\n\nДобавь в КОНЕЦ документа только недостающие разделы: каждый с заголовком ## на русском "
                "в стиле исходного задания (## Приоритизация, блоки развития, ## Взаимодействие и обратная связь, "
                "## Книги, ## Метрики и чекпоинты — по необходимости). Не дублируй уже полностью написанные разделы."
            )
            messages.append({"role": "user", "content": patch_prompt})
            try:
                patch_resp = self.client.chat.completions.create(
                    model=Config.PLAN_GENERATOR_MODEL,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=PLAN_PATCH_MAX_TOKENS,
                )
                delta = (patch_resp.choices[0].message.content or "").strip()
                if delta:
                    content = f"{content.rstrip()}\n\n{delta}"
            except Exception as patch_err:
                last_error = patch_err
                break

        if Config.LLM_OBSERVABILITY_ENABLED:
            log_llm_call(
                LLMCallMetrics(
                    component="plan_generator",
                    operation="generate_plan_702010",
                    model=Config.PLAN_GENERATOR_MODEL,
                    request_id=None,
                    success=True,
                    latency_ms=int(time.time() * 1000) - start_ms,
                    prompt_chars=prompt_chars,
                    completion_chars=len(content),
                )
            )
        return content

    def generate_focused_plan_json(
        self,
        *,
        selected_skills: List[str],
        profession: str,
        grade: str,
        scenario: str,
        target_name: str,
        skill_context: str,
    ) -> Dict[str, Any]:
        if not self.client:
            return {
                "tasks": [{"skill": s, "items": ["Требуется уточнение"]} for s in selected_skills[:10]],
                "communication": ["Требуется уточнение"],
                "learning": ["Требуется уточнение"],
            }

        context_block = self._build_context_block(
            context=(
                f"Профессия: {profession}. "
                f"Грейд: {grade}. "
                f"Сценарий: {scenario}. "
                f"Цель: {target_name}. "
                f"Выбранные навыки: {', '.join(selected_skills[:10])}."
            ),
            skill_context=skill_context,
            strong_skills=[],
            gap_summary={"selected_skills": selected_skills[:10]},
            max_chars=Config.PLAN_CONTEXT_MAX_CHARS,
        )

        prompt = f"""Сгенерируй фокусный план развития в JSON-формате.

Профессия: {profession}
Грейд: {grade}
Сценарий: {scenario}
Цель: {target_name}
Выбранные навыки: {', '.join(selected_skills[:10])}

КОНТЕКСТ (описания навыков и примеры задач из таксономии):
{context_block or "Требуется уточнение"}

Верни ТОЛЬКО валидный JSON:
{{
  "tasks": [
    {{"skill": "название навыка", "items": ["конкретная задача 1", "конкретная задача 2"]}}
  ],
  "communication": ["рекомендация 1", "рекомендация 2"],
  "learning": ["'Название книги' — Автор, главы X-Y"]
}}

Правила:
- tasks: для каждого выбранного навыка 2-3 практических задачи
- каждая задача = глагол + объект + контекст + измеримый результат
- ЗАПРЕЩЕНО: абстрактные "изучите X", "практикуйтесь в Y"
- ОБЯЗАТЕЛЬНО: опирайся на примеры задач из контекста таксономии
- каждая задача должна быть выполнима за 1-4 часа
- communication: конкретные форматы (1:1, code review, митапы) привязанные к навыкам
- learning: только книги с автором и конкретными главами (без курсов/платформ)
- если не хватает данных, используй «Требуется уточнение»
- никаких пояснений вне JSON"""

        last_error = None
        prompt_chars = len(prompt)
        start_ms = int(time.time() * 1000)
        max_out = FOCUSED_PLAN_MAX_TOKENS
        if scenario == "Исследование возможностей" and len(selected_skills) > 4:
            # Больше навыков — длиннее JSON; ограничиваем верх, чтобы не раздувать стоимость бесконечно.
            max_out = min(6000, FOCUSED_PLAN_MAX_TOKENS + 220 * (len(selected_skills) - 4))
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=Config.PLAN_GENERATOR_MODEL,
                    messages=[
                        {"role": "system", "content": self._system_policy() + "\nОтвечай строго JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=max_out,
                    response_format={"type": "json_object"},
                )
                parsed = json.loads(response.choices[0].message.content)
                normalized = self._normalize_focused_json(parsed if isinstance(parsed, dict) else {})
                if Config.LLM_OBSERVABILITY_ENABLED:
                    completion_text = json.dumps(normalized, ensure_ascii=False)
                    log_llm_call(
                        LLMCallMetrics(
                            component="plan_generator",
                            operation="generate_focused_plan_json",
                            model=Config.PLAN_GENERATOR_MODEL,
                            request_id=None,
                            success=True,
                            latency_ms=int(time.time() * 1000) - start_ms,
                            prompt_chars=prompt_chars,
                            completion_chars=len(completion_text),
                        )
                    )
                return normalized
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1 + attempt)

        if Config.LLM_OBSERVABILITY_ENABLED:
            log_llm_call(
                LLMCallMetrics(
                    component="plan_generator",
                    operation="generate_focused_plan_json",
                    model=Config.PLAN_GENERATOR_MODEL,
                    request_id=None,
                    success=False,
                    latency_ms=int(time.time() * 1000) - start_ms,
                    prompt_chars=prompt_chars,
                    completion_chars=0,
                    error=str(last_error),
                )
            )
        return {
            "tasks": [{"skill": s, "items": ["Требуется уточнение"]} for s in selected_skills[:10]],
            "communication": [f"Требуется уточнение ({last_error})" if last_error else "Требуется уточнение"],
            "learning": ["Требуется уточнение"],
        }

    def _fallback_plan(self, target_name):
        return f"""## План развития: {target_name}

Для персонального плана с генерацией через ИИ укажите OPENAI_API_KEY в .env.

**Развитие через реальные задачи:** Возьмите задачи из блока «Зона роста» и выполняйте в работе с фиксацией результата.
**Взаимодействие и обратная связь:** Обсудите приоритеты с руководителем, запросите обратную связь раз в 2–4 недели.
**Книги:** Подберите 2–3 профильные книги по недостающим навыкам из рекомендаций выше.

**Чекпоинты:** пересмотр прогресса через 4, 8 и 12 недель."""
