import { Sun, Moon, Compass } from 'lucide-react';
import { useTheme } from '../useTheme';

interface Props {
  showBrand?: boolean;
}

export default function NavBar({ showBrand = true }: Props) {
  const { theme, toggle } = useTheme();
  return (
    <div className="flex items-center justify-between py-3">
      {showBrand ? (
        <div className="flex items-center gap-2">
          <Compass className="h-5 w-5 text-(--color-accent)" />
          <span className="text-sm font-semibold text-(--color-text-primary) tracking-tight">
            Career Copilot
          </span>
        </div>
      ) : (
        <div />
      )}
      <button
        onClick={toggle}
        className="flex items-center justify-center h-9 w-9 rounded-lg
                   bg-(--color-surface-alt) border border-(--color-border)
                   text-(--color-text-secondary) transition-all duration-200
                   hover:bg-(--color-accent-light) hover:text-(--color-accent)"
        aria-label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
      >
        {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </div>
  );
}
