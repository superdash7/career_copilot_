import { Check } from 'lucide-react';

const STEPS = ['Старт', 'Цель', 'Навыки', 'Проверка', 'План'];

interface Props {
  current: number;
}

export default function Stepper({ current }: Props) {
  return (
    <nav className="flex items-center justify-center gap-1 sm:gap-2 pb-3">
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={i} className="flex items-center gap-1 sm:gap-2">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`
                  flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold
                  transition-all duration-300
                  ${done ? 'bg-(--color-accent) text-white' : ''}
                  ${active ? 'bg-(--color-accent) text-white ring-4 ring-(--color-accent)/20' : ''}
                  ${!done && !active ? 'bg-(--color-surface-alt) border border-(--color-border) text-(--color-text-muted)' : ''}
                `}
              >
                {done ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </div>
              <span
                className={`text-[11px] font-medium hidden sm:block ${
                  active ? 'text-(--color-accent)' : done ? 'text-(--color-accent)' : 'text-(--color-text-muted)'
                }`}
              >
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className={`h-px w-5 sm:w-8 rounded transition-colors duration-300 ${
                  i < current ? 'bg-(--color-accent)' : 'bg-(--color-border)'
                }`}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
