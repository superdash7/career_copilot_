import { useState, useMemo, useEffect } from 'react';
import { ArrowRight, RefreshCw, Loader2 } from 'lucide-react';
import Layout from '../components/Layout';
import { buildFocusedPlan, fetchSkillsForRole, ApiError } from '../api/client';
import { showToast } from '../components/toastStore';
import type {
  PlanResponse, ExploreAnalysis,
  AppState, FocusedPlan,
} from '../types';
import Button from '../components/ui/Button';
import Eyebrow from '../components/ui/Eyebrow';
import FocusedPlanSection from '../components/FocusedPlanSection';

interface Props {
  plan: PlanResponse;
  appState: AppState;
  isAuthenticated?: boolean;
  onSoftGate?: () => void;
  onOpenOnboarding?: () => void;
  onReset: () => void;
  onBackToSkills: () => void;
  onOpenDashboard: () => void;
  onOpenShare: (analysisId: string) => void;
}

const EXPLORE_MIN_SKILLS = 4;
const EXPLORE_MAX_SKILLS = 10;


export default function Result({
  plan, appState, isAuthenticated = true, onSoftGate, onReset,
  onBackToSkills, onOpenDashboard, onOpenShare,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [sharing, setSharing] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(plan.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleShare = async () => {
    if (!plan.analysis_id || sharing) {
      showToast('Сначала сохраните анализ');
      return;
    }
    setSharing(true);
    try {
      const shareUrl = `${window.location.origin}${window.location.pathname}#share/${plan.analysis_id}`;
      await navigator.clipboard.writeText(shareUrl);
      showToast('Ссылка скопирована');
      onOpenShare(plan.analysis_id);
    } catch { showToast('Не удалось скопировать ссылку'); }
    finally { setSharing(false); }
  };

  return (
    <Layout step={3} wide>
      <div className="space-y-6 slide-up">
        {/* Header actions */}
        <div className="flex flex-wrap justify-end gap-2">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={onReset}>Заново</Button>
            <Button variant="secondary" onClick={handleShare} disabled={!plan.analysis_id || sharing}>
              {sharing ? 'Копируем...' : 'Поделиться'}
            </Button>
            <Button variant="secondary" onClick={handleCopy}>
              {copied ? 'Скопировано' : 'Скопировать'}
            </Button>
          </div>
        </div>

        {/* Main content */}
        {/* Explore: full width, no sidebar */}
        {plan.analysis?.scenario === 'explore' && (
          <ExploreView data={plan.analysis} appState={appState} onBackToSkills={onBackToSkills} />
        )}

        {/* Growth / Switch now handled by dedicated GrowthPage / SwitchPage */}

        {/* Footer */}
        {!isAuthenticated && onSoftGate && (
          <div className="card border-(--color-border) bg-[var(--chip)]">
            <h3 className="text-lg font-semibold text-(--color-text-primary)">
              Сохранить результат и получить полный план
            </h3>
            <p className="mt-2 text-sm text-(--color-text-secondary)">
              Создайте аккаунт, чтобы сохранить историю и открыть трекинг прогресса.
            </p>
            <div className="mt-4">
              <Button onClick={onSoftGate}>Создать аккаунт и сохранить</Button>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-3 pt-2">
          <Button variant="secondary" onClick={onBackToSkills}>← Уточнить навыки</Button>
          {isAuthenticated && (
            <Button variant="secondary" onClick={onOpenDashboard}>Личный кабинет</Button>
          )}
        </div>
      </div>
    </Layout>
  );
}


// ======================== FOCUSED PLAN ========================

// ======================== EXPLORE ========================

const ROLE_STYLES = {
  closest: {
    card: 'bg-[var(--chip)] border-[var(--blue-deep)]/30',
    category: 'text-[var(--blue-deep)]',
    bar: 'bg-[var(--blue-deep)]',
    chip: 'bg-[var(--blue-deep)]/10 text-[var(--blue-deep)]',
    dot: 'bg-[var(--blue-deep)]',
  },
  adjacent: {
    card: 'bg-[#E1F5EE] border-[#1D9E75]/30',
    category: 'text-[#1D9E75]',
    bar: 'bg-[#1D9E75]',
    chip: 'bg-[#1D9E75]/10 text-[#1D9E75]',
    dot: 'bg-[#1D9E75]',
  },
};

type ExploreFilter = 'all' | 'closest' | 'adjacent';

function ExploreView({ data, appState, onBackToSkills }: {
  data: ExploreAnalysis;
  appState: AppState;
  onBackToSkills: () => void;
}) {
  const [filter, setFilter] = useState<ExploreFilter>('all');
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [selectedMissingSkills, setSelectedMissingSkills] = useState<Set<string>>(new Set());
  const [roleMissingSkills, setRoleMissingSkills] = useState<string[] | null>(null);
  const [roleSkillsLoading, setRoleSkillsLoading] = useState(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState('');
  const [focusedPlan, setFocusedPlan] = useState<FocusedPlan | null>(null);

  const filtered = filter === 'all' ? data.roles : data.roles.filter(r => r.category === filter);
  const selectedRole = selectedIdx !== null ? data.roles[selectedIdx] : null;
  const userSkillsSet = useMemo(
    () => new Set(appState.skills.map((s) => s.name.trim().toLowerCase())),
    [appState.skills],
  );
  const missingSkillsForRole = selectedRole
    ? (roleMissingSkills ?? selectedRole.missing)
    : [];

  const selectedSkillsList = Array.from(selectedMissingSkills);

  const toggleMissingSkill = (skill: string) => {
    setSelectedMissingSkills((prev) => {
      const next = new Set(prev);
      if (next.has(skill)) {
        next.delete(skill);
        return next;
      }
      if (next.size >= EXPLORE_MAX_SKILLS) {
        return prev;
      }
      next.add(skill);
      return next;
    });
  };

  const handleSelectRole = (idx: number | null) => {
    setSelectedIdx(idx);
    setSelectedMissingSkills(new Set());
    setRoleMissingSkills(null);
    setRoleSkillsLoading(false);
    setPlanError('');
    setFocusedPlan(null);
  };

  useEffect(() => {
    if (!selectedRole) {
      setRoleMissingSkills(null);
      setRoleSkillsLoading(false);
      return;
    }
    let cancelled = false;
    setRoleSkillsLoading(true);
    setRoleMissingSkills([]);
    fetchSkillsForRole(selectedRole.title)
      .then((roleSkills) => {
        if (cancelled) return;
        const uniqueRoleSkills = Array.from(
          new Set(roleSkills.map((s) => s.trim()).filter(Boolean)),
        );
        const missing = uniqueRoleSkills.filter(
          (skill) => !userSkillsSet.has(skill.toLowerCase()),
        );
        setRoleMissingSkills(missing);
      })
      .catch(() => {
        if (!cancelled) {
          // Fallback to analysis payload if role skills can't be loaded.
          setRoleMissingSkills(selectedRole.missing);
        }
      })
      .finally(() => {
        if (!cancelled) setRoleSkillsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRole, userSkillsSet]);

  const handleGenerateRolePlan = async () => {
    if (!selectedRole) return;
    if (selectedSkillsList.length < EXPLORE_MIN_SKILLS || selectedSkillsList.length > EXPLORE_MAX_SKILLS) {
      setPlanError(`Выберите от ${EXPLORE_MIN_SKILLS} до ${EXPLORE_MAX_SKILLS} навыков для генерации плана`);
      return;
    }
    setPlanLoading(true);
    setPlanError('');
    try {
      const result = await buildFocusedPlan({
        profession: appState.profession,
        grade: appState.grade,
        scenario: 'Исследование возможностей',
        target_profession: selectedRole.title,
        selected_skills: selectedSkillsList,
      });
      setFocusedPlan(result);
    } catch (err) {
      setPlanError(err instanceof ApiError ? err.message : 'Не удалось сформировать план');
    } finally {
      setPlanLoading(false);
    }
  };

  const FILTERS: Array<{ key: ExploreFilter; label: string }> = [
    { key: 'all', label: 'Все' },
    { key: 'closest', label: 'Ближайшие' },
    { key: 'adjacent', label: 'Смежные' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Eyebrow className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-[var(--chip)] px-3 py-1">
            ✦ Исследование возможностей
          </Eyebrow>
          <h2 className="mt-2 text-2xl font-bold text-[var(--ink)] sm:text-3xl">
            Направления развития
          </h2>
        </div>
        <Button variant="secondary" onClick={onBackToSkills}>
          <RefreshCw className="h-4 w-4" />
          Обновить профиль
        </Button>
      </div>

      {/* Profile chip */}
      {appState.skills.length > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-[var(--line)] bg-[var(--bg)] p-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--blue-deep)] text-xs font-semibold text-white">
            {(appState.profession || 'U')[0]}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[var(--ink)] truncate">{appState.profession || 'Не указано'}</p>
            <p className="text-xs text-[var(--muted)] truncate">{appState.grade}</p>
          </div>
          <div className="hidden flex-wrap gap-1 sm:flex">
            {appState.skills.slice(0, 4).map(s => (
              <span key={s.name} className="rounded-full border border-[var(--line)] bg-[var(--paper)] px-2.5 py-0.5 text-xs text-[var(--muted)]">{s.name}</span>
            ))}
            {appState.skills.length > 4 && (
              <span className="rounded-full border border-[var(--line)] bg-[var(--paper)] px-2.5 py-0.5 text-xs text-[var(--muted)]">+{appState.skills.length - 4}</span>
            )}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--muted)]">Показать:</span>
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => { setFilter(f.key); setSelectedIdx(null); }}
            className={`rounded-full border px-4 py-1.5 text-xs font-medium transition-all ${
              filter === f.key
                ? 'border-[var(--ink)] bg-[var(--ink)] text-white'
                : 'border-[var(--line)] text-[var(--muted)] hover:bg-[var(--chip)]'
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-[var(--muted)]">{filtered.length} ролей</span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5">
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-full bg-[var(--blue-deep)]" />
          <span className="text-xs text-[var(--muted)]">Ближайшие — переход до 6 мес.</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-full bg-[#1D9E75]" />
          <span className="text-xs text-[var(--muted)]">Смежные — 6–12 мес.</span>
        </div>
      </div>

      {/* Detail panel */}
      {selectedRole && (
        <div className="rounded-2xl border border-[var(--line)] bg-[var(--bg)] p-5">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-xl font-bold text-[var(--ink)]">{selectedRole.title}</h3>
              <p className="mt-1 text-sm text-[var(--muted)]">{selectedRole.match_label}</p>
            </div>
            <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
              selectedRole.category === 'closest' ? 'bg-[var(--chip)] text-[var(--blue-deep)]' : 'bg-[#E1F5EE] text-[#1D9E75]'
            }`}>
              {selectedRole.category === 'closest' ? 'Ближайшая' : 'Смежная'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2.5 mb-4">
            <div className="rounded-xl border border-[var(--line)] bg-[var(--paper)] p-3 text-center">
              <span className="block text-xl font-bold text-[var(--blue-deep)]">{selectedRole.match}%</span>
              <span className="text-xs text-[var(--muted)]">Готовность к переходу</span>
            </div>
            <div className="rounded-xl border border-[var(--line)] bg-[var(--paper)] p-3 text-center">
              <span className="block text-xl font-bold text-[var(--ink)]">{missingSkillsForRole.length}</span>
              <span className="text-xs text-[var(--muted)]">Навыков развить</span>
            </div>
          </div>

          {selectedRole.key_skills.length > 0 && (
            <div className="mb-4">
              <p className="mb-2 text-xs font-medium text-[var(--muted)] uppercase tracking-wider">Имеющиеся навыки</p>
              <div className="flex flex-wrap gap-1.5">
                {selectedRole.key_skills.map(sk => (
                  <span key={sk} className="rounded-full border border-[var(--line)] bg-[var(--paper)] px-3 py-1 text-xs text-[var(--ink)]">{sk}</span>
                ))}
              </div>
            </div>
          )}

          {(roleSkillsLoading || missingSkillsForRole.length > 0) && (
            <div className="mb-5">
              <p className="mb-2 text-xs font-medium text-[var(--muted)] uppercase tracking-wider">
                Нужно освоить (выберите от {EXPLORE_MIN_SKILLS} до {EXPLORE_MAX_SKILLS} навыков)
              </p>
              {roleSkillsLoading ? (
                <p className="inline-flex items-center gap-2 text-xs text-[var(--muted)]">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Загружаем навыки профессии...
                </p>
              ) : (
                <>
                  <div className="flex flex-wrap gap-1.5">
                    {missingSkillsForRole.map((sk) => {
                      const isSelected = selectedMissingSkills.has(sk);
                      return (
                        <button
                          key={sk}
                          type="button"
                          onClick={() => toggleMissingSkill(sk)}
                          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                            isSelected
                              ? 'bg-[var(--blue-deep)] text-white'
                              : selectedRole.category === 'closest'
                                ? 'bg-[var(--blue-deep)]/10 text-[var(--blue-deep)]'
                                : 'bg-[#1D9E75]/10 text-[#1D9E75]'
                          }`}
                        >
                          {sk}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Выбрано: {selectedSkillsList.length} (нужно от {EXPLORE_MIN_SKILLS} до {EXPLORE_MAX_SKILLS})
                  </p>
                </>
              )}
            </div>
          )}

          <div className="flex gap-2">
            <Button
              onClick={handleGenerateRolePlan}
              className="flex-1"
              disabled={
                planLoading
                || selectedSkillsList.length < EXPLORE_MIN_SKILLS
                || selectedSkillsList.length > EXPLORE_MAX_SKILLS
              }
            >
              {planLoading ? (
                <>Генерируем...</>
              ) : (
                <>Составить план развития <ArrowRight className="h-4 w-4" /></>
              )}
            </Button>
            <Button variant="secondary" onClick={() => setSelectedIdx(null)}>
              Закрыть
            </Button>
          </div>
          {planError && <p className="mt-2 text-xs text-red-500">{planError}</p>}
          {focusedPlan && (
            <div className="mt-5 border-t border-[var(--line)] pt-5">
              <FocusedPlanSection plan={focusedPlan} />
            </div>
          )}
        </div>
      )}

      {/* Role grid */}
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((role, idx) => {
          const globalIdx = data.roles.indexOf(role);
          const s = ROLE_STYLES[role.category] || ROLE_STYLES.adjacent;
          const isSelected = selectedIdx === globalIdx;

          return (
            <div
              key={idx}
              onClick={() => handleSelectRole(isSelected ? null : globalIdx)}
              className={`h-full cursor-pointer rounded-2xl border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${s.card} flex flex-col ${
                isSelected ? 'ring-2 ring-[var(--blue-deep)]/20' : ''
              }`}
            >
              <p className={`text-[10px] font-medium uppercase tracking-widest mb-2 ${s.category}`}>
                {role.category === 'closest' ? 'Ближайшая' : 'Смежная'}
              </p>
              <h3 className="text-[15px] font-semibold leading-snug text-[var(--ink)] mb-1.5">{role.title}</h3>

              <p className="mb-3 line-clamp-3 text-[11px] leading-relaxed text-[var(--muted)]">
                {role.summary || role.reasons.slice(0, 3).join(', ')}
              </p>

              <div className="mt-auto flex items-center gap-2">
                <div className="flex-1">
                  <p className="text-[10px] text-[var(--muted)] mb-1">Готовность к переходу</p>
                  <div className="h-1 overflow-hidden rounded-full bg-black/10">
                    <div className={`h-full rounded-full transition-all duration-700 ${s.bar}`} style={{ width: `${role.match}%` }} />
                  </div>
                </div>
                <span className={`text-sm font-semibold ${s.category}`}>{role.match}%</span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-center text-xs text-[var(--muted)]">
        Нажмите на роль, чтобы увидеть детали перехода
      </p>
    </div>
  );
}


