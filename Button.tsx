type ButtonVariant = 'primary' | 'secondary' | 'ghost';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClass: Record<ButtonVariant, string> = {
  primary:
    'bg-[var(--blue-deep)] text-white border-transparent hover:shadow-[0_4px_16px_rgba(79,70,229,0.3)] hover:-translate-y-0.5',
  secondary:
    'bg-[var(--paper)] text-[var(--ink)] border-[var(--line)] hover:border-[var(--blue-deep)] hover:text-[var(--blue-deep)] hover:-translate-y-0.5',
  ghost:
    'bg-transparent text-[var(--blue-deep)] border-transparent hover:bg-[var(--chip)]',
};

const sizeClass: Record<ButtonSize, string> = {
  sm: 'px-3.5 py-1.5 text-xs gap-1.5',
  md: 'px-5 py-2.5 text-sm gap-2',
  lg: 'px-7 py-3.5 text-base gap-2.5',
};

export default function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  type = 'button',
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={[
        'inline-flex items-center justify-center rounded-xl border font-semibold',
        'transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--blue-deep)]/30 focus-visible:ring-offset-2',
        'disabled:cursor-not-allowed disabled:opacity-50',
        variantClass[variant],
        sizeClass[size],
        className,
      ].join(' ')}
      {...rest}
    >
      {children}
    </button>
  );
}
