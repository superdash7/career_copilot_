interface EyebrowProps {
  children: React.ReactNode;
  className?: string;
}

export default function Eyebrow({ children, className = '' }: EyebrowProps) {
  return <p className={`editorial-eyebrow ${className}`.trim()}>{children}</p>;
}
