
"""Форматирование ответа для пользователя"""

from gap_analyzer import level_display


def _build_skill_context(data_loader, skill_gaps, grade):
    """Собирает описания уровней + примеры задач для навыков из gap-списка (для LLM)."""
    parts = []
    for g in skill_gaps[:15]:
        detail = data_loader.get_skill_detail(g["name"], grade)
        if not detail:
            continue
        block = f"[Навык: {g['name']}] Требуемый уровень: {detail['level_key']}"
        if detail["description"]:
            block += f"\nОписание уровня: {detail['description']}"
        if detail["tasks"]:
            block += f"\nПримеры задач на развитие: {detail['tasks']}"
        parts.append(block)
    return "\n\n".join(parts)


def _params_table(gaps, strong):
    """Markdown-таблица разрывов по параметрам атласа."""
    if not gaps and not strong:
        return "Нет данных по параметрам.\n\n"
    out = "| Параметр | Текущий | Требуемый | Разрыв |\n"
    out += "|---|---|---|---|\n"
    for g in gaps:
        curr = level_display(g["current"], is_atlas=True)
        req = level_display(g["required"], is_atlas=True)
        out += f"| **{g['name']}** | {curr} | {req} | {g['delta']} |\n"
    for s in strong:
        lvl = level_display(s["level"], is_atlas=True)
        out += f"| {s['name']} | {lvl} | {lvl} | 0 |\n"
    out += "\n"
    return out


def _skills_table(gaps, strong):
    """Markdown-таблица разрывов по навыкам (без описаний — они идут ниже)."""
    if not gaps and not strong:
        return "Нет данных по навыкам.\n\n"
    out = "| Навык | Текущий | Требуемый | Разрыв |\n"
    out += "|---|---|---|---|\n"
    for g in gaps:
        curr = level_display(g["current"], is_atlas=False)
        req = level_display(g["required"], is_atlas=False)
        out += f"| **{g['name']}** | {curr} | {req} | {g['delta']} |\n"
    for s in strong[:5]:
        lvl = level_display(s["level"], is_atlas=False)
        out += f"| {s['name']} | {lvl} | {lvl} | 0 |\n"
    out += "\n"
    return out


def _skill_details_blocks(data_loader, skill_gaps, grade):
    """Структурированные блоки с описанием уровня и задачами на развитие."""
    out = ""
    for g in skill_gaps[:12]:
        detail = data_loader.get_skill_detail(g["name"], grade)
        if not detail:
            continue
        if not detail["description"] and not detail["tasks"]:
            continue
        out += f"#### {g['name']}\n\n"
        if detail["description"]:
            out += f"> **Целевой уровень ({detail['level_key']}):** {detail['description']}\n\n"
        if detail["tasks"]:
            out += f"**Задачи на развитие:**\n\n{detail['tasks']}\n\n"
    return out


class OutputFormatter:
    def __init__(self, data_loader):
        self.data = data_loader
        self._plan_gen = None

    def _get_plan_generator(self):
        if self._plan_gen is None:
            try:
                from plan_generator import PlanGenerator
                self._plan_gen = PlanGenerator()
            except ImportError:
                self._plan_gen = None
        return self._plan_gen

    def format_plan(self, gap_analysis, target_role_name):
        work = gap_analysis.get("missing", []) + [
            (g[0], g[2]) if len(g) == 3 else (g[0], g[1]) for g in gap_analysis.get("gaps", [])
        ]
        out = f"# План развития: {target_role_name}\n\n"
        out += f"Совпадение профиля: {gap_analysis.get('match_percent', 0)}%\n\n"
        if work:
            out += "## Зона роста\n\n"
            for item in work:
                out += f"- {item[0]} → целевой уровень {item[1]}\n"
        if gap_analysis.get("strong"):
            out += "\n## Сильные стороны\n\n"
            for s, lvl in gap_analysis["strong"]:
                out += f"- {s} (уровень {lvl})\n"
        return out

    def format_next_grade(self, structured, target_role_name, profession_display,
                          current_grade=None, target_grade=None, profession_internal=None):
        atlas_gaps = structured.get("atlas_gaps", [])
        skill_gaps = structured.get("skill_gaps", [])
        atlas_strong = structured.get("atlas_strong", [])
        skill_strong = structured.get("skill_strong", [])
        match_percent = structured.get("match_percent", 0)

        all_gaps = sorted(atlas_gaps + skill_gaps, key=lambda x: -x["delta"])
        top_blockers = all_gaps[:5]
        focus_str = ", ".join(b["name"] for b in top_blockers) if top_blockers else "—"

        cur_grade = current_grade or "Middle"
        tgt_grade = target_grade or "Senior"

        # --- Header ---
        out = f"# Цель: Перейти на следующий грейд\n\n"
        out += f"| | |\n|---|---|\n"
        out += f"| **Целевая роль** | {target_role_name} |\n"
        out += f"| **Совпадение** | {match_percent}% |\n"
        out += f"| **Фокус роста** | {focus_str} |\n\n"
        out += "---\n\n"

        # --- Section 1: Atlas narrative ---
        out += "## Ожидания целевого грейда\n\n"
        try:
            from next_grade_service import build_next_grade_narrative, build_next_grade_rag_context
            narrative = build_next_grade_narrative(cur_grade, tgt_grade, self.data.atlas_map)
            for pe in narrative.param_expectations:
                if pe.get("target_text"):
                    out += f"**{pe['param_name']}**\n\n"
                    if pe.get("current_text"):
                        out += f"> *Сейчас ({cur_grade}):* {pe['current_text']}\n\n"
                    out += f"> *Цель ({tgt_grade}):* {pe['target_text']}\n\n"
        except Exception:
            pass

        # --- Section 2: Param gaps table ---
        out += "## Разрывы по параметрам\n\n"
        if atlas_gaps:
            out += _params_table(atlas_gaps, [])
        else:
            out += "Нет разрывов по параметрам — текущий грейд соответствует требованиям.\n\n"

        # --- Section 3: Skill gaps table ---
        out += "## Разрывы по навыкам\n\n"
        if skill_gaps:
            out += _skills_table(skill_gaps[:15], skill_strong[:5] if len(skill_gaps) < 10 else [])
        else:
            out += "Нет разрывов по навыкам.\n\n"

        # --- Section 4: Skill detail blocks ---
        if skill_gaps:
            details = _skill_details_blocks(self.data, skill_gaps, tgt_grade)
            if details:
                out += "## Описание навыков и задачи на развитие\n\n"
                out += details

        # --- Summary ---
        out += "## Сводка\n\n"
        if top_blockers:
            out += "**Приоритет развития:** " + ", ".join(b["name"] for b in top_blockers) + "\n\n"
        if skill_strong:
            out += "**Сильные стороны:** " + ", ".join(s["name"] for s in skill_strong[:8]) + "\n\n"
        out += "---\n\n"

        # --- Step 2: Plan ---
        out += "## План развития\n\n"
        gen = self._get_plan_generator()
        if gen and gen.client:
            rag_context = ""
            skill_context = _build_skill_context(self.data, skill_gaps, tgt_grade)
            try:
                role_internal = profession_internal or self.data.get_internal_role_name(profession_display)
                rag_context = build_next_grade_rag_context(
                    atlas_gaps, skill_gaps, tgt_grade, self.data.atlas_map, self.data, role_internal
                )
            except Exception:
                try:
                    from rag_service import get_rag_context_for_plan
                    step1_summary = " ".join([g["name"] for g in atlas_gaps[:5] + skill_gaps[:5]])
                    rag_context = get_rag_context_for_plan(step1_summary, target_role_name)
                except Exception:
                    pass
            gap_summary = {
                "param_gaps": [{"name": g["name"], "delta": g["delta"]} for g in atlas_gaps],
                "skill_gaps": [{"name": g["name"], "delta": g["delta"], "current": g["current"], "required": g["required"]} for g in skill_gaps[:15]],
            }
            strong_names = [s["name"] for s in skill_strong[:20]]
            step2 = gen.generate_plan_702010(
                "next_grade", out, target_role_name,
                context=f"Профессия: {profession_display}.",
                rag_context=rag_context,
                skill_context=skill_context,
                strong_skills=strong_names,
                gap_summary=gap_summary,
            )
            out += step2
        else:
            out += "*Для генерации персонального плана укажите OPENAI_API_KEY в .env.*\n\n"
            out += "**Развитие через реальные задачи:** задачи из диагностики с фиксацией результата.\n"
            out += "**Взаимодействие и обратная связь:** обратная связь, наставник, калибровки каждые 2–4 недели.\n"
            out += "**Курсы и тренинги:** материалы по недостающим навыкам.\n\n"
            out += "**Чекпоинты:** пересмотр через 4, 8 и 12 недель.\n"

        return out

    def format_change_profession(self, switch_view_model, target_role_name, target_profession_display):
        from switch_profession_service import SwitchViewModel, build_switch_rag_context

        if not isinstance(switch_view_model, SwitchViewModel):
            return self.format_change_profession_legacy(
                switch_view_model, target_role_name, target_profession_display
            )

        vm = switch_view_model
        match_pct = int(vm.match_score * 100)
        focus_names = [m.get("name", "") for m in vm.missing_skills[:5] if m.get("name")]
        focus_str = ", ".join(focus_names) if focus_names else "—"

        # --- Header ---
        out = f"# Цель: Сменить профессию\n\n"
        out += f"| | |\n|---|---|\n"
        out += f"| **Целевая профессия** | {target_profession_display} |\n"
        out += f"| **Совпадение** | {match_pct}% |\n"
        out += f"| **Baseline** | {vm.baseline_level} |\n"
        out += f"| **В приоритете** | {focus_str} |\n\n"
        out += "---\n\n"

        # --- Matched skills ---
        out += "## Что уже совпадает\n\n"
        if vm.matched_skills:
            out += "| Навык | Описание |\n|---|---|\n"
            for m in vm.matched_skills[:8]:
                snip = (m.get("snippet") or "").strip()
                out += f"| **{m.get('name', '')}** | {snip} |\n"
            out += "\n"
        else:
            out += "Пока мало пересечений — фокус на ключевых навыках целевой роли.\n\n"

        # --- Missing skills ---
        out += "## Чего не хватает\n\n"
        if vm.missing_skills:
            out += "| Навык | Приоритет |\n|---|---|\n"
            for m in vm.missing_skills[:12]:
                out += f"| **{m.get('name', '')}** | {m.get('importance', '')} |\n"
            out += "\n"

            details = _skill_details_blocks(self.data,
                [{"name": m.get("name", "")} for m in vm.missing_skills[:8]], "Middle")
            if details:
                out += "### Описание навыков и задачи на развитие\n\n"
                out += details

        if vm.suggested_tracks:
            out += "## Рекомендуемые треки\n\n"
            for t in vm.suggested_tracks[:3]:
                out += f"- {t}\n"
            out += "\n"
        out += "---\n\n"

        # --- Plan ---
        out += "## План развития\n\n"
        focus_names_for_plan = [m.get("name", "") for m in vm.missing_skills[:7] if m.get("name")]
        gen = self._get_plan_generator()
        if gen and gen.client and focus_names_for_plan:
            try:
                rag_context = build_switch_rag_context(
                    focus_names_for_plan, target_profession_display, vm.baseline_level, self.data,
                )
            except Exception:
                rag_context = ""
            skill_context = _build_skill_context(
                self.data,
                [{"name": n, "delta": 1} for n in focus_names_for_plan],
                "Middle",
            )
            gap_summary = {
                "gaps": [{"name": n} for n in focus_names_for_plan],
                "transferable": [m.get("name", "") for m in vm.matched_skills[:10]],
            }
            strong_names = [m.get("name", "") for m in vm.matched_skills[:15]]
            step2 = gen.generate_plan_702010(
                "change_profession", out, target_role_name,
                context="Сфокусируй план на недостающих навыках для перехода.",
                rag_context=rag_context,
                skill_context=skill_context,
                strong_skills=strong_names,
                gap_summary=gap_summary,
            )
            out += step2
        else:
            out += "*Укажите OPENAI_API_KEY для генерации плана.*\n\n"
            out += "**Развитие через реальные задачи:** мини-проекты по недостающим навыкам.\n"
            out += "**Взаимодействие и обратная связь:** наставник, интервью.\n"
            out += "**Курсы и тренинги:** курсы по ключевым навыкам.\n"
        return out

    def format_change_profession_legacy(self, structured, target_role_name, target_profession_display):
        match_percent = structured.get("match_percent", 0)
        strong = structured.get("strong", [])
        missing = structured.get("missing", [])
        gaps = structured.get("gaps", [])

        out = f"# Цель: Сменить профессию\n\n"
        out += f"**Целевая профессия/роль:** {target_role_name}\n\n---\n\n"
        out += "## Оценка соответствия\n\n"
        out += f"**Совпадение:** {match_percent}%\n\n"
        if strong:
            out += "| Навык | Уровень |\n|---|---|\n"
            for s, lvl in strong[:20]:
                out += f"| {s} | {lvl} |\n"
            out += "\n"
        work = [(m[0], m[1]) for m in missing] + [(g[0], g[2]) for g in gaps if len(g) == 3]
        if work:
            out += "| Навык | Требуется |\n|---|---|\n"
            for name, req in work[:15]:
                out += f"| {name} | {req} |\n"
            out += "\n"
        out += "---\n\n## План развития\n\n"
        gen = self._get_plan_generator()
        if gen and gen.client:
            try:
                from rag_service import get_rag_context_for_plan
                rag_context = get_rag_context_for_plan(" ".join([m[0] for m in missing[:5]]), target_role_name)
            except Exception:
                rag_context = ""
            out += gen.generate_plan_702010("change_profession", out, target_role_name, context="", rag_context=rag_context)
        else:
            out += "*Укажите OPENAI_API_KEY.*\n"
        return out

    def format_explore(self, view_model, user_skills):
        from explore_recommendations import ExploreViewModel

        if not isinstance(view_model, ExploreViewModel):
            return "# Цель: Исследовать возможности\n\n*Нет данных для отображения.*"

        def card_block(cards, section_title):
            if not cards:
                return ""
            out = f"### {section_title}\n\n"
            for c in cards:
                out += f"**{c.title}** — {c.match_label}"
                if c.percent_text:
                    out += f" ({c.percent_text})"
                out += "\n\n"
                if c.reasons:
                    out += "*Почему подходит:* " + "; ".join(c.reasons[:5]) + "\n\n"
                if c.add_skills:
                    out += "*Что добавить:* " + ", ".join(c.add_skills[:3]) + "\n\n"
                if c.key_skills:
                    out += "*Навыки роли:* " + ", ".join(c.key_skills[:8]) + "\n\n"
            return out

        out = "# Возможные направления\n\n"
        out += card_block(view_model.closest, "Ближайшие роли (реалистичный переход)")
        out += card_block(view_model.adjacent, "Смежные направления (требуют усиления базы)")
        if view_model.far:
            out += "### Требуют переквалификации\n\n"
            for c in view_model.far:
                out += f"- **{c.title}** — {c.match_label} ({c.percent_text})\n"
            out += "\n"

        out += "---\n\n"
        out += "**Следующий шаг:** выберите роль и нажмите «Сгенерировать план».\n"
        return out
