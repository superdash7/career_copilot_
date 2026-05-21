import type { ReactNode } from 'react';
import { useAuth } from '../auth/AuthContext';

interface Props {
  children: ReactNode;
}

export default function ProtectedRoute({ children }: Props) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-(--color-surface)">
        <p className="text-sm text-(--color-text-muted)">Проверяем сессию…</p>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return <>{children}</>;
}
