import { useState } from 'react';
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Tooltip,
} from 'recharts';
import {
  Copy, RotateCcw, ArrowLeft, ChevronRight, ChevronDown, Check,
  TrendingUp, FileText, CheckCircle2, Target, Sparkles,
  BookOpen, MessageCircle, ListTodo,
} from 'lucide-react';
import Layout from '../components/Layout';
import ProgressLoader from '../components/ProgressLoader';
import { buildFocusedPlan, ApiError } from '../api/client';
import type {
  PlanResponse, GrowthAnalysis, SwitchAnalysis, ExploreAnalysis,
  AppState, FocusedPlan,
} from '../types';

interface Props {
  plan: PlanResponse;
  appState: AppState;
  onReset: () => void;
  onBackToSkills: () => void;
}

export default function Result({ plan, appState, onReset, onBackToSkills }: Props) {
  const [copied, setCopied] = useState(false);
  const [selectedGaps, setSelectedGaps] = useState<Set<string>>(new Set());
  const [focusedPlan, setFocusedPlan] = useState<FocusedPlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState('');

  const handleCopy = async () => {
    await navigator.clipboard.writeText(plan.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const toggleGap = (name: string) => {
    setSelectedGaps(prev => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handleGeneratePlan = async () => {
    if (selectedGaps.size === 0) return;
    setPlanLoading(true);
    setPlanError('');
    try {
      const result = await buildFocusedPlan({
        profession: appState.profession,
        grade: appState.grade,
        scenario: appState.scenario,
        target_profession: appState.targetProfession || undefined,
        selected_skills: Array.from(selectedGaps),
      });
      setFocusedPlan(result);
    } catch (err) {
      setPlanError(err instanceof ApiError ? err.message : 'Не удалось сформировать план');
    } finally {
      setPlanLoading(false);
    }
  };

  // Collect gap names from analysis
  const gapNames: string[] = [];
  if (plan.analysis?.scenario === 'growth') {
    for (const g of plan.analysis.skill_gaps) gapNames.push(g.name);
  } else if (plan.analysis?.scenario === 'switch') {
    for (const g of plan.analysis.gaps) gapNames.push(g.name);
  }

  return (
    <Layout step={4} wide>
      <div className="space-y-6 slide-up">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-(--color-text-primary)">
              Результаты анализа
            </h1>
            <p className="text-(--color-text-muted) mt-1">Выберите навыки для развития и сформируйте план.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={onReset} className="btn-secondary text-sm">
              <RotateCcw className="h-4 w-4" /> Заново
            </button>
            <button onClick={handleCopy} className="btn-secondary text-sm">
              {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
              {copied ? 'Скопировано' : 'Скопировать'}
            </button>
          </div>
        </div>

        {/* Visual analysis */}
        {plan.analysis && (
          <div className="fade-in">
            {plan.analysis.scenario === 'growth' && <GrowthView data={plan.analysis} />}
            {plan.analysis.scenario === 'switch' && <SwitchView data={plan.analysis} />}
            {plan.analysis.scenario === 'explore' && <ExploreView data={plan.analysis} />}
          </div>
        )}

        {/* Gap selection for plan generation */}
        {gapNames.length > 0 && !focusedPlan && !planLoading && (
          <div className="card fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-9 w-9 rounded-lg bg-(--color-accent-light) flex items-center justify-center">
                <Target className="h-5 w-5 text-(--color-accent)" />
              </div>
              <div>
                <h3 className="font-semibold text-(--color-text-primary)">Что хотите развить?</h3>
                <p className="text-xs text-(--color-text-muted)">Выберите навыки — мы сформируем фокусный план</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mb-4">
              {gapNames.map(name => (
                <button
                  key={name}
                  onClick={() => toggleGap(name)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                    selectedGaps.has(name)
                      ? 'bg-(--color-accent) text-white border-(--color-accent)'
                      : 'bg-(--color-surface-alt) text-(--color-text-secondary) border-(--color-border) hover:border-(--color-accent)/40'
                  }`}
                >
                  {selectedGaps.has(name) && <Check className="h-3 w-3 inline mr-1" />}
                  {name}
                </button>
              ))}
            </div>
            {selectedGaps.size > 0 && (
              <button onClick={handleGeneratePlan} className="btn-primary">
                <Sparkles className="h-4 w-4" />
                Сформировать план ({selectedGaps.size})
              </button>
            )}
            {planError && <p className="text-sm text-red-500 mt-3">{planError}</p>}
          </div>
        )}

        {/* Plan loading */}
        {planLoading && (
          <ProgressLoader text="Формируем персональный план…" subtext="Это займёт несколько секунд" durationMs={20000} />
        )}

        {/* Focused plan */}
        {focusedPlan && <FocusedPlanView plan={focusedPlan} />}

        {/* Footer */}
        <div className="flex flex-wrap gap-3 pt-2">
          <button onClick={onBackToSkills} className="btn-secondary text-sm">
            <ArrowLeft className="h-4 w-4" /> Уточнить навыки
          </button>
        </div>
      </div>
    </Layout>
  );
}


// ======================== FOCUSED PLAN ========================

function FocusedPlanView({ plan }: { plan: FocusedPlan }) {
  return (
    <div className="space-y-4 fade-in">
      {/* Tasks */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-9 w-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <ListTodo className="h-5 w-5 text-blue-600" />
          </div>
          <h3 className="font-semibold text-(--color-text-primary)">Задачи на развитие</h3>
        </div>
        <div className="space-y-4">
          {plan.tasks.map((t, i) => (
            <div key={i}>
              <p className="text-sm font-semibold text-(--color-accent) mb-2">{t.skill}</p>
              <ul className="space-y-1.5">
                {t.items.map((item, j) => (
                  <li key={j} className="flex items-start gap-2 text-sm text-(--color-text-secondary)">
                    <ChevronRight className="h-4 w-4 mt-0.5 shrink-0 text-(--color-text-muted)" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      {/* Communication */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-9 w-9 rounded-lg bg-purple-500/10 flex items-center justify-center">
            <MessageCircle className="h-5 w-5 text-purple-600" />
          </div>
          <h3 className="font-semibold text-(--color-text-primary)">Развитие через общение</h3>
        </div>
        <ul className="space-y-2">
          {plan.communication.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-(--color-text-secondary)">
              <ChevronRight className="h-4 w-4 mt-0.5 shrink-0 text-purple-400" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Learning */}
      <div className="card">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-9 w-9 rounded-lg bg-emerald-500/10 flex items-center justify-center">
            <BookOpen className="h-5 w-5 text-emerald-600" />
          </div>
          <h3 className="font-semibold text-(--color-text-primary)">Книги и тренинги</h3>
        </div>
        <ul className="space-y-2">
          {plan.learning.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-(--color-text-secondary)">
              <ChevronRight className="h-4 w-4 mt-0.5 shrink-0 text-emerald-400" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}


// ======================== GROWTH ========================

function GrowthView({ data }: { data: GrowthAnalysis }) {
  const radarMax = Math.max(...data.radar_data.map(d => d.target), 5);
  const radarForChart = data.radar_data.map(d => ({
    subject: d.param,
    current: d.current,
    target: d.target,
  }));

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-blue-500/10 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <span className="text-xs font-bold text-blue-600 uppercase tracking-wide">План роста</span>
              <h2 className="text-xl font-bold text-(--color-text-primary)">
                {data.current_grade} <span className="text-(--color-text-muted) mx-1">→</span> {data.target_grade}
              </h2>
            </div>
          </div>
          <div className="text-right px-5 py-3 rounded-xl bg-(--color-accent-light)">
            <div className="text-xs text-(--color-text-muted) font-medium">Совпадение</div>
            <div className="text-2xl font-bold text-(--color-accent)">{data.match_percent}%</div>
          </div>
        </div>
      </div>

      {radarForChart.length > 2 && (
        <div className="card">
          <h3 className="font-semibold text-(--color-text-primary) mb-4">Параметры атласа</h3>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radarForChart}>
                  <PolarGrid stroke="var(--color-border)" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} />
                  <PolarRadiusAxis domain={[0, radarMax]} tick={false} axisLine={false} />
                  <Radar name="Текущий" dataKey="current" stroke="#818cf8" fill="#818cf8" fillOpacity={0.5} />
                  <Radar name="Цель" dataKey="target" stroke="#34d399" fill="#34d399" fillOpacity={0.15} />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-bold text-(--color-text-muted) uppercase tracking-wide mb-3">Зоны развития</p>
              {data.radar_data.filter(d => d.target > d.current).map((d, i) => (
                <div key={i} className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                  <div className="flex justify-between text-sm font-medium mb-1">
                    <span className="text-(--color-text-primary)">{d.param}</span>
                    <span className="text-amber-600">{d.current_label} → {d.target_label}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-amber-200 overflow-hidden">
                    <div className="h-full bg-amber-500 rounded-full" style={{ width: `${(d.current / d.target) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {data.skill_gaps.length > 0 && <SkillGapsSection gaps={data.skill_gaps} />}

      {data.skill_strong.length > 0 && (
        <div className="card">
          <h3 className="font-semibold text-(--color-text-primary) mb-3 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-500" /> Сильные стороны
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.skill_strong.map(s => (
              <span key={s.name} className="px-3 py-1.5 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 rounded-lg text-sm font-medium border border-emerald-500/20">
                {s.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


// ======================== SWITCH ========================

function SwitchView({ data }: { data: SwitchAnalysis }) {
  return (
    <div className="space-y-6">
      <div className="card">
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1 text-center sm:text-left">
            <span className="text-xs font-bold text-(--color-text-muted) uppercase">Из профессии</span>
            <div className="font-semibold text-(--color-text-primary)">{data.from_role}</div>
          </div>
          <ChevronRight className="h-5 w-5 text-(--color-text-muted) hidden sm:block" />
          <div className="flex-1 text-center sm:text-left">
            <span className="text-xs font-bold text-(--color-text-muted) uppercase">В профессию</span>
            <div className="font-semibold text-purple-600">{data.to_role}</div>
          </div>
          <div className="px-5 py-3 rounded-xl bg-purple-500/10 text-center">
            <div className="text-xs text-purple-600 font-bold uppercase">Совместимость</div>
            <div className="text-2xl font-bold text-purple-700">{data.match_percent}%</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="flex items-center gap-2 font-semibold text-emerald-700 dark:text-emerald-400 mb-3">
            <CheckCircle2 className="h-5 w-5" /> Переносимые навыки
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.transferable.map(s => (
              <span key={s.name} className="px-3 py-1.5 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 rounded-lg text-sm font-medium border border-emerald-500/20">
                {s.name}
              </span>
            ))}
          </div>
        </div>
        <div className="card">
          <h3 className="flex items-center gap-2 font-semibold text-amber-700 dark:text-amber-400 mb-3">
            <Target className="h-5 w-5" /> Зона роста
          </h3>
          <div className="flex flex-wrap gap-2">
            {data.gaps.map(g => (
              <span key={g.name} className="px-3 py-1.5 bg-amber-500/10 text-amber-800 dark:text-amber-300 rounded-lg text-sm font-medium border border-amber-500/20">
                {g.name}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


// ======================== EXPLORE ========================

function ExploreView({ data }: { data: ExploreAnalysis }) {
  const categoryColor: Record<string, string> = {
    closest: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20',
    adjacent: 'bg-amber-500/10 text-amber-700 border-amber-500/20',
    far: 'bg-slate-500/10 text-slate-600 border-slate-500/20',
  };
  const categoryLabel: Record<string, string> = {
    closest: 'Ближайшие', adjacent: 'Смежные', far: 'Дальние',
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {data.roles.map((role, idx) => (
        <ExploreRoleCard key={idx} role={role} categoryColor={categoryColor} categoryLabel={categoryLabel} />
      ))}
    </div>
  );
}

function ExploreRoleCard({ role, categoryColor, categoryLabel }: {
  role: ExploreAnalysis['roles'][0];
  categoryColor: Record<string, string>;
  categoryLabel: Record<string, string>;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="card hover:shadow-md transition-all cursor-pointer" onClick={() => setOpen(!open)}>
      <div className="flex justify-between items-start mb-3">
        <h3 className="font-bold text-(--color-text-primary) text-lg">{role.title}</h3>
        <span className={`px-2.5 py-1 rounded-lg text-xs font-bold border ${categoryColor[role.category] || ''}`}>
          {role.match}%
        </span>
      </div>
      <span className="text-xs font-medium text-(--color-text-muted)">{categoryLabel[role.category]}</span>
      {role.missing.length > 0 && (
        <div className="mt-3">
          <span className="text-xs font-semibold text-(--color-text-muted) uppercase">Не хватает:</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {role.missing.map(m => (
              <span key={m} className="text-xs px-2 py-1 bg-(--color-surface-alt) text-(--color-text-secondary) rounded border border-(--color-border)">{m}</span>
            ))}
          </div>
        </div>
      )}
      {open && role.reasons.length > 0 && (
        <div className="mt-4 pt-3 border-t border-(--color-border) fade-in">
          <ul className="space-y-1">
            {role.reasons.map((r, i) => (
              <li key={i} className="text-sm text-(--color-text-secondary) flex items-start gap-2">
                <ChevronRight className="h-3.5 w-3.5 mt-0.5 shrink-0 text-(--color-accent)" /> {r}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}


// ======================== SHARED ========================

function SkillGapsSection({ gaps }: { gaps: Array<{ name: string; description?: string; tasks?: string; level_key?: string }> }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const withDetails = gaps.filter(g => g.description || g.tasks);
  if (withDetails.length === 0) return null;

  return (
    <div className="card">
      <h3 className="font-semibold text-(--color-text-primary) mb-4 flex items-center gap-2">
        <FileText className="h-5 w-5 text-(--color-accent)" /> Навыки: описание и задачи
      </h3>
      <div className="space-y-2">
        {withDetails.map((g, i) => (
          <div key={g.name} className="rounded-xl border border-(--color-border) overflow-hidden">
            <button
              onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
              className="w-full flex items-center justify-between p-4 text-left hover:bg-(--color-surface-alt) transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="font-medium text-(--color-text-primary)">{g.name}</span>
                {g.level_key && (
                  <span className="text-xs px-2 py-0.5 rounded bg-(--color-accent-light) text-(--color-accent) font-medium">
                    {g.level_key}
                  </span>
                )}
              </div>
              <ChevronDown className={`h-4 w-4 text-(--color-text-muted) transition-transform ${expandedIdx === i ? 'rotate-180' : ''}`} />
            </button>
            {expandedIdx === i && (
              <div className="px-4 pb-4 fade-in space-y-3">
                {g.description && (
                  <div className="p-3 rounded-lg bg-(--color-accent-light)/50 border-l-3 border-(--color-accent)">
                    <p className="text-xs font-bold text-(--color-text-muted) uppercase mb-1">Описание уровня</p>
                    <p className="text-sm text-(--color-text-secondary) leading-relaxed">{g.description}</p>
                  </div>
                )}
                {g.tasks && (
                  <div className="p-3 rounded-lg bg-emerald-500/5 border-l-3 border-emerald-500">
                    <p className="text-xs font-bold text-(--color-text-muted) uppercase mb-1">Задачи на развитие</p>
                    <p className="text-sm text-(--color-text-secondary) leading-relaxed whitespace-pre-line">{g.tasks}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
