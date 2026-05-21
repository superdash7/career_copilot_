import { useTheme } from '../useTheme';
import { useAuth } from '../auth/AuthContext';
import { Sun, Moon, LogOut, Users, LayoutDashboard } from 'lucide-react';
import { useGoToDashboard } from '../navigation/goToDashboardContext';
import Button from './ui/Button';

interface Props {
  showBrand?: boolean;
  /** На экране самого кабинета ссылка не нужна — пользователь уже там. */
  hidePersonalCabinet?: boolean;
  onLogin?: () => void;
  onRegister?: () => void;
  onTeams?: () => void;
}

export default function NavBar({
  showBrand = true,
  hidePersonalCabinet = false,
  onLogin,
  onRegister,
  onTeams,
}: Props) {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const goToDashboard = useGoToDashboard();
  return (
    <div className="flex items-center justify-between py-4">
      {showBrand ? (
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--blue-deep)] text-sm font-bold text-white"
          >
            ✦
          </span>
          <span className="text-sm font-semibold tracking-tight text-[var(--ink)]">
            Career Copilot
          </span>
        </div>
      ) : (
        <div />
      )}

      <div className="flex items-center gap-2">
        {!user && onRegister && (
          <Button size="sm" onClick={onRegister}>
            Начать бесплатно
          </Button>
        )}
        {!user && onLogin && (
          <Button variant="ghost" size="sm" onClick={onLogin}>
            Войти
          </Button>
        )}

        {user && !hidePersonalCabinet && (
          <button
            type="button"
            onClick={goToDashboard}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] px-3 py-1.5 text-xs font-medium text-[var(--blue-deep)] transition-colors hover:border-[var(--blue-deep)] hover:bg-[var(--paper)]"
          >
            <LayoutDashboard className="h-3.5 w-3.5" />
            Личный кабинет
          </button>
        )}
        {user && (
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--line)] px-3 py-1.5 text-xs font-medium text-[var(--muted)] transition-colors hover:border-[var(--accent-red)] hover:text-[var(--accent-red)]"
          >
            <LogOut className="h-3.5 w-3.5" />
            Выйти
          </button>
        )}

        {onTeams && (
          <button
            onClick={onTeams}
            className="hidden items-center gap-1.5 text-sm font-medium text-[var(--muted)] transition-colors hover:text-[var(--blue-deep)] sm:inline-flex"
          >
            <Users className="h-3.5 w-3.5" />
            Для команд
          </button>
        )}

        <button
          onClick={toggle}
          className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--line)] bg-[var(--paper)] text-[var(--muted)] transition-colors hover:border-[var(--blue-deep)] hover:text-[var(--blue-deep)]"
          aria-label={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
        >
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </button>
      </div>
    </div>
  );
}
