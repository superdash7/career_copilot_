import { AlertTriangle, Info, XCircle, CheckCircle, X } from 'lucide-react';

type Variant = 'error' | 'warning' | 'info' | 'success';

interface Props {
  variant?: Variant;
  title?: string;
  children: React.ReactNode;
  onClose?: () => void;
}

const cfg: Record<Variant, { bg: string; border: string; icon: string; El: typeof XCircle }> = {
  error:   { bg: 'bg-red-500/10',    border: 'border-red-500/20',    icon: 'text-red-500',     El: XCircle },
  warning: { bg: 'bg-amber-500/10',  border: 'border-amber-500/20',  icon: 'text-amber-500',   El: AlertTriangle },
  info:    { bg: 'bg-blue-500/10',   border: 'border-blue-500/20',   icon: 'text-blue-500',    El: Info },
  success: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', icon: 'text-emerald-500', El: CheckCircle },
};

export default function Alert({ variant = 'error', title, children, onClose }: Props) {
  const s = cfg[variant];
  return (
    <div className={`fade-in flex gap-3 rounded-xl border p-4 ${s.bg} ${s.border}`} role="alert">
      <div className={`mt-0.5 shrink-0 ${s.icon}`}><s.El className="h-5 w-5" /></div>
      <div className="flex-1 text-sm">
        {title && <p className="font-semibold mb-0.5 text-(--color-text-primary)">{title}</p>}
        <div className="text-(--color-text-secondary)">{children}</div>
      </div>
      {onClose && (
        <button onClick={onClose} className="shrink-0 text-(--color-text-muted) hover:text-(--color-text-secondary) transition-colors">
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
