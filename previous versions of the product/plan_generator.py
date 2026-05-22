
"""Генерация плана развития через LLM."""

import json
import time
from config import Config

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

MAX_TOKENS_RESPONSE = 4096


class PlanGenerator:
    def __init__(self):
        self._api_key = Config.OPENAI_API_KEY
        self.client = OpenAI(api_key=self._api_key) if (OpenAI and self._api_key) else None

    def generate_plan_702010(self, scenario_type, step1_markdown, target_name,
                              context="", rag_context="", skill_context="",
                              strong_skills=None, gap_summary=None):
        if not self.client:
            return self._fallback_plan(target_name)

        # Structured gap data for the model (JSON is parsed better than markdown)
        structured_block = ""
        if gap_summary:
            structured_block = "\n\nСтруктурированные данные анализа (JSON):\n```json\n"
            structured_block += json.dumps(gap_summary, ensure_ascii=False, indent=2)[:3000]
            structured_block += "\n```"

        strong_block = ""
        if strong_skills:
            strong_block = "\n\nНавыки, которые пользователь УЖЕ ОСВОИЛ (НЕ включать в план развития): "
            strong_block += ", ".join(strong_skills[:20])

        extra_rag = ""
        if rag_context and rag_context.strip():
            extra_rag = "\n\nМатериалы из базы навыков (используй для конкретики):\n" + rag_context.strip()[:2000]

        extra_skills = ""
        if skill_context and skill_context.strip():
            extra_skills = "\n\nОписания навыков и задачи на развитие (основа рекомендаций):\n" + skill_context.strip()[:3000]

        prompt = f"""Цель: {target_name}
Сценарий: {scenario_type}
{structured_block}
{strong_block}
{extra_rag}
{extra_skills}

Дополнительно: {context}

ЗАДАЧА: составь персональный план развития строго по данным выше.

СТРУКТУРА ОТВЕТА:

## Приоритизация
Из всех разрывов выбери 5-7 самых критичных навыков/параметров и кратко объясни почему именно они.

## Развитие через реальные задачи
Для каждого приоритетного навыка/параметра — 2-3 конкретных действия с ожидаемым результатом. Опирайся на примеры задач из контекста.

## Взаимодействие и обратная связь
Конкретные форматы: менторство, code review, 1-on-1, ретроспективы, калибровки. Привяжи к навыкам.

## Курсы и тренинги
Конкретные направления обучения для каждого приоритетного навыка.

## Метрики и чекпоинты
Как измерить прогресс. Точки пересмотра: 4 / 8 / 12 недель.

ПРАВИЛА:
- Отвечай на русском языке
- Не повторяй диагностику, сразу план
- Не предлагай изучать навыки из списка «уже освоил»
- Не обрывай текст, не используй «…»
- Опирайся ТОЛЬКО на данные из контекста"""

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Ты эксперт по карьерному развитию в IT. Отвечай структурированно, на русском. Никогда не обрывай текст. Не выдумывай навыки — используй только то, что есть в контексте."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=MAX_TOKENS_RESPONSE,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1 + attempt)
        return self._fallback_plan(target_name) + f"\n\n*(Ошибка генерации: {last_error})*"

    def _fallback_plan(self, target_name):
        return f"""## План развития: {target_name}

Для персонального плана с генерацией через ИИ укажите OPENAI_API_KEY в .env.

**Развитие через реальные задачи:** Возьмите задачи из блока «Зона роста» и выполняйте в работе с фиксацией результата.
**Взаимодействие и обратная связь:** Обсудите приоритеты с руководителем, запросите обратную связь раз в 2–4 недели.
**Курсы и тренинги:** Изучите материалы по недостающим навыкам из рекомендаций выше.

**Чекпоинты:** пересмотр прогресса через 4, 8 и 12 недель."""
