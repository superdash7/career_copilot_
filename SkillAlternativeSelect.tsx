import type { Skill } from '../types';

interface Props {
  skill: Skill;
  onSelectAlternative: (name: string) => void;
}

export default function SkillAlternativeSelect({ skill, onSelectAlternative }: Props) {
  const alternatives = (skill.alternatives || []).filter((a) => a.name && a.name !== skill.name).slice(0, 3);
  if (alternatives.length === 0) return null;

  return (
    <div className="mt-2 flex flex-col gap-1.5">
      <label className="font-[var(--font-mono)] text-[10px] uppercase tracking-[0.12em] text-[var(--muted)]">
        Подтвердите навык
      </label>
      <select
        className="rounded-xl border border-[var(--line)] bg-[color-mix(in_srgb,var(--paper)_90%,white)] px-3 py-2 text-sm text-[var(--ink)]"
        value=""
        onChange={(e) => {
          if (!e.target.value) return;
          onSelectAlternative(e.target.value);
        }}
      >
        <option value="">Выберите альтернативу</option>
        {alternatives.map((alt) => {
          const score = typeof alt.score === 'number' ? ` (${Math.round(alt.score * 100)}%)` : '';
          return (
            <option key={alt.name} value={alt.name}>
              {alt.name}{score}
            </option>
          );
        })}
      </select>
    </div>
  );
}
