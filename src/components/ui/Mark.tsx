interface MarkProps {
  children: React.ReactNode;
  className?: string;
}

export default function Mark({ children, className = '' }: MarkProps) {
  return <span className={`editorial-mark ${className}`.trim()}>{children}</span>;
}
