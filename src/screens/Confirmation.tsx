import { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import Alert from '../components/Alert';
import MiniProgress from '../components/MiniProgress';
import SoftOnboardingHint from '../components/SoftOnboardingHint';
import LoadingCarousel from '../components/LoadingCarousel';
import { buildPlan, createAnalysis, ApiError } from '../api/client';
import { showToast } from '../components/toastStore';
import type { AppState, PlanResponse, Scenario } from '../types';
import { skillLevelLabel } from '../types';
import Button from '../components/ui/Button';
import MonoLabel from '../components/ui/MonoLabel';
import {
  startProfileAnalysisFaviconPulse,
  stopProfileAnalysisFaviconPulse,
  requestAnalysisNotificationPermission,
  notifyProfileAnalysisReadyIfHadBackground,
} from '../utils/profileAnalysisNotify';

interface Props {
  state: AppState;
  onBack: () => void;
  onResult: (plan: PlanResponse) => void;
  isAuthenticated?: boolean;
  onRequireAuth?: () => void;
}


const INITIAL_VISIBLE = 5;

export default function Confirmation({ state, onBack, onResult, isAuthenticated = true, onRequireAuth }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAllSkills, setShowAllSkills] = useState(false);
  const [loadingCycle, setLoadingCycle] = useState(0);

  useEffect(() => () => stopProfileAnalysisFaviconPulse(), []);

  const sortedSkills = [...state.skills].sort((a, b) => a.name.localeCompare(b.name));
  const visibleSkills = showAllSkills ? sortedSkills : sortedSkills.slice(0, INITIAL_VISIBLE);
  const hasMore = sortedSkills.length > INITIAL_VISIBLE;

  const handleGenerate = async () => {
    setLoading(true);
    setLoadingCycle((c) => c + 1);
    setError('');
    startProfileAnalysisFaviconPulse();
    await requestAnalysisNotificationPermission();
    try {
      const scenario = (state.scenario || 'Следующий грейд') as Scenario;
      const plan = await buildPlan({
        profession: state.profession,
        grade: state.grade,
        skills: state.skills,
        scenario,
        target_profession:
          state.scenario === 'Смена профессии' ? state.targetProfession : undefined,
      });

      let enrichedPlan = plan;
      if (isAuthenticated) {
        try {
          const saved = await createAnalysis({
            scenario,
            current_role: state.profession || undefined,
            target_role: state.scenario === 'Смена профессии' ? state.targetProfession || undefined : undefined,
            skills_json: {
              profession: state.profession,
              grade: state.grade,
              scenario,
              target_profession: state.targetProfession,
              skills: state.skills,
            },
            result_json: plan as unknown as Record<string, unknown>,
          });
          enrichedPlan = { ...plan, analysis_id: saved.id };
        } catch {
          showToast('План построен, но не удалось сохранить его в историю');
        }
      }

      const userWasAway = typeof document !== 'undefined' && document.visibilityState !== 'visible';
      onResult(enrichedPlan);
      notifyProfileAnalysisReadyIfHadBackground(userWasAway);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Не удалось получить план. Попробуйте снова.');
      }
    } finally {
      stopProfileAnalysisFaviconPulse();
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Layout step={2}>
        <div className="mx-auto max-w-lg px-4">
          <LoadingCarousel
            key={loadingCycle}
            text="Анализ профиля"
            subtext="Этот шаг может занять до минуты."
            showSpinner={false}
          />
        </div>
      </Layout>
    );
  }

  return (
    <Layout step={2}>
      <div className="space-y-8 slide-up">
        <div>
          <MiniProgress current={3} total={4} label="Анализ" />
          <h1 className="mt-2 mb-2 text-3xl leading-tight text-(--color-text-primary) sm:text-4xl">
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
          <div className="space-y-3">
            <Alert variant="error" onClose={() => setError('')}>
              {error}
            </Alert>
            <p className="text-sm text-(--color-text-secondary)">
              Проверьте интернет и попробуйте снова. Если ошибка повторяется — подождите минуту: сервис мог быть перегружен.
            </p>
            <Button variant="secondary" onClick={handleGenerate}>
              Повторить анализ
            </Button>
          </div>
        )}

        {/* Goal summary */}
        <div className="card space-y-4">
          <MonoLabel>Цель и сценарий</MonoLabel>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="font-medium text-(--color-text-muted)">Профессия</dt>
            <dd className="text-(--color-text-primary)">{state.profession}</dd>
            <dt className="font-medium text-(--color-text-muted)">Сценарий</dt>
            <dd className="text-(--color-text-primary)">
              {state.scenario || '—'}
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
          <MonoLabel>
            Навыки профиля
            <span className="ml-2 text-sm font-normal text-(--color-text-muted) lowercase tracking-normal" style={{ fontFamily: 'inherit' }}>
              ({state.skills.length})
            </span>
          </MonoLabel>
          <div className="flex flex-wrap gap-2">
            {visibleSkills.map((s) => (
              <span
                key={s.name}
                className="inline-flex items-center gap-1.5 rounded-full border border-(--color-border) bg-[var(--chip)] px-3 py-1.5 text-sm font-medium text-[var(--blue-deep)]"
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
              className="inline-flex items-center gap-1 text-sm font-medium text-[var(--blue-deep)] transition-colors hover:text-(--color-accent-hover)"
            >
              {showAllSkills ? (
                <>Свернуть ▲</>
              ) : (
                <>Показать все {sortedSkills.length} навыков ▼</>
              )}
            </button>
          )}
        </div>

        {/* How we build the plan — simplified */}
        <div className="card border-(--color-border) bg-[var(--chip)]">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-(--color-border) text-xs text-[var(--blue-deep)]">
              ◎
            </span>
            <div>
              <p className="mb-1 text-sm font-semibold text-(--color-text-primary)">Что произойдет дальше</p>
              <p className="text-sm text-(--color-text-secondary) leading-relaxed">
                На следующем шаге мы проанализируем ваш профиль: сравним навыки с требованиями роли
                и покажем зоны роста. Персональный план сформируется после этого.
              </p>
            </div>
          </div>
        </div>

        {!isAuthenticated && (
          <div className="card border-(--color-border) bg-[color-mix(in_srgb,var(--paper)_92%,white)]">
            <p className="text-sm text-(--color-text-secondary) leading-relaxed">
              Вы получите черновик плана развития. Чтобы сохранить историю,
              открыть полный план и трекинг прогресса — создайте аккаунт.
            </p>
            {onRequireAuth && (
              <div className="mt-3">
                <Button variant="secondary" onClick={onRequireAuth}>
                  Войти и сохранить прогресс →
                </Button>
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-between pt-2">
          <Button variant="secondary" onClick={onBack}>
            ← Назад
          </Button>
          <Button onClick={handleGenerate}>Построить план →</Button>
        </div>
      </div>
    </Layout>
  );
}
