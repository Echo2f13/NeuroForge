'use client';

import React, { useState } from 'react';
import { useSubject } from '@/contexts/SubjectContext';
import { SubjectSelector } from './SubjectSelector';

interface SubjectHeaderProps {
  onCreateNew?: () => void;
  onViewAll?: () => void;
  compact?: boolean;
  className?: string;
}

export function SubjectHeader({ 
  onCreateNew, 
  onViewAll, 
  compact = false,
  className = '' 
}: SubjectHeaderProps) {
  const { activeSubject, subjects, loading } = useSubject();
  const [showSelector, setShowSelector] = useState(false);

  // Get current subject summary for stats
  const currentSummary = subjects.find(s => s.id === activeSubject?.id);

  // Get mastery color
  const getMasteryColor = (percent: number): string => {
    if (percent >= 80) return 'text-green-500';
    if (percent >= 60) return 'text-blue-500';
    if (percent >= 40) return 'text-yellow-500';
    return 'text-red-500';
  };

  if (loading && !activeSubject) {
    return (
      <div className={`animate-pulse flex items-center gap-3 ${className}`}>
        <div className="w-8 h-8 bg-gray-200 dark:bg-gray-700 rounded-lg" />
        <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded" />
      </div>
    );
  }

  if (compact) {
    return (
      <div className={`relative ${className}`}>
        <SubjectSelector
          onCreateNew={onCreateNew}
          onViewAll={onViewAll}
        />
      </div>
    );
  }

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      {/* Subject Info */}
      <div 
        className="flex items-center gap-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg px-3 py-2 transition-colors"
        onClick={() => setShowSelector(!showSelector)}
      >
        {/* Icon */}
        <div 
          className="w-10 h-10 rounded-lg flex items-center justify-center text-xl"
          style={{ 
            backgroundColor: activeSubject?.color ? `${activeSubject.color}20` : '#f3f4f6',
            borderLeft: activeSubject?.color ? `3px solid ${activeSubject.color}` : undefined,
          }}
        >
          {activeSubject?.icon || '📚'}
        </div>

        {/* Name & Stats */}
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold">{activeSubject?.name || 'General'}</span>
            {activeSubject?.is_default && (
              <span className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded">
                Default
              </span>
            )}
          </div>
          {currentSummary && (
            <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
              <span>{currentSummary.document_count} docs</span>
              <span>·</span>
              <span className={getMasteryColor(currentSummary.mastery_percent)}>
                {Math.round(currentSummary.mastery_percent)}% mastery
              </span>
            </div>
          )}
        </div>

        {/* Dropdown Arrow */}
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${showSelector ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>

      {/* Inline Stats (optional, for larger screens) */}
      {currentSummary && (
        <div className="hidden lg:flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
          <div className="flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>{currentSummary.document_count}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <span>{currentSummary.quiz_count}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-20 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${currentSummary.mastery_percent}%` }}
              />
            </div>
            <span className={getMasteryColor(currentSummary.mastery_percent)}>
              {Math.round(currentSummary.mastery_percent)}%
            </span>
          </div>
        </div>
      )}

      {/* Dropdown */}
      {showSelector && (
        <div className="absolute top-full left-0 mt-2 z-50">
          <SubjectSelector
            onCreateNew={() => {
              setShowSelector(false);
              onCreateNew?.();
            }}
            onViewAll={() => {
              setShowSelector(false);
              onViewAll?.();
            }}
          />
        </div>
      )}
    </div>
  );
}

export default SubjectHeader;
