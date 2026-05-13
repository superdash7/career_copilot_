import { useMemo, useState } from 'react';
import { ArrowRight, ArrowLeft, HelpCircle, Briefcase, Clock, CheckCircle2, Sparkles } from 'lucide-react';
import Layout from '../components/Layout';
import Alert from '../components/Alert';
import { useAuth } from '../auth/AuthContext';
import { saveOnboarding, ApiError } from '../api/client';
import { showToast } from '../components/toastStore';
import type { OnboardingPainPoint, Scenario } from '../types';
import { deriveScenarioRecommendation } from '../utils/onboarding';
import Eyebrow from '../components/ui/Eyebrow';
import Button from '../components/ui/Button';

interface Props {
  initialExperience?: string;
  initialPainPoint?: string;
  initialHours?: number;
  onBack?: () => void;
  /** После регистрации из мастера: короче копирайт + выход к плану без квиза */
  compactFromWizard?: boolean;
  onComplete: (result: { recommendedScenario: Scenario; painPoint: OnboardingPainPoint; developmentHoursPerWeek: number }) => void;
}

const PAIN_OPTIONS: Array<{ value: OnboardingPainPoint; label: string; sub: string }> = [
  { value: 'рост', label: 'Вырасти в должности', sub: 'Понять, какие навыки нужно подтянуть для перехода на следующий грейд.' },
  { value: 'неопределённость', label: 'Найти направление для роста', sub: 'Я пока не знаю, куда двигаться дальше, и хочу изучить возможные варианты.' },
  { value: 'смена', label: 'Сменить профессию', sub: 'Перейти в совершенно новую сферу по четкому пошаговому плану.' },
  { value: 'стагнация', label: 'Сделать развитие системным', sub: 'Цель есть, но нужен структурированный план обучения без хаоса.' },
];

const EXPERIENCE_OPTIONS = [
  'До 1\u00a0года',
  '1–3 года',
  '3–6 лет',
  'Более 6 лет',
];

const HOURS_OPTIONS = [
  { value: 2, label: '1–2 ч' },
  { value: 4, label: '3–5 ч' },
  { value: 8, label: '5–10 ч' },
  { value: 12, label: '10+ ч' },
];

type Step = 'pain' | 'experience' | 'hours';
const STEPS: Step[] = ['pain', 'experience', 'hours'];

const STEP_LABELS: Record<Step, string> = {
  pain: 'Цель',
  experience: 'Опыт',
  hours: 'Время',
};

const DEFAULT_SKIP_PROFILE = {
  experience_level: '1–3 года',
  pain_point: 'рост' as OnboardingPainPoint,
  development_hours_per_week: 4,
};

export default function OnboardingQuiz({
  initialExperience,
  initialPainPoint,
  initialHours,
  onBack,
  compactFromWizard = false,
  onComplete,
}: Props) {
  const { user, refreshMe } = useAuth();
  const [currentStep, setCurrentStep] = useState<Step>('pain');
  const [painPoint, setPainPoint] = useState<OnboardingPainPoint | ''>(
    initialPainPoint && ['рост', 'смена', 'стагнация', 'неопределённость'].includes(initialPainPoint)
      ? (initialPainPoint as OnboardingPainPoint)
      : user?.pain_point && ['рост', 'смена', 'стагнация', 'неопределённость'].includes(user.pain_point)
        ? (user.pain_point as OnboardingPainPoint)
      : '',
  );
  const [experience, setExperience] = useState(initialExperience || user?.experience_level || '');
  const [hours, setHours] = useState<number>(initialHours || user?.development_hours_per_week || 4);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const stepIndex = STEPS.indexOf(currentStep);
  const progress = ((stepIndex + 1) / STEPS.length) * 100;

  const canProceed = useMemo(() => {
    switch (currentStep) {
      case 'pain': return Boolean(painPoint);
      case 'experience': return Boolean(experience.trim());
      case 'hours': return hours > 0;
      default: return false;
    }
  }, [currentStep, painPoint, experience, hours]);

  const canSubmit = useMemo(
    () => Boolean(experience.trim() && painPoint && hours > 0),
    [experience, painPoint, hours],
  );

  const goNext = () => {
    const idx = STEPS.indexOf(currentStep);
    if (idx < STEPS.length - 1) setCurrentStep(STEPS[idx + 1]);
  };

  const goPrev = () => {
    const idx = STEPS.indexOf(currentStep);
    if (idx > 0) setCurrentStep(STEPS[idx - 1]);
  };

  const submit = async () => {
    if (!canSubmit || !painPoint) {
      setError('Пожалуйста, ответьте на все вопросы.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const result = await saveOnboarding({
        experience_level: experience.trim(),
        pain_point: painPoint,
        development_hours_per_week: hours,
      });
      await refreshMe();
      showToast('Профиль сохранен. Рекомендации обновлены.');
      const recommendedScenario = deriveScenarioRecommendation(painPoint);
      onComplete({
        recommendedScenario: result.recommended_scenario || recommendedScenario,
        painPoint,
        developmentHoursPerWeek: hours,
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Не удалось сохранить ответы';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  const skipToPlanWithDefaults = async () => {
    if (!compactFromWizard) return;
    setSaving(true);
    setError('');
    try {
      const result = await saveOnboarding(DEFAULT_SKIP_PROFILE);
      await refreshMe();
      showToast('Профиль можно донастроить позже в кабинете.');
      const recommendedScenario = deriveScenarioRecommendation(DEFAULT_SKIP_PROFILE.pain_point);
      onComplete({
        recommendedScenario: result.recommended_scenario || recommendedScenario,
        painPoint: DEFAULT_SKIP_PROFILE.pain_point,
        developmentHoursPerWeek: DEFAULT_SKIP_PROFILE.development_hours_per_week,
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Не удалось сохранить профиль';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  const isLastStep = currentStep === 'hours';

  return (
    <Layout step={0} showStepper={false}>
      <div className="mx-auto max-w-2xl slide-up">
        {/* Header */}
        <div className="mb-8 text-center">
          <Eyebrow className="mb-3 inline-flex items-center gap-2 rounded-full bg-[var(--chip)] px-4 py-1.5">
            <Sparkles className="h-3.5 w-3.5" />
            Шаг {stepIndex + 1} из {STEPS.length}
          </Eyebrow>
          <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)] md:text-4xl">
            Настроим ваш профиль
          </h1>
          {compactFromWizard && (
            <div className="mx-auto mt-4 max-w-md space-y-3 rounded-xl border border-[var(--line)] bg-[var(--chip)]/60 px-4 py-3 text-left">
              <p className="text-sm text-[var(--muted)] leading-relaxed">
                План уже сформирован — эти ответы помогают персонализировать кабинет и прогнозы.
                Их можно изменить позже в настройках профиля.
              </p>
              <Button variant="secondary" className="w-full" onClick={skipToPlanWithDefaults} disabled={saving}>
                {saving ? 'Сохраняем…' : 'Открыть мой план →'}
              </Button>
            </div>
          )}
        </div>

        {/* Progress bar */}
        <div className="mb-8">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--line)]">
            <div
              className="h-full rounded-full bg-[var(--blue-deep)] transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {error && (
          <div className="mb-6">
            <Alert variant="error" onClose={() => setError('')}>
              {error}
            </Alert>
          </div>
        )}

        {/* Step content */}
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-6 shadow-[var(--shadow-soft)] md:p-8">
          {currentStep === 'pain' && (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--chip)]">
                  <HelpCircle className="h-5 w-5 text-[var(--blue-deep)]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[var(--ink)]">Какая у вас сейчас главная карьерная цель?</h2>
                  <p className="text-sm text-[var(--muted)]">От этого будет зависеть ваш персональный роадмап.</p>
                </div>
              </div>
              <div className="grid gap-3">
                {PAIN_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setPainPoint(option.value)}
                    className={`flex items-start gap-4 rounded-xl border p-4 text-left transition-all duration-200 ${
                      painPoint === option.value
                        ? 'border-[var(--blue-deep)] bg-[var(--chip)] shadow-[0_0_0_1px_var(--blue-deep)]'
                        : 'border-[var(--line)] hover:border-[var(--blue-deep)]/40'
                    }`}
                  >
                    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors ${
                      painPoint === option.value ? 'bg-[var(--blue-deep)] text-white' : 'bg-[var(--chip)]'
                    }`}>
                      <HelpCircle className={`h-4 w-4 ${painPoint === option.value ? 'text-white' : 'text-[var(--blue-deep)]'}`} />
                    </div>
                    <div className="flex-1">
                      <p className={`text-sm font-medium ${
                        painPoint === option.value ? 'text-[var(--blue-deep)]' : 'text-[var(--ink)]'
                      }`}>
                        {option.label}
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--muted)]">{option.sub}</p>
                    </div>
                    {painPoint === option.value && (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[var(--blue-deep)]" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {currentStep === 'experience' && (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--chip)]">
                  <Briefcase className="h-5 w-5 text-[var(--blue-deep)]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[var(--ink)]">Сколько лет опыта работы?</h2>
                  <p className="text-sm text-[var(--muted)]">Выберите наиболее подходящий вариант</p>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {EXPERIENCE_OPTIONS.map((option) => (
                  <button
                    key={option}
                    onClick={() => setExperience(option)}
                    className={`flex items-center gap-3 rounded-xl border p-4 text-left transition-all duration-200 ${
                      experience === option
                        ? 'border-[var(--blue-deep)] bg-[var(--chip)] shadow-[0_0_0_1px_var(--blue-deep)]'
                        : 'border-[var(--line)] hover:border-[var(--blue-deep)]/40'
                    }`}
                  >
                    <span className={`text-sm font-medium ${
                      experience === option ? 'text-[var(--blue-deep)]' : 'text-[var(--ink)]'
                    }`}>
                      {option}
                    </span>
                    {experience === option && (
                      <CheckCircle2 className="ml-auto h-4 w-4 text-[var(--blue-deep)]" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {currentStep === 'hours' && (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--chip)]">
                  <Clock className="h-5 w-5 text-[var(--blue-deep)]" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-[var(--ink)]">Сколько часов в неделю готовы уделять развитию?</h2>
                  <p className="text-sm text-[var(--muted)]">Это повлияет на темп вашего плана</p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {HOURS_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setHours(option.value)}
                    className={`flex items-center gap-3 rounded-xl border p-4 text-left transition-all duration-200 ${
                      hours === option.value
                        ? 'border-[var(--blue-deep)] bg-[var(--chip)] shadow-[0_0_0_1px_var(--blue-deep)]'
                        : 'border-[var(--line)] hover:border-[var(--blue-deep)]/40'
                    }`}
                  >
                    <span className={`text-sm font-medium ${
                      hours === option.value ? 'text-[var(--blue-deep)]' : 'text-[var(--ink)]'
                    }`}>
                      {option.label}
                    </span>
                    {hours === option.value && (
                      <CheckCircle2 className="ml-auto h-4 w-4 text-[var(--blue-deep)]" />
                    )}
                  </button>
                ))}
              </div>

              <div className="rounded-xl bg-[var(--chip)] p-4">
                <p className="text-sm text-[var(--color-text-secondary)]">
                  На основе ваших ответов мы автоматически предложим сценарий развития.
                  Вы всегда сможете его изменить.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="mt-6 flex items-center justify-between">
          <div>
            {stepIndex > 0 ? (
              <Button variant="ghost" onClick={goPrev}>
                <ArrowLeft className="h-4 w-4" />
                Назад
              </Button>
            ) : onBack ? (
              <Button variant="ghost" onClick={onBack}>
                <ArrowLeft className="h-4 w-4" />
                Назад
              </Button>
            ) : (
              <div />
            )}
          </div>

          {isLastStep ? (
            <Button onClick={submit} disabled={!canSubmit || saving}>
              {saving ? 'Сохраняем...' : 'Завершить настройку'}
              {!saving && <CheckCircle2 className="h-4 w-4" />}
            </Button>
          ) : (
            <Button onClick={goNext} disabled={!canProceed}>
              Далее
              <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Upcoming steps hint */}
        <div className="mt-6 flex items-center justify-center gap-2">
          {STEPS.map((step, i) => (
            <span
              key={step}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                i === stepIndex
                  ? 'bg-[var(--blue-deep)] text-white'
                  : i < stepIndex
                    ? 'bg-[var(--chip)] text-[var(--blue-deep)]'
                    : 'bg-[var(--chip)] text-[var(--muted)]'
              }`}
            >
              {STEP_LABELS[step]}
            </span>
          ))}
        </div>
      </div>
    </Layout>
  );
}
