interface Props {
  lines?: number;
  className?: string;
}

export function SkeletonLine({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-(--color-border)/60 ${className}`}
    />
  );
}

export default function Skeleton({ lines = 4, className = '' }: Props) {
  return (
    <div className={`space-y-4 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine
          key={i}
          className={`h-4 ${i === 0 ? 'w-3/4' : i === lines - 1 ? 'w-1/2' : 'w-full'}`}
        />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="card animate-pulse space-y-4">
      <SkeletonLine className="h-5 w-1/3" />
      <SkeletonLine className="h-4 w-full" />
      <SkeletonLine className="h-4 w-2/3" />
      <div className="flex gap-2 pt-2">
        <SkeletonLine className="h-8 w-24 rounded-xl" />
        <SkeletonLine className="h-8 w-24 rounded-xl" />
        <SkeletonLine className="h-8 w-20 rounded-xl" />
      </div>
    </div>
  );
}

export function SkeletonForm() {
  return (
    <div className="space-y-8 fade-in">
      <div>
        <SkeletonLine className="h-6 w-48 mb-3" />
        <SkeletonLine className="h-4 w-72" />
      </div>
      <div className="card space-y-6">
        <div>
          <SkeletonLine className="h-4 w-32 mb-2" />
          <SkeletonLine className="h-12 w-full rounded-xl" />
        </div>
        <div>
          <SkeletonLine className="h-4 w-28 mb-3" />
          <div className="space-y-3">
            <SkeletonLine className="h-20 w-full rounded-xl" />
            <SkeletonLine className="h-20 w-full rounded-xl" />
            <SkeletonLine className="h-20 w-full rounded-xl" />
          </div>
        </div>
        <div>
          <SkeletonLine className="h-4 w-36 mb-2" />
          <SkeletonLine className="h-12 w-full rounded-xl" />
        </div>
      </div>
    </div>
  );
}
