import { CheckCircle2 } from 'lucide-react';
import type { Scenario } from '../types';

const SYMBOLS: Record<Scenario, string> = {
  'Следующий грейд': '↗',
  'Смена профессии': '⇄',
  'Исследование возможностей': '⌕',
};

interface Props {
  value: Scenario;
  label: string;
  description: string;
  selected: boolean;
  onSelect: () => void;
}

export default function ScenarioCard({ value, label, description, selected, onSelect }: Props) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`
        w-full text-left rounded-xl border p-5 transition-all duration-200 cursor-pointer
        ${selected
          ? 'border-[var(--blue-deep)] bg-[var(--chip)] shadow-[0_0_0_1px_var(--blue-deep)]'
          : 'border-[var(--line)] bg-[var(--paper)] hover:border-[var(--blue-deep)]/40'
        }
      `}
    >
      <div className="flex items-start gap-4">
        <div
          className={`shrink-0 mt-0.5 flex h-10 w-10 items-center justify-center rounded-xl text-sm transition-colors duration-200 ${
            selected
              ? 'bg-[var(--blue-deep)] text-white'
              : 'bg-[var(--chip)] text-[var(--blue-deep)]'
          }`}
        >
          {SYMBOLS[value]}
        </div>
        <div className="flex-1">
          <p className={`mb-1 font-semibold ${selected ? 'text-[var(--blue-deep)]' : 'text-[var(--ink)]'}`}>
            {label}
          </p>
          <p className="text-sm leading-relaxed text-[var(--muted)]">{description}</p>
        </div>
        {selected && (
          <CheckCircle2 className="mt-1 h-5 w-5 shrink-0 text-[var(--blue-deep)]" />
        )}
      </div>
    </button>
  );
}
