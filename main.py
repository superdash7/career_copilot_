"""Основной файл для запуска"""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
if os.getcwd() != str(PROJECT_DIR):
    os.chdir(PROJECT_DIR)
    sys.path.insert(0, str(PROJECT_DIR))

import gradio as gr
import pandas as pd
from data_loader import DataLoader
from config import Config
from resume_parser import ResumeParser
from gap_analyzer import GapAnalyzer
from scenario_handler import ScenarioHandler
from output_formatter import OutputFormatter

# Инициализация модулей
data = DataLoader()
parser = ResumeParser()
analyzer = GapAnalyzer()
scenarios = ScenarioHandler(data)
formatter = OutputFormatter(data)

# Маппинг грейдов
GRADE_MAP = {
    "Младший (Junior)": "Junior",
    "Специалист (Middle)": "Middle",
    "Старший (Senior)": "Senior",
    "Ведущий (Lead)": "Lead",
    "Эксперт (Expert)": "Expert"
}

# Шкала оценки навыков
SKILL_LEVELS = {
    0: "Нет навыка",
    0.5: "Начальный | Есть знания, нет навыка",
    1: "Базовый | Применяет в типовых ситуациях",
    1.5: "Продвинутый | Применяет в нестандартных ситуациях",
    2: "Эксперт | Может обучать"
}

def get_professions_list():
    """Получаем список профессий из JSON"""
    try:
        return data.get_all_roles()
    except Exception as e:
        print(f"❌ Ошибка загрузки профессий: {e}")
        return ["Product Manager", "Data Analyst"]  # Fallback

def analyze_resume(pdf_file, profession):
    """Парсинг резюме через AI"""
    if pdf_file is None:
        return []

    if parser.client is None:
        return [["⚠️ Для распознавания навыков из PDF укажите OPENAI_API_KEY в .env", 0]]

    try:
        text = parser.extract_text(pdf_file)
        if not text or not text.strip():
            return [["⚠️ Не удалось извлечь текст из PDF. Проверьте файл.", 0]]
        skills_dicts = data.skills
        result = parser.parse_skills(text, skills_dicts)

        # Преобразуем уровни 0-3 в шкалу 0-2
        level_mapping = {0: 0, 1: 1, 2: 1.5, 3: 2}

        table_data = []
        for s in result.get('skills', []):
            mapped_level = level_mapping.get(s['level'], 1)
            table_data.append([s['name'], mapped_level])

        return table_data

    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        msg = str(e).strip() or "Ошибка API"
        return [[f"⚠️ Не удалось распознать резюме. Проверьте PDF и подключение. ({msg[:80]})", 0]]

def add_skill_from_skillset(current_table, skill_name, skill_level):
    """Добавить навык из скиллсета выбранной профессии."""
    if not skill_name or not str(skill_name).strip() or skill_level is None:
        return current_table
    skill_name = str(skill_name).strip()
    if skill_name not in data.skills_map:
        return current_table

    import pandas as pd
    if current_table is None:
        current_table = []
    elif isinstance(current_table, pd.DataFrame):
        current_table = current_table.values.tolist()
    existing = [row for row in current_table if row[0] == skill_name]
    if existing:
        return current_table
    current_table.append([skill_name, skill_level])
    return current_table


def add_custom_skill(current_table, skill_name, skill_level):
    """Добавить произвольный навык (свой). Сначала синонимы/стемминг, затем семантический маппинг на канонический навык."""
    if not skill_name or not str(skill_name).strip() or skill_level is None:
        return current_table
    skill_name = str(skill_name).strip()
    canonical_set = set(data.skills_map.keys())
    try:
        from skill_normalizer import resolve_to_canonical
        canonical = resolve_to_canonical(skill_name, canonical_set)
        if canonical:
            skill_name = canonical
    except Exception:
        pass
    if skill_name not in (canonical_set or set()):
        try:
            from rag_service import map_to_canonical_skill_v2
            result = map_to_canonical_skill_v2(skill_name)
            if result.get("canonical_name"):
                skill_name = result["canonical_name"]
        except Exception:
            try:
                from rag_service import map_to_canonical_skill
                canonical = map_to_canonical_skill(skill_name)
                if canonical:
                    skill_name = canonical
            except Exception:
                pass

    import pandas as pd
    if current_table is None:
        current_table = []
    elif isinstance(current_table, pd.DataFrame):
        current_table = current_table.values.tolist()
    existing = [row for row in current_table if row[0] == skill_name]
    if existing:
        return current_table
    current_table.append([skill_name, skill_level])
    return current_table


def get_skill_suggestions_markdown(user_input):
    """Подсказки «возможно, вы имели в виду» для поля «Свой навык». Сначала синонимы, затем RAG."""
    if not user_input or len(str(user_input).strip()) < 2:
        return ""
    raw = str(user_input).strip()
    suggestions = []
    try:
        from skill_normalizer import resolve_to_canonical, get_canonical_skills_set
        canonical_set = get_canonical_skills_set()
        by_synonym = resolve_to_canonical(raw, canonical_set)
        if by_synonym:
            suggestions.append(by_synonym)
    except Exception:
        pass
    try:
        from rag_service import suggest_skills
        from_rag = suggest_skills(raw)
        for s in from_rag:
            if s and s not in suggestions:
                suggestions.append(s)
    except Exception:
        pass
    if not suggestions:
        return ""
    return "**Возможно, вы имели в виду:** " + ", ".join(suggestions[:8])


def dedupe_opportunities_by_profession(opportunities):
    """Одна запись на профессию: группируем по internal_role, оставляем лучшую по semantic_score и match, убираем грейд из названия."""
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


def build_role_matches(opps, user_skills, data_loader):
    """Строит список RoleMatch из opps для build_explore_recommendations."""
    from concurrent.futures import ThreadPoolExecutor
    from explore_recommendations import RoleMatch
    try:
        from rag_service import get_rag_why_role_bullets
    except Exception:
        get_rag_why_role_bullets = lambda u, r, **kw: []

    def _one(opp):
        role_title = opp.get("role", "")
        internal = opp.get("internal_role")
        reqs = data_loader.get_role_requirements(internal, "Middle") if internal else {}
        skill_keys = [k for k in reqs.keys() if k not in data_loader.atlas_map]
        matched = [{"name": s} for s in user_skills if s in reqs][:5]
        missing = [{"name": s} for s in skill_keys if s not in user_skills][:3]
        why = get_rag_why_role_bullets(
            user_skills, role_title, top_k=5, atlas_keys=set(data_loader.atlas_map.keys())
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
    max_workers = min(2, max(1, len(opps)))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(_one, opps))


def build_plan(skills_table, profession, current_grade, scenario, target_profession):
    """Построение плана развития"""
    # Сразу приводим к list — иначе "if not skills_table" падает на pandas DataFrame
    import pandas as pd
    if isinstance(skills_table, pd.DataFrame):
        skills_table = skills_table.values.tolist()
    if not skills_table or len(skills_table) == 0:
        return "⚠️ **Добавьте хотя бы один навык** — загрузите резюме (PDF) или выберите из скиллсета / введите свой.", []

    if not profession:
        return "⚠️ **Выберите текущую профессию** в шаге 1.", []

    if not current_grade:
        return "⚠️ **Выберите текущий грейд** в шаге 1.", []

    if scenario == "Смена профессии" and not target_profession:
        return "⚠️ **Выберите целевую профессию** для смены (появляется при выборе сценария «Смена профессии»).", []

    try:
        # Преобразуем таблицу в словарь (устойчиво к заголовкам, NaN, разным типам)
        user_skills = {}
        for row in skills_table:
            if not row or len(row) < 2:
                continue
            name = row[0]
            # Пропускаем строку заголовка и служебные сообщения об ошибках
            if name is None or str(name).strip() == "" or str(name) == "Навык" or str(name).startswith("⚠️"):
                continue
            try:
                level = float(row[1])
            except (TypeError, ValueError):
                continue
            if level != level:  # NaN
                continue
            if level < 1:
                internal_level = 0
            elif level == 1:
                internal_level = 1
            elif level == 1.5:
                internal_level = 2
            else:
                internal_level = 3
            user_skills[str(name).strip()] = internal_level

        if not user_skills:
            return "⚠️ В таблице нет корректных навыков. Добавьте навыки и укажите уровень (0–2).", []

        grade_key = GRADE_MAP.get(current_grade, "Middle")

        atlas_param_names = list(data.atlas_map.keys())

        if scenario == "Следующий грейд":
            grade_sequence = ["Junior", "Middle", "Senior", "Lead", "Expert"]
            current_index = grade_sequence.index(grade_key) if grade_key in grade_sequence else 1
            next_index = min(current_index + 1, len(grade_sequence) - 1)
            target_grade = grade_sequence[next_index]

            profession_internal = data.get_internal_role_name(profession)
            reqs, role_name = scenarios.next_grade(profession_internal, grade_key, user_skills)
            structured = analyzer.analyze_structured(
                user_skills, reqs, atlas_param_names, data.atlas_map
            )
            return formatter.format_next_grade(
                structured, role_name, profession,
                current_grade=grade_key, target_grade=target_grade, profession_internal=profession_internal,
            ), []

        elif scenario == "Смена профессии":
            target_internal = data.get_internal_role_name(target_profession)
            try:
                from switch_profession_service import build_switch_comparison
                switch_vm = build_switch_comparison(user_skills, target_internal, "Middle", data)
                role_name = f"{target_profession} ({switch_vm.baseline_level} → Middle)"
                return formatter.format_change_profession(switch_vm, role_name, target_profession), []
            except Exception:
                reqs, role_name = scenarios.change_profession(target_internal, user_skills)
                structured = analyzer.analyze_structured(
                    user_skills, reqs, atlas_param_names, data.atlas_map
                )
                return formatter.format_change_profession_legacy(
                    structured, role_name, target_profession
                ), []

        else:
            opps = scenarios.explore_opportunities(user_skills)
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
            opps = dedupe_opportunities_by_profession(opps)
            matches = build_role_matches(opps, user_skills, data)
            from explore_recommendations import build_explore_recommendations
            view_model = build_explore_recommendations(matches)
            role_titles = [c.title for c in view_model.closest + view_model.adjacent + view_model.far]
            return formatter.format_explore(view_model, user_skills), role_titles

    except Exception as e:
        print(f"❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ **Произошла ошибка.** Проверьте ввод и повторите. Если повторяется — убедитесь, что данные в папке `data/` на месте и при использовании RAG заданы QDRANT_URL и QDRANT_API_KEY.\n\n*(Технически: {str(e)[:150]})*", []

# Стили интерфейса
CUSTOM_CSS = """
.block { padding: 1rem 1.25rem !important; }
.gr-markdown h1 { font-size: 1.75rem !important; margin-bottom: 0.5rem !important; font-weight: 700 !important; }
.gr-markdown h2 { font-size: 1.15rem !important; color: #374151 !important; font-weight: 600 !important; }
.gr-button-primary { font-weight: 600 !important; border-radius: 8px !important; }
.accordion { border-radius: 12px !important; }
footer .gr-markdown { color: #6b7280 !important; font-size: 0.875rem !important; }
"""

with gr.Blocks(
    title="AI Career Pathfinder",
    theme=gr.themes.Soft(primary_hue="slate", secondary_hue="blue"),
    css=CUSTOM_CSS,
) as demo:
    gr.Markdown("# 🚀 AI Career Pathfinder")
    gr.Markdown("Персональный план карьерного развития на основе AI")

    with gr.Accordion("📋 Шаг 1: Основная информация", open=True):
        with gr.Row():
            profession_input = gr.Dropdown(
                choices=get_professions_list(),
                label="Текущая профессия",
                info="Выберите из списка",
            )
            grade_input = gr.Dropdown(
                choices=list(GRADE_MAP.keys()),
                label="Текущий грейд",
                value="Специалист (Middle)",
            )

    with gr.Accordion("📄 Шаг 2: Добавьте навыки", open=True):
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Tab("Загрузить резюме"):
                    file_input = gr.File(label="PDF файл", file_types=[".pdf"])
                    btn_analyze = gr.Button("🔍 Распознать навыки", variant="primary")
                with gr.Tab("Добавить вручную"):
                    gr.Markdown("**Из скиллсета профессии** (список зависит от выбора в шаге 1)")
                    skill_from_skillset = gr.Dropdown(
                        choices=[],
                        label="Навык из скиллсета",
                        allow_custom_value=False,
                        value=None,
                    )
                    level_skillset = gr.Dropdown(
                        choices=[(f"{k} — {v}", k) for k, v in SKILL_LEVELS.items()],
                        label="Уровень владения",
                        value=1,
                    )
                    btn_add_skillset = gr.Button("➕ Добавить из скиллсета")
                    gr.Markdown("**Свой навык**")
                    custom_skill_input = gr.Textbox(
                        label="Название навыка",
                        placeholder="Введите любой навык вручную",
                    )
                    skill_suggestions_md = gr.Markdown()
                    level_custom = gr.Dropdown(
                        choices=[(f"{k} — {v}", k) for k, v in SKILL_LEVELS.items()],
                        label="Уровень владения",
                        value=1,
                    )
                    btn_add_custom = gr.Button("➕ Добавить свой навык")
            with gr.Column(scale=2):
                gr.Markdown("**Ваши навыки** (можно редактировать)")
                skills_table = gr.Dataframe(
                    headers=["Навык", "Уровень (0-2)"],
                    datatype=["str", "number"],
                    col_count=(2, "fixed"),
                    interactive=True,
                    label="Текущие навыки",
                )

    with gr.Accordion("🎯 Шаг 3: Выберите цель", open=True):
        with gr.Row():
            scenario_choice = gr.Radio(
                ["Следующий грейд", "Смена профессии", "Исследование возможностей"],
                label="Что вы хотите сделать?",
                value="Следующий грейд",
            )
            target_profession_input = gr.Dropdown(
                choices=get_professions_list(),
                label="Целевая профессия (для смены)",
                visible=False,
            )
        btn_plan = gr.Button("📊 Построить план развития", variant="primary", size="lg")

    gr.Markdown("---")
    result_output = gr.Markdown(label="Результат")
    download_btn = gr.DownloadButton(label="📥 Скачать отчёт (Markdown)", visible=True)
    with gr.Row(visible=False) as explore_plan_row:
        explore_role_dropdown = gr.Dropdown(
            choices=[],
            label="Роль для пробного плана",
            value=None,
        )
        btn_explore_plan = gr.Button("Сгенерировать пробный план 70/20/10", variant="secondary")
    gr.Markdown("*AI Career Pathfinder — персональный план карьерного развития на основе ваших навыков*")

    def update_skills_choices(profession_display):
        if not profession_display:
            return gr.update(choices=[], value=None)
        choices = data.get_skills_for_role(profession_display)
        return gr.update(choices=choices, value=choices[0] if choices else None)

    profession_input.change(
        fn=update_skills_choices,
        inputs=[profession_input],
        outputs=[skill_from_skillset],
    )

    btn_analyze.click(
        fn=analyze_resume,
        inputs=[file_input, profession_input],
        outputs=[skills_table],
        show_progress=True,
    )
    btn_add_skillset.click(
        fn=add_skill_from_skillset,
        inputs=[skills_table, skill_from_skillset, level_skillset],
        outputs=[skills_table],
    )
    custom_skill_input.change(
        fn=get_skill_suggestions_markdown,
        inputs=[custom_skill_input],
        outputs=[skill_suggestions_md],
    )
    btn_add_custom.click(
        fn=add_custom_skill,
        inputs=[skills_table, custom_skill_input, level_custom],
        outputs=[skills_table],
    )

    def build_plan_with_outputs(skills_table, profession, grade, scenario, target_profession):
        md, role_titles = build_plan(skills_table, profession, grade, scenario, target_profession)
        return md, gr.update(choices=role_titles or [], value=(role_titles[0] if role_titles else None))

    def make_plan_download(markdown_text):
        """Формирует файл для скачивания из текущего результата."""
        import tempfile
        text = (markdown_text or "").strip() or "*Отчёт пуст. Постройте план выше.*"
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        f.write(text)
        f.close()
        return f.name

    scenario_choice.change(
        fn=lambda x: (gr.update(visible=(x == "Смена профессии")), gr.update(visible=(x == "Исследование возможностей"))),
        inputs=[scenario_choice],
        outputs=[target_profession_input, explore_plan_row],
    )

    btn_plan.click(
        fn=build_plan_with_outputs,
        inputs=[skills_table, profession_input, grade_input, scenario_choice, target_profession_input],
        outputs=[result_output, explore_role_dropdown],
        show_progress=True,
    )

    def generate_explore_plan(skills_table, profession, grade, selected_role):
        if not selected_role:
            return "⚠️ Выберите роль из списка выше."
        return build_plan(skills_table, profession, grade, "Смена профессии", selected_role)[0]

    btn_explore_plan.click(
        fn=generate_explore_plan,
        inputs=[skills_table, profession_input, grade_input, explore_role_dropdown],
        outputs=[result_output],
        show_progress=True,
    )

    download_btn.click(
        fn=make_plan_download,
        inputs=[result_output],
        outputs=[download_btn],
    )

def _launch():
    port = 7860
    for _ in range(3):
        try:
            print("🚀 Запуск AI Career Pathfinder...")
            print(f"   Откройте в браузере: http://127.0.0.1:{port}")
            demo.launch(
                server_name="127.0.0.1",
                server_port=port,
                share=True,
                inbrowser=True,
            )
            return
        except OSError as e:
            if "address already in use" in str(e).lower() or "48" in str(e):
                port += 1
                print(f"   Порт занят, пробуем {port}...")
            else:
                raise
    print("❌ Не удалось занять порт 7860–7862. Закройте другие приложения или укажите другой порт.")


if __name__ == "__main__":
    _launch()
