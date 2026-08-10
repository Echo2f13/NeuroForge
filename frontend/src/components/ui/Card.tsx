'use client';

import { forwardRef, HTMLAttributes } from 'react';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  gradient?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card = forwardRef<HTMLDivElement, CardProps>(({
  children,
  hover = false,
  gradient = false,
  padding = 'md',
  className = '',
  ...props
}, ref) => {
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  };

  return (
    <div
      ref={ref}
      className={`
        bg-white dark:bg-gray-800 rounded-2xl border border-gray-100 dark:border-gray-700
        ${hover ? 'hover:shadow-lg hover:border-gray-200 dark:hover:border-gray-600 transition-all duration-200 cursor-pointer' : 'shadow-sm'}
        ${gradient ? 'bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900' : ''}
        ${paddingClasses[padding]}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

export interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}

export const CardHeader = forwardRef<HTMLDivElement, CardHeaderProps>(({
  title,
  subtitle,
  icon,
  action,
  children,
  className = '',
  ...props
}, ref) => (
  <div
    ref={ref}
    className={`flex items-center justify-between mb-4 ${className}`}
    {...props}
  >
    <div className="flex items-center gap-3">
      {icon && (
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-lg">
          {icon}
        </div>
      )}
      <div>
        {title && <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>}
        {subtitle && <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>}
      </div>
    </div>
    {action && <div>{action}</div>}
    {children}
  </div>
));

CardHeader.displayName = 'CardHeader';

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(({
  children,
  className = '',
  ...props
}, ref) => (
  <div ref={ref} className={`${className}`} {...props}>
    {children}
  </div>
));

CardContent.displayName = 'CardContent';

export const CardFooter = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(({
  children,
  className = '',
  ...props
}, ref) => (
  <div
    ref={ref}
    className={`mt-4 pt-4 border-t border-gray-100 dark:border-gray-700 ${className}`}
    {...props}
  >
    {children}
  </div>
));

CardFooter.displayName = 'CardFooter';
