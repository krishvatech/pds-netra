import type { HTMLAttributes } from 'react';

type SkeletonProps = HTMLAttributes<HTMLDivElement>;

export function Skeleton({ className = '', ...props }: SkeletonProps) {
  return <div className={`animate-pulse rounded-lg bg-white/10 ${className}`} {...props} />;
}
