import { TrendingUp, RefreshCw, Search } from 'lucide-react';
import type { Scenario } from '../types';

const ICONS: Record<Scenario, React.ReactNode> = {
  'Следующий грейд': <TrendingUp className="h-5 w-5" />,
  'Смена профессии': <RefreshCw className="h-5 w-5" />,
  'Исследование возможностей': <Search className="h-5 w-5" />,
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
        w-full text-left rounded-xl border-2 p-5 transition-all duration-200 cursor-pointer
        ${selected
          ? 'border-(--color-accent) bg-(--color-accent-light) shadow-md'
          : 'border-(--color-border) bg-(--color-surface-raised) hover:border-(--color-accent)/40 hover:shadow-sm'
        }
      `}
    >
      <div className="flex items-start gap-4">
        <div
          className={`shrink-0 mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg transition-colors duration-200 ${
            selected
              ? 'bg-(--color-accent) text-white'
              : 'bg-(--color-accent-light) text-(--color-accent)'
          }`}
        >
          {ICONS[value]}
        </div>
        <div>
          <p className={`font-semibold mb-1 ${selected ? 'text-(--color-accent)' : 'text-(--color-text-primary)'}`}>
            {label}
          </p>
          <p className="text-sm text-(--color-text-muted) leading-relaxed">{description}</p>
        </div>
      </div>
    </button>
  );
}
