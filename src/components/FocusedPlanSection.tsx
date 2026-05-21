import { useState } from 'react';
import { Check } from 'lucide-react';
import MonoLabel from './ui/MonoLabel';
import type { FocusedPlan } from '../types';

interface Props {
  plan: FocusedPlan;
  title?: string;
}

export default function FocusedPlanSection({ plan, title = 'План развития' }: Props) {
  const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set());

  const toggleCheck = (id: string) => {
    setCheckedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <section className="border-t border-[var(--line)] pt-5 mt-5 space-y-4 fade-in">
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--muted)]">
        {title}
      </p>

      <div className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-5 shadow-[var(--shadow-soft)]">
        <MonoLabel>70%</MonoLabel>
        <h3 className="mt-3 mb-4 font-semibold text-[var(--ink)]">Задачи на развитие</h3>
        <div className="space-y-4">
          {plan.tasks.map((t) => (
            <div key={t.skill}>
              <p className="text-sm font-semibold text-[var(--blue-deep)] mb-2">{t.skill}</p>
              <ul className="space-y-2">
                {t.items.map((item, j) => {
                  const itemId = `${t.skill}::${j}`;
                  const done = checkedItems.has(itemId);
                  return (
                    <li key={itemId} className="flex items-start gap-3">
                      <button
                        onClick={() => toggleCheck(itemId)}
                        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
                          done
                            ? 'border-[var(--blue-deep)] bg-[var(--blue-deep)]'
                            : 'border-[var(--line)] hover:border-[var(--blue-deep)]'
                        }`}
                      >
                        {done && <Check className="h-3.5 w-3.5 text-white" />}
                      </button>
                      <span className={`text-sm leading-relaxed ${done ? 'text-[var(--muted)] line-through' : 'text-[var(--ink)]'}`}>
                        {item}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-5 shadow-[var(--shadow-soft)]">
        <MonoLabel>20%</MonoLabel>
        <h3 className="mt-3 mb-4 font-semibold text-[var(--ink)]">Развитие через общение</h3>
        <ul className="space-y-2">
          {plan.communication.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-[var(--ink)]">
              <span className="mt-0.5 shrink-0 text-[var(--muted)]">—</span>
              <span className="leading-relaxed">{item}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-2xl border border-[var(--line)] bg-[var(--paper)] p-5 shadow-[var(--shadow-soft)]">
        <MonoLabel>10%</MonoLabel>
        <h3 className="mt-3 mb-4 font-semibold text-[var(--ink)]">Книги и курсы</h3>
        <ul className="space-y-2">
          {plan.learning.map((item, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-[var(--ink)]">
              <span className="mt-0.5 shrink-0 text-[var(--muted)]">—</span>
              <span className="leading-relaxed">{item}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
