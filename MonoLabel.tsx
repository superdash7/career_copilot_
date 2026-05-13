interface MonoLabelProps {
  children: React.ReactNode;
  className?: string;
}

export default function MonoLabel({ children, className = '' }: MonoLabelProps) {
  return <span className={`mono-label ${className}`.trim()}>{children}</span>;
}
