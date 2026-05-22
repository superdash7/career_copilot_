import { Loader2 } from 'lucide-react';

interface Props {
  text?: string;
  subtext?: string;
}

export default function Spinner({ text, subtext }: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 fade-in">
      <Loader2 className="h-8 w-8 animate-spin text-(--color-accent)" />
      {text && <p className="text-base font-medium text-(--color-text-primary)">{text}</p>}
      {subtext && <p className="text-sm text-(--color-text-muted)">{subtext}</p>}
    </div>
  );
}
