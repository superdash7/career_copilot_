import { useState, useCallback, useEffect, useRef, type KeyboardEvent } from 'react';
import { useDropzone } from 'react-dropzone';
import Layout from '../components/Layout';
import Alert from '../components/Alert';
import SkillCard from '../components/SkillCard';
import SkillConfidenceBadge from '../components/SkillConfidenceBadge';
import SkillAlternativeSelect from '../components/SkillAlternativeSelect';
import ProgressLoader from '../components/ProgressLoader';
import MiniProgress from '../components/MiniProgress';
import SoftOnboardingHint from '../components/SoftOnboardingHint';
import { showToast } from '../components/toastStore';
import { analyzeResume, suggestSkills, fetchSkillsForRole, fetchSkillsByCategoryForRole } from '../api/client';
import { ApiError } from '../api/client';
import type { AppState, Skill } from '../types';
import Button from '../components/ui/Button';

interface Props {
  state: AppState;
  onChange: (patch: Partial<AppState>) => void;
  onNext: () => void;
  onBack: () => void;
}

const RECOMMENDED_VISIBLE = 6;
// Removed InputMode — single unified flow
interface SkillCategoryGroup {
  name: string;
  skills: string[];
}

function SkillQualityBar({ count }: { count: number }) {
  const pct = Math.min(count / 7, 1) * 100;
  const color =
    count === 0 ? 'bg-(--color-border)'
    : count < 3 ? 'bg-red-400'
    : count < 5 ? 'bg-amber-400'
    : 'bg-emerald-400';
  const label =
    count === 0 ? 'Добавьте навыки для точного анализа профиля'
    : count < 3 ? 'Маловато — добавьте еще для точности'
    : count < 5 ? 'Хорошо, можно добавить еще'
    : count < 7 ? 'Отлично!'
    : 'Превосходно!';
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-(--color-text-muted)">{label}</span>
        <span className="text-(--color-text-muted) font-medium">{count} навык(ов)</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-(--color-border)/50 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function Skills({ state, onChange, onNext, onBack }: Props) {
  // Input mode removed — single unified flow
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploadError, setUploadError] = useState<{ title: string; text: string } | null>(null);
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [roleSkills, setRoleSkills] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [highlightedIdx, setHighlightedIdx] = useState(-1);
  const [newSkillNames, setNewSkillNames] = useState<Set<string>>(new Set());
  const [showAllRecommended, setShowAllRecommended] = useState(false);
  const [skillCategories, setSkillCategories] = useState<SkillCategoryGroup[]>([]);
  const suggestRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suggestAbortRef = useRef<AbortController | null>(null);
  const roleAbortRef = useRef<AbortController | null>(null);
  const categoryAbortRef = useRef<AbortController | null>(null);

  const skills = state.skills;
  const setSkills = useCallback((s: Skill[]) => onChange({ skills: s }), [onChange]);

  const hasConfidenceMetadata = skills.some((s) => typeof s.confidence === 'number');

  useEffect(() => {
    if (state.profession) {
      roleAbortRef.current?.abort();
      roleAbortRef.current = new AbortController();
      fetchSkillsForRole(state.profession, roleAbortRef.current.signal)
        .then(setRoleSkills)
        .catch(() => {});

      categoryAbortRef.current?.abort();
      categoryAbortRef.current = new AbortController();
      fetchSkillsByCategoryForRole(state.profession, categoryAbortRef.current.signal)
        .then(setSkillCategories)
        .catch(() => setSkillCategories([]));
    }
    return () => {
      roleAbortRef.current?.abort();
      categoryAbortRef.current?.abort();
    };
  }, [state.profession]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (suggestRef.current && !suggestRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Clear highlight from new skills after 3s
  useEffect(() => {
    if (newSkillNames.size === 0) return;
    const t = setTimeout(() => setNewSkillNames(new Set()), 3000);
    return () => clearTimeout(t);
  }, [newSkillNames]);

  const addSkill = useCallback(
    (name: string, level: number = 1) => {
      const trimmed = name.trim();
      if (!trimmed) return;
      if (skills.some((s) => s.name.toLowerCase() === trimmed.toLowerCase())) return;
      setSkills([...skills, { name: trimmed, level }]);
      setNewSkillNames((prev) => new Set(prev).add(trimmed.toLowerCase()));
      setQuery('');
      setSuggestions([]);
      setShowSuggestions(false);
      setHighlightedIdx(-1);
    },
    [skills, setSkills],
  );

  const removeSkill = useCallback(
    (index: number) => {
      const removed = skills[index];
      const next = skills.filter((_, j) => j !== index);
      setSkills(next);
      showToast(`Навык «${removed.name}» удален`, {
        label: 'Отменить',
        onClick: () => setSkills([...next.slice(0, index), removed, ...next.slice(index)]),
      });
    },
    [skills, setSkills],
  );

  const applyAlternative = useCallback(
    (index: number, altName: string) => {
      const current = skills[index];
      if (!current) return;
      const next = [...skills];

      // Если альтернатива уже есть в списке — не дублируем, только удаляем текущую запись.
      if (skills.some((s, i) => i !== index && s.name.toLowerCase() === altName.toLowerCase())) {
        next.splice(index, 1);
        setSkills(next);
        showToast(`Навык заменён на «${altName}» (дубликат объединён)`);
        return;
      }

      next[index] = {
        ...current,
        name: altName,
        confidence: 0.95,
        confidence_band: 'vector_llm',
      };
      setSkills(next);
      showToast(`Навык заменён на «${altName}»`);
    },
    [skills, setSkills],
  );

  const handleQueryChange = (val: string) => {
    setQuery(val);
    setHighlightedIdx(-1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    suggestAbortRef.current?.abort();
    if (val.trim().length >= 2) {
      debounceRef.current = setTimeout(() => {
        suggestAbortRef.current = new AbortController();
        suggestSkills(val, suggestAbortRef.current.signal)
          .then((s) => {
            setSuggestions(s);
            setShowSuggestions(s.length > 0);
          })
          .catch(() => {});
      }, 250);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter' && query.trim()) {
        e.preventDefault();
        addSkill(query);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIdx((h) => Math.min(h + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIdx((h) => Math.max(h - 1, -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightedIdx >= 0 && suggestions[highlightedIdx]) {
        addSkill(suggestions[highlightedIdx]);
      } else if (query.trim()) {
        addSkill(query);
      }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setHighlightedIdx(-1);
    }
  };

  const onDrop = useCallback(
    async (files: File[]) => {
      const file = files[0];
      if (!file) return;
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        setUploadError({ title: 'Неверный формат', text: 'Загрузите файл в формате PDF.' });
        return;
      }
      setUploading(true);
      setUploadError(null);
      setUploadMsg('');
      try {
        const result = await analyzeResume(file);
        if (result.skills.length === 0) {
          setUploadMsg('Не удалось найти навыки. Попробуйте другой файл или добавьте вручную.');
        } else {
          const newSkills = [...skills];
          const addedNames = new Set<string>();
          for (const s of result.skills) {
            if (!newSkills.some((x) => x.name.toLowerCase() === s.name.toLowerCase())) {
              newSkills.push(s);
              addedNames.add(s.name.toLowerCase());
            }
          }
          setSkills(newSkills);
          setNewSkillNames(addedNames);
          setUploadMsg(`Добавлено ${addedNames.size} из ${result.skills.length} найденных навыков`);
        }
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 400) {
            setUploadError({ title: 'Неверный формат', text: 'Загрузите файл в формате PDF.' });
          } else if (err.status === 503) {
            setUploadError({
              title: 'Автоматический разбор временно недоступен',
              text: 'Добавьте навыки вручную.',
            });
          } else {
            setUploadError({ title: 'Ошибка', text: 'Проверьте соединение и попробуйте еще раз.' });
          }
        } else {
          setUploadError({ title: 'Ошибка', text: 'Проверьте соединение и попробуйте еще раз.' });
        }
      } finally {
        setUploading(false);
      }
    },
    [skills, setSkills],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: uploading,
  });

  const handleNext = () => {
    if (skills.length === 0) {
      setValidationError('Добавьте хотя бы один навык для анализа профиля.');
      return;
    }
    setValidationError('');
    onNext();
  };

  const existingNames = new Set(skills.map((s) => s.name.toLowerCase()));
  const filteredRoleSkills = roleSkills.filter((s) => !existingNames.has(s.toLowerCase()));
  const visibleRecommended = showAllRecommended
    ? filteredRoleSkills
    : filteredRoleSkills.slice(0, RECOMMENDED_VISIBLE);

  return (
    <Layout step={1}>
      <div className="space-y-8 slide-up">
        <div>
          <MiniProgress current={2} total={4} label="Навыки" />
          <h1 className="mt-2 mb-2 text-3xl leading-tight text-(--color-text-primary) sm:text-4xl">
            Ваши навыки
          </h1>
          <p className="text-(--color-text-secondary)">
            Добавьте навыки — загрузите резюме или введите вручную. Можно добавить свои навыки, которых нет в подсказках.
          </p>
        </div>

        <SoftOnboardingHint id="skills_intro">
          Это ключевой шаг — чем точнее данные, тем точнее анализ профиля и план на следующих шагах.
        </SoftOnboardingHint>

        {validationError && (
          <Alert variant="warning" onClose={() => setValidationError('')}>
            {validationError}
          </Alert>
        )}

        {/* Resume upload — always visible */}
        <div className="card space-y-4">
          <div>
            <h2 className="mb-1 text-xl text-(--color-text-primary)">Загрузите резюме</h2>
            <p className="text-sm text-(--color-text-muted)">PDF — мы извлечем навыки автоматически. Или добавьте вручную ниже.</p>
          </div>

            {uploading ? (
              <ProgressLoader text="Извлекаем навыки из резюме…" subtext="Обычно это занимает до минуты" durationMs={40000} />
            ) : (
              <div
                {...getRootProps()}
                className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-8 transition-all ${
                  isDragActive
                    ? 'border-[var(--blue-deep)] bg-[var(--chip)]'
                    : 'border-(--color-border) bg-(--color-surface-alt) hover:border-[var(--blue-deep)]/40 hover:bg-[var(--chip)]/60'
                }`}
              >
                <input {...getInputProps()} />
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-(--color-border) bg-(--color-surface-raised) text-[18px] text-(--color-text-muted)">
                  ⤴
                </span>
                <p className="text-sm text-(--color-text-secondary) text-center">
                  Перетащите PDF сюда или{' '}
                  <span className="font-medium text-[var(--blue-deep)]">выберите файл</span>
                </p>
              </div>
            )}

            {uploadMsg && !uploadError && (
              <Alert variant={uploadMsg.startsWith('Добавлено') ? 'success' : 'info'}>
                {uploadMsg}
              </Alert>
            )}

            {uploadError && (
              <Alert
                variant={uploadError.title.includes('недоступен') ? 'warning' : 'error'}
                title={uploadError.title}
                onClose={() => setUploadError(null)}
              >
                {uploadError.text}
              </Alert>
            )}
          </div>

        {/* Manual input — always visible */}
        <div className="card space-y-4">
          <div>
            <h2 className="mb-1 text-xl text-(--color-text-primary)">Добавьте вручную</h2>
            <p className="text-sm text-(--color-text-muted)">
              Введите название навыка или выберите из подсказок. Можно добавить свои навыки.
            </p>
          </div>

          <div className="relative" ref={suggestRef}>
            <div className="relative">
              <span
                aria-hidden
                className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-(--color-text-muted)"
              >
                ⌕
              </span>
              <input
                type="text"
                value={query}
                onChange={(e) => handleQueryChange(e.target.value)}
                onKeyDown={handleKeyDown}
                onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                placeholder="SQL, коммуникации, roadmap…"
                className="input-field pl-10 pr-12"
                role="combobox"
                aria-expanded={showSuggestions}
                aria-autocomplete="list"
              />
              {query.trim() && (
                <button
                  onClick={() => addSkill(query)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg bg-[var(--chip)] p-1.5 text-[var(--blue-deep)] transition-colors hover:bg-[var(--line)]/60"
                  title="Добавить"
                >
                  +
                </button>
              )}
            </div>

            {showSuggestions && suggestions.length > 0 && (
              <div
                className="absolute z-20 mt-1 max-h-60 w-full overflow-y-auto rounded-2xl border border-(--color-border) bg-(--color-surface-raised) shadow-lg"
                role="listbox"
                aria-live="polite"
              >
                {suggestions.map((s, i) => (
                  <button
                    key={s}
                    onClick={() => addSkill(s)}
                    role="option"
                    aria-selected={i === highlightedIdx}
                    className={`w-full text-left px-4 py-2.5 text-sm transition-colors first:rounded-t-2xl last:rounded-b-2xl ${
                      i === highlightedIdx
                        ? 'bg-[var(--chip)] font-medium text-[var(--blue-deep)]'
                        : 'text-(--color-text-secondary) hover:bg-[var(--chip)]'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {skillCategories.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs font-medium text-(--color-text-muted)">
                Выбор по категориям для «{state.profession}»:
              </p>
              {skillCategories.map((category) => {
                const available = category.skills.filter((skillName) => !existingNames.has(skillName.toLowerCase()));
                if (available.length === 0) return null;
                return (
                  <div key={category.name} className="space-y-2">
                    <p className="text-sm font-medium text-(--color-text-primary)">{category.name}</p>
                    <div className="flex flex-wrap gap-2">
                      {available.slice(0, 20).map((skillName) => (
                        <button
                          key={`${category.name}-${skillName}`}
                          onClick={() => addSkill(skillName)}
                          className="inline-flex items-center gap-1 rounded-full border border-(--color-border) bg-(--color-surface-raised) px-3 py-1.5 text-sm text-(--color-text-secondary) transition-colors hover:border-[var(--blue-deep)]/40 hover:bg-[var(--chip)]"
                        >
                          + {skillName}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {filteredRoleSkills.length > 0 && (
            <div>
              <p className="text-xs font-medium text-(--color-text-muted) mb-2">
                Рекомендуемые для «{state.profession}»:
              </p>
              <div className="flex flex-wrap gap-2">
                {visibleRecommended.map((s) => (
                  <button
                    key={s}
                    onClick={() => addSkill(s)}
                    className="inline-flex items-center gap-1 rounded-full border border-(--color-border) bg-(--color-surface-raised) px-3 py-1.5 text-sm text-(--color-text-secondary) transition-colors hover:border-[var(--blue-deep)]/40 hover:bg-[var(--chip)]"
                  >
                    + {s}
                  </button>
                ))}
              </div>
              {filteredRoleSkills.length > RECOMMENDED_VISIBLE && (
                <button
                  onClick={() => setShowAllRecommended(!showAllRecommended)}
                  className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-[var(--blue-deep)] transition-colors hover:text-[var(--color-accent-hover)]"
                >
                  {showAllRecommended ? (
                    <>Свернуть ▲</>
                  ) : (
                    <>Показать все ({filteredRoleSkills.length}) ▼</>
                  )}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Skill scale description */}
        <div className="card border-(--color-border) bg-[var(--chip)]">
          <p className="mb-3 text-sm font-semibold text-(--color-text-primary)">Шкала оценки навыков</p>
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-xs">
            <div className="rounded-lg bg-[var(--paper)] p-2.5 border border-(--color-border)">
              <span className="font-semibold text-(--color-text-primary)">0 — Нет навыка</span>
            </div>
            <div className="rounded-lg bg-[var(--paper)] p-2.5 border border-(--color-border)">
              <span className="font-semibold text-(--color-text-primary)">1 — Начальный</span>
              <p className="mt-0.5 text-(--color-text-muted)">знаю, но не умею</p>
            </div>
            <div className="rounded-lg bg-[var(--paper)] p-2.5 border border-(--color-border)">
              <span className="font-semibold text-(--color-text-primary)">2 — Базовый</span>
              <p className="mt-0.5 text-(--color-text-muted)">применяю в стандартных ситуациях</p>
            </div>
            <div className="rounded-lg bg-[var(--paper)] p-2.5 border border-(--color-border)">
              <span className="font-semibold text-(--color-text-primary)">3 — Продвинутый</span>
              <p className="mt-0.5 text-(--color-text-muted)">применяю в нестандартных ситуациях</p>
            </div>
            <div className="rounded-lg bg-[var(--paper)] p-2.5 border border-(--color-border)">
              <span className="font-semibold text-(--color-text-primary)">4 — Эксперт</span>
              <p className="mt-0.5 text-(--color-text-muted)">любая сложность, адаптируюсь под контекст</p>
            </div>
          </div>
        </div>

        {/* Selected skills */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-(--color-text-primary)">
            Выбранные навыки
            {skills.length > 0 && (
              <span className="ml-2 text-sm font-normal text-(--color-text-muted)">({skills.length})</span>
            )}
          </h2>

          <SkillQualityBar count={skills.length} />

          {hasConfidenceMetadata && (
            <Alert variant="info" title="Проверка распознавания навыков">
              Зелёный — распознано автоматически, жёлтый — подтвердите вариант, серый — низкая уверенность.
            </Alert>
          )}

          {skills.length === 0 ? (
            <div className="card flex flex-col items-center justify-center py-10 text-center">
              <span className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-full border border-(--color-border) text-lg text-(--color-text-muted)/60">
                ◎
              </span>
              <p className="text-sm text-(--color-text-muted)">
                Добавьте 3–7 навыков — это улучшит точность рекомендаций.
              </p>
            </div>
          ) : (
            <div className="space-y-2" aria-live="polite">
              {skills.map((skill, i) => (
                <div key={`${skill.name}-${i}`} className="space-y-2">
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <SkillConfidenceBadge skill={skill} />
                  </div>

                  <SkillCard
                    skill={skill}
                    isNew={newSkillNames.has(skill.name.toLowerCase())}
                    onChange={(updated) => {
                      const next = [...skills];
                      next[i] = updated;
                      setSkills(next);
                    }}
                    onRemove={() => removeSkill(i)}
                  />

                  {(skill.confidence ?? 0) > 0.6 && (skill.confidence ?? 0) <= 0.85 && (
                    <SkillAlternativeSelect
                      skill={skill}
                      onSelectAlternative={(altName: string) => applyAlternative(i, altName)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-2">
          <Button variant="secondary" onClick={onBack}>
            ← Назад
          </Button>
          <Button onClick={handleNext}>Продолжить →</Button>
        </div>
      </div>
    </Layout>
  );
}
