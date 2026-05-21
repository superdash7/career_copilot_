interface Props {
  current: number;
  total: number;
  label: string;
}

export default function MiniProgress({ current, total, label }: Props) {
  return (
    <p className="font-[var(--font-mono)] text-[11px] uppercase tracking-[0.13em] text-[var(--muted)]">
      Шаг {current} из {total}
      <span className="mx-1.5 text-[var(--line)]">·</span>
      {label}
    </p>
  );
}
