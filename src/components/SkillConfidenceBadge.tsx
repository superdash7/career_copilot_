import type { Skill } from '../types';

interface Props {
  skill: Skill;
}

function getConfidenceLabel(skill: Skill): { text: string; cls: string } | null {
  const confidence = skill.confidence;
  if (confidence === undefined || confidence === null) return null;

  if (confidence > 0.85) {
    return {
      text: `Высокая уверенность (${Math.round(confidence * 100)}%) · авто`,
      cls: 'border-[var(--accent-green)]/30 bg-[color-mix(in_srgb,var(--accent-green)_14%,white)] text-[var(--accent-green)]',
    };
  }
  if (confidence >= 0.6) {
    return {
      text: `Средняя уверенность (${Math.round(confidence * 100)}%) · подтвердите`,
      cls: 'border-[#d2a441]/40 bg-[color-mix(in_srgb,#d2a441_16%,white)] text-[#8c6918]',
    };
  }
  return {
    text: `Низкая уверенность (${Math.round(confidence * 100)}%) · не распознано`,
    cls: 'border-[var(--line)] bg-[color-mix(in_srgb,var(--chip)_80%,white)] text-[var(--muted)]',
  };
}

export default function SkillConfidenceBadge({ skill }: Props) {
  const state = getConfidenceLabel(skill);
  if (!state) return null;

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-[var(--font-mono)] uppercase tracking-[0.1em] ${state.cls}`}>
      {state.text}
    </span>
  );
}

