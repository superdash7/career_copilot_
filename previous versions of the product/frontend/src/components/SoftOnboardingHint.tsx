import { useEffect, useState } from 'react';
import { Lightbulb, X } from 'lucide-react';

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
    <div className="fade-in flex items-start gap-3 rounded-xl border border-(--color-accent)/20 bg-(--color-accent-light) p-4">
      <Lightbulb className="h-5 w-5 shrink-0 text-(--color-accent) mt-0.5" />
      <p className="flex-1 text-sm text-(--color-text-secondary)">{children}</p>
      <button onClick={dismiss} className="shrink-0 text-(--color-text-muted) hover:text-(--color-text-secondary) transition-colors">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
