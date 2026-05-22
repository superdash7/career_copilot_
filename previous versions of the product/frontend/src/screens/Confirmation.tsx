import { useState } from 'react';
import { ArrowLeft, Sparkles, Cpu, ChevronDown, ChevronUp } from 'lucide-react';
import Layout from '../components/Layout';
import Alert from '../components/Alert';
import ProgressLoader from '../components/ProgressLoader';
import MiniProgress from '../components/MiniProgress';
import SoftOnboardingHint from '../components/SoftOnboardingHint';
import { buildPlan, ApiError } from '../api/client';
import type { AppState, PlanResponse, Scenario } from '../types';
import { skillLevelLabel } from '../types';

interface Props {
  state: AppState;
  onBack: () => void;
  onResult: (plan: PlanResponse) => void;
}

const SCENARIO_LABELS: Record<Scenario, string> = {
  'Следующий грейд': 'Следующий грейд',
  'Смена профессии': 'Смена профессии',
  'Исследование возможностей': 'Исследование возможностей',
};

const INITIAL_VISIBLE = 5;

export default function Confirmation({ state, onBack, onResult }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAllSkills, setShowAllSkills] = useState(false);

  const sortedSkills = [...state.skills].sort((a, b) => a.name.localeCompare(b.name));
  const visibleSkills = showAllSkills ? sortedSkills : sortedSkills.slice(0, INITIAL_VISIBLE);
  const hasMore = sortedSkills.length > INITIAL_VISIBLE;

  const handleGenerate = async () => {
    setLoading(true);
    setError('');
    try {
      const plan = await buildPlan({
        profession: state.profession,
        grade: state.grade,
        skills: state.skills,
        scenario: state.scenario as Scenario,
        target_profession:
          state.scenario === 'Смена профессии' ? state.targetProfession : undefined,
      });
      onResult(plan);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Не удалось получить план. Попробуйте снова.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout step={3}>
        <div className="py-20">
          <ProgressLoader text="Создаём ваш персональный план…" subtext="Это может занять немного времени" durationMs={50000} />
        </div>
      </Layout>
    );
  }

  return (
    <Layout step={3}>
      <div className="space-y-8 slide-up">
        <div>
          <MiniProgress current={3} total={3} label="Подтверждение" />
          <h1 className="text-2xl sm:text-3xl font-bold text-(--color-text-primary) mt-2 mb-2">
            Проверьте данные перед анализом
          </h1>
          <p className="text-(--color-text-secondary)">
            Убедитесь, что всё верно — дальше Career Copilot построит персональный план.
          </p>
        </div>

        <SoftOnboardingHint id="confirm_ready">
          Почти готово — осталось одно действие.
        </SoftOnboardingHint>

        {error && (
          <Alert variant="error" onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {/* Goal summary */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-(--color-text-primary)">Цель</h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="font-medium text-(--color-text-muted)">Профессия</dt>
            <dd className="text-(--color-text-primary)">{state.profession}</dd>
            <dt className="font-medium text-(--color-text-muted)">Сценарий</dt>
            <dd className="text-(--color-text-primary)">
              {state.scenario ? SCENARIO_LABELS[state.scenario as Scenario] : '—'}
            </dd>
            <dt className="font-medium text-(--color-text-muted)">Грейд</dt>
            <dd className="text-(--color-text-primary)">{state.grade}</dd>
            {state.scenario === 'Смена профессии' && (
              <>
                <dt className="font-medium text-(--color-text-muted)">Целевая профессия</dt>
                <dd className="text-(--color-text-primary)">{state.targetProfession}</dd>
              </>
            )}
          </dl>
        </div>

        {/* Skills summary — expandable */}
        <div className="card space-y-4">
          <h2 className="text-lg font-semibold text-(--color-text-primary)">
            Навыки
            <span className="ml-2 text-sm font-normal text-(--color-text-muted)">
              ({state.skills.length})
            </span>
          </h2>
          <div className="flex flex-wrap gap-2">
            {visibleSkills.map((s) => (
              <span
                key={s.name}
                className="inline-flex items-center gap-1.5 rounded-lg bg-(--color-accent-light) px-3 py-1.5 text-sm font-medium text-(--color-accent)"
              >
                {s.name}
                <span className="opacity-60 text-xs">
                  {skillLevelLabel(s.level).toLowerCase()}
                </span>
              </span>
            ))}
          </div>
          {hasMore && (
            <button
              onClick={() => setShowAllSkills(!showAllSkills)}
              className="inline-flex items-center gap-1 text-sm font-medium text-(--color-accent) hover:text-(--color-accent-hover) transition-colors"
            >
              {showAllSkills ? (
                <>Свернуть <ChevronUp className="h-3.5 w-3.5" /></>
              ) : (
                <>Показать все {sortedSkills.length} навыков <ChevronDown className="h-3.5 w-3.5" /></>
              )}
            </button>
          )}
        </div>

        {/* How we build the plan — simplified */}
        <div className="card bg-(--color-accent-light)/50 border-(--color-accent)/10">
          <div className="flex items-start gap-3">
            <Cpu className="h-5 w-5 shrink-0 mt-0.5 text-(--color-accent)" />
            <div>
              <p className="font-semibold text-sm text-(--color-text-primary) mb-1">Что произойдёт дальше</p>
              <p className="text-sm text-(--color-text-secondary) leading-relaxed">
                Мы сравним ваш уровень с требованиями рынка, определим зоны роста
                и сформируем конкретные шаги: 70% — практика на работе, 20% — обучение у коллег,
                10% — курсы и книги.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2">
          <button onClick={onBack} className="btn-secondary">
            <ArrowLeft className="h-4 w-4" /> Назад
          </button>
          <button onClick={handleGenerate} className="btn-primary text-lg px-8 py-4">
            <Sparkles className="h-5 w-5" /> Построить план
          </button>
        </div>
      </div>
    </Layout>
  );
}
