import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { setToastListener } from './toastStore';
import type { ToastItem } from './toastStore';

export default function ToastContainer() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    setToastListener((t) => {
      const id = Date.now();
      setToasts((prev) => [...prev, { ...t, id }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== id));
      }, 4000);
    });
    return () => {
      setToastListener(() => {});
    };
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((x) => x.id !== id));

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="slide-up flex items-center gap-3 rounded-xl border border-(--color-border) bg-(--color-surface-raised) px-4 py-3 shadow-lg min-w-[280px] max-w-[90vw]"
        >
          <p className="flex-1 text-sm text-(--color-text-primary)">{t.message}</p>
          {t.action && (
            <button
              onClick={() => {
                t.action!.onClick();
                dismiss(t.id);
              }}
              className="shrink-0 text-sm font-semibold text-(--color-accent) hover:text-(--color-accent-hover) transition-colors"
            >
              {t.action.label}
            </button>
          )}
          <button
            onClick={() => dismiss(t.id)}
            className="shrink-0 text-(--color-text-muted) hover:text-(--color-text-secondary) transition-colors"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  );
}
