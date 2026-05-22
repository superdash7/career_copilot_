import { useState, useEffect } from 'react';

interface Props {
  text: string;
  subtext?: string;
  durationMs?: number;
}

export default function ProgressLoader({ text, subtext, durationMs = 30000 }: Props) {
  const [barWidth, setBarWidth] = useState(0);

  useEffect(() => {
    let mounted = true;
    let elapsed = 0;
    const tick = 100;

    const interval = setInterval(() => {
      if (!mounted) return;
      elapsed += tick;
      const pct = Math.min((elapsed / durationMs) * 90, 90);
      setBarWidth(pct);
    }, tick);

    return () => { mounted = false; clearInterval(interval); };
  }, [durationMs]);

  return (
    <div className="flex flex-col items-center justify-center gap-5 py-16 fade-in">
      <div className="text-center">
        <p className="text-base font-medium text-(--color-text-primary) mb-1">{text}</p>
        {subtext && <p className="text-sm text-(--color-text-muted)">{subtext}</p>}
      </div>

      <div className="w-full max-w-xs">
        <div className="h-1.5 rounded-full bg-(--color-border) overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-(--color-accent) to-indigo-400 transition-all duration-500 ease-out"
            style={{ width: `${barWidth}%` }}
          />
        </div>
      </div>
    </div>
  );
}
