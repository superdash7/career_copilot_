import { useEffect, useState } from 'react';

interface Props {
  id: string;
  children: React.ReactNode;
}

export default function SoftOnboardingHint({ id, children }: Props) {
  const key = `onboarding_seen_${id}`;
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(key)) {
      const t = setTimeout(() => setVisible(true), 600);
      return () => clearTimeout(t);
    }
  }, [key]);

  const dismiss = () => {
    setVisible(false);
    localStorage.setItem(key, '1');
  };

  if (!visible) return null;

  return (
    <div className="fade-in flex items-start gap-3 rounded-2xl border border-[var(--line)] bg-[var(--chip)] p-4">
      <span
        aria-hidden
        className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[var(--line)] text-[10px] text-[var(--blue-deep)]"
      >
        i
      </span>
      <p className="flex-1 text-sm text-(--color-text-secondary)">{children}</p>
      <button
        onClick={dismiss}
        className="shrink-0 rounded-full border border-[var(--line)] px-2 py-0.5 text-[10px] uppercase tracking-[0.1em] text-[var(--muted)] transition-colors hover:bg-[var(--paper)]"
      >
        x
      </button>
    </div>
  );
}
