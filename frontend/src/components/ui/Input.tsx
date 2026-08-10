'use client';

import { forwardRef, InputHTMLAttributes } from 'react';

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'size'> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  size?: 'sm' | 'md' | 'lg';
  onChange?: (value: string) => void;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  error,
  hint,
  icon,
  iconPosition = 'left',
  size = 'md',
  className = '',
  onChange,
  ...props
}, ref) => {
  const sizes = {
    sm: 'px-3 py-2 text-sm',
    md: 'px-4 py-3 text-base',
    lg: 'px-5 py-4 text-lg',
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e.target.value);
  };

  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && iconPosition === 'left' && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
            {icon}
          </div>
        )}
        <input
          ref={ref}
          onChange={handleChange}
          className={`
            w-full border rounded-xl
            focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 
            outline-none transition-all duration-200
            placeholder:text-gray-400 dark:placeholder:text-gray-500
            bg-white dark:bg-gray-800
            text-gray-900 dark:text-white
            ${error 
              ? 'border-red-300 dark:border-red-500 focus:ring-red-500 focus:border-red-500' 
              : 'border-gray-200 dark:border-gray-700'
            }
            ${icon && iconPosition === 'left' ? 'pl-10' : ''}
            ${icon && iconPosition === 'right' ? 'pr-10' : ''}
            ${sizes[size]}
            ${className}
          `}
          {...props}
        />
        {icon && iconPosition === 'right' && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
            {icon}
          </div>
        )}
      </div>
      {error && (
        <p className="mt-1.5 text-sm text-red-500 dark:text-red-400">{error}</p>
      )}
      {hint && !error && (
        <p className="mt-1.5 text-sm text-gray-500 dark:text-gray-400">{hint}</p>
      )}
    </div>
  );
});

Input.displayName = 'Input';
