'use client';

interface ProgressBarProps {
  progress: number;
  size?: 'sm' | 'md' | 'lg';
  color?: 'primary' | 'success' | 'warning' | 'error' | 'info';
  showLabel?: boolean;
  animated?: boolean;
  className?: string;
}

export function ProgressBar({
  progress,
  size = 'md',
  color = 'primary',
  showLabel = false,
  animated = true,
  className = '',
}: ProgressBarProps) {
  const normalizedProgress = Math.min(100, Math.max(0, progress));
  
  const sizeClasses = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  };

  const colorClasses = {
    primary: 'from-indigo-500 to-purple-500',
    success: 'from-green-500 to-emerald-500',
    warning: 'from-yellow-500 to-orange-500',
    error: 'from-red-500 to-pink-500',
    info: 'from-blue-500 to-cyan-500',
  };

  return (
    <div className={`w-full ${className}`}>
      {showLabel && (
        <div className="flex justify-between mb-1">
          <span className="text-sm text-gray-600 dark:text-gray-400">Progress</span>
          <span className="text-sm font-medium text-gray-900 dark:text-white">{Math.round(normalizedProgress)}%</span>
        </div>
      )}
      <div className={`bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden ${sizeClasses[size]}`}>
        <div
          className={`
            h-full bg-gradient-to-r ${colorClasses[color]} rounded-full
            ${animated ? 'transition-all duration-500 ease-out' : ''}
          `}
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>
    </div>
  );
}

// Circular progress variant
interface CircularProgressProps {
  progress: number;
  size?: number;
  strokeWidth?: number;
  color?: 'primary' | 'success' | 'warning' | 'error' | 'info';
  showLabel?: boolean;
}

export function CircularProgress({
  progress,
  size = 80,
  strokeWidth = 8,
  color = 'primary',
  showLabel = true,
}: CircularProgressProps) {
  const normalizedProgress = Math.min(100, Math.max(0, progress));
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (normalizedProgress / 100) * circumference;

  const colorClasses = {
    primary: 'text-indigo-500',
    success: 'text-green-500',
    warning: 'text-yellow-500',
    error: 'text-red-500',
    info: 'text-blue-500',
  };

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} className="-rotate-90">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          className="fill-none stroke-gray-200 dark:stroke-gray-700"
        />
        {/* Progress circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className={`fill-none ${colorClasses[color]} transition-all duration-500 ease-out`}
          style={{
            stroke: 'currentColor',
            strokeDasharray: circumference,
            strokeDashoffset: offset,
          }}
        />
      </svg>
      {showLabel && (
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-semibold text-gray-900 dark:text-white">
            {Math.round(normalizedProgress)}%
          </span>
        </div>
      )}
    </div>
  );
}
