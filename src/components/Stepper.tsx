import { Check } from 'lucide-react';

const STEPS = ['Цель', 'Навыки', 'Анализ', 'План'];

interface Props {
  current: number;
}

export default function Stepper({ current }: Props) {
  return (
    <nav className="flex items-center justify-center gap-1.5 pb-3 pt-1 sm:gap-2">
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={i} className="flex items-center gap-1.5 sm:gap-2">
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={`
                  flex h-7 w-7 items-center justify-center rounded-lg text-[11px] font-medium
                  transition-all duration-300
                  ${done ? 'border border-[var(--blue-deep)] bg-[var(--blue-deep)] text-white' : ''}
                  ${active ? 'border border-[var(--blue-deep)] bg-[var(--blue-deep)] text-white ring-4 ring-[color-mix(in_srgb,var(--blue-deep)_15%,transparent)]' : ''}
                  ${!done && !active ? 'border border-[var(--line)] bg-[var(--paper)] text-[var(--muted)]' : ''}
                `}
              >
                {done ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : i + 1}
              </div>
              <span
                className={`hidden text-[10px] font-medium sm:block ${
                  active ? 'text-[var(--blue-deep)]' : done ? 'text-[var(--blue-deep)]' : 'text-[var(--muted)]'
                }`}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`h-px w-4 rounded transition-colors duration-300 sm:w-7 ${
                  i < current ? 'bg-[var(--blue-deep)]' : 'bg-[var(--line)]'
                }`}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
