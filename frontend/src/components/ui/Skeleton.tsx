'use client';

import { HTMLAttributes } from 'react';

interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  lines?: number;
}

export function Skeleton({
  variant = 'rectangular',
  width,
  height,
  lines = 1,
  className = '',
  ...props
}: SkeletonProps) {
  const baseClasses = 'animate-pulse bg-gray-200 dark:bg-gray-700';
  
  const variantClasses = {
    text: 'rounded h-4',
    circular: 'rounded-full',
    rectangular: 'rounded-lg',
  };

  if (variant === 'text' && lines > 1) {
    return (
      <div className={`space-y-2 ${className}`} {...props}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`${baseClasses} ${variantClasses.text}`}
            style={{
              width: i === lines - 1 ? '75%' : '100%',
              height,
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`${baseClasses} ${variantClasses[variant]} ${className}`}
      style={{ width, height }}
      {...props}
    />
  );
}

// Pre-built skeleton components
export function QuizSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <div className="flex justify-between items-center">
        <Skeleton width={120} height={32} />
        <Skeleton width={80} height={24} variant="text" />
      </div>
      <Skeleton height={24} variant="text" className="w-3/4" />
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} height={56} className="w-full" />
        ))}
      </div>
    </div>
  );
}

export function FlashcardSkeleton() {
  return (
    <div className="flex flex-col items-center gap-6 p-8">
      <div className="flex gap-4">
        <Skeleton width={40} height={40} variant="circular" />
        <Skeleton width={200} height={40} />
        <Skeleton width={40} height={40} variant="circular" />
      </div>
      <Skeleton width={400} height={250} className="rounded-2xl" />
      <Skeleton width={120} height={40} />
    </div>
  );
}

export function NotesSkeleton() {
  return (
    <div className="space-y-6 p-6">
      <Skeleton height={32} variant="text" className="w-1/2" />
      <div className="space-y-4">
        {[1, 2, 3].map((section) => (
          <div key={section} className="space-y-2">
            <Skeleton height={24} variant="text" className="w-1/3" />
            <Skeleton variant="text" lines={3} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChatSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex justify-end">
        <Skeleton width={200} height={48} className="rounded-2xl" />
      </div>
      <div className="flex justify-start">
        <Skeleton width={300} height={80} className="rounded-2xl" />
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-6">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="p-4 rounded-xl border border-gray-200 dark:border-gray-700">
          <Skeleton height={20} variant="text" className="w-1/2 mb-2" />
          <Skeleton height={36} variant="text" className="w-3/4" />
        </div>
      ))}
    </div>
  );
}
