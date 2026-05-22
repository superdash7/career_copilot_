interface Props {
  current: number;
  total: number;
  label: string;
}

export default function MiniProgress({ current, total, label }: Props) {
  return (
    <p className="text-xs font-medium text-(--color-text-muted) tracking-wide">
      Шаг {current} из {total}
      <span className="mx-1.5 text-(--color-border)">·</span>
      {label}
    </p>
  );
}
