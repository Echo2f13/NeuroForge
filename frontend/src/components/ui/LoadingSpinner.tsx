'use client';

interface LoadingSpinnerProps {
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  color?: 'primary' | 'white' | 'gray';
  className?: string;
}

export function LoadingSpinner({ 
  size = 'md', 
  color = 'primary',
  className = '' 
}: LoadingSpinnerProps) {
  const sizeClasses = {
    xs: 'w-3 h-3',
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16',
  };

  const colorClasses = {
    primary: 'border-indigo-200 border-t-indigo-600 dark:border-indigo-800 dark:border-t-indigo-400',
    white: 'border-white/30 border-t-white',
    gray: 'border-gray-200 border-t-gray-600 dark:border-gray-700 dark:border-t-gray-400',
  };

  return (
    <div 
      className={`${sizeClasses[size]} border-2 ${colorClasses[color]} rounded-full animate-spin ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}

// Loading overlay component
interface LoadingOverlayProps {
  message?: string;
  transparent?: boolean;
}

export function LoadingOverlay({ message = 'Loading...', transparent = false }: LoadingOverlayProps) {
  return (
    <div className={`
      absolute inset-0 flex flex-col items-center justify-center z-10
      ${transparent ? 'bg-white/80 dark:bg-gray-900/80' : 'bg-white dark:bg-gray-900'}
      backdrop-blur-sm
    `}>
      <LoadingSpinner size="lg" />
      <p className="mt-4 text-gray-500 dark:text-gray-400 font-medium">{message}</p>
    </div>
  );
}
