'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useSubject } from '@/contexts/SubjectContext';
import { SubjectSummary } from '@/lib/api';

interface SubjectSelectorProps {
  onCreateNew?: () => void;
  onViewAll?: () => void;
  className?: string;
}

export function SubjectSelector({ onCreateNew, onViewAll, className = '' }: SubjectSelectorProps) {
  const { subjects, activeSubjectId, activeSubject, setActiveSubject, loading, isSwitching } = useSubject();
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Filter subjects by search query
  const filteredSubjects = subjects.filter(subject =>
    subject.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (subject.description?.toLowerCase() || '').includes(searchQuery.toLowerCase())
  );

  // Get mastery color
  const getMasteryColor = (mastery: number): string => {
    if (mastery >= 80) return 'text-green-500';
    if (mastery >= 60) return 'text-blue-500';
    if (mastery >= 40) return 'text-yellow-500';
    return 'text-red-500';
  };

  const handleSelect = async (subject: SubjectSummary) => {
    await setActiveSubject(subject.id);
    setIsOpen(false);
    setSearchQuery('');
  };

  const currentSubject = subjects.find(s => s.id === activeSubjectId) || activeSubject;

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading || isSwitching}
        className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors min-w-[200px] disabled:opacity-70"
      >
        {isSwitching && (
          <svg className="animate-spin w-4 h-4 text-blue-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
        {currentSubject ? (
          <>
            {!isSwitching && <span className="text-lg">{currentSubject.icon || '📚'}</span>}
            <span className="flex-1 text-left truncate font-medium">
              {isSwitching ? 'Switching...' : currentSubject.name}
            </span>
            {!isSwitching && (
              <span className={`text-xs ${getMasteryColor((currentSubject as SubjectSummary).mastery_percent || 0)}`}>
                {Math.round((currentSubject as SubjectSummary).mastery_percent || 0)}%
              </span>
            )}
          </>
        ) : (
          <span className="text-gray-500">Select Subject</span>
        )}
        <svg
          className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-1 w-full min-w-[280px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-50">
          {/* Search Input */}
          <div className="p-2 border-b border-gray-200 dark:border-gray-700">
            <input
              type="text"
              placeholder="Search subjects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
          </div>

          {/* Subject List */}
          <div className="max-h-[300px] overflow-y-auto">
            {filteredSubjects.length === 0 ? (
              <div className="p-4 text-center text-gray-500 text-sm">
                No subjects found
              </div>
            ) : (
              filteredSubjects.map(subject => (
                <button
                  key={subject.id}
                  onClick={() => handleSelect(subject)}
                  className={`w-full flex items-center gap-3 px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors ${
                    subject.id === activeSubjectId ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                  }`}
                >
                  <span className="text-lg">{subject.icon || '📚'}</span>
                  <div className="flex-1 text-left">
                    <div className="font-medium truncate">{subject.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      {subject.document_count} docs · {subject.quiz_count} quizzes
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-sm font-medium ${getMasteryColor(subject.mastery_percent)}`}>
                      {Math.round(subject.mastery_percent)}%
                    </div>
                    <div className="w-16 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-blue-500 rounded-full"
                        style={{ width: `${subject.mastery_percent}%` }}
                      />
                    </div>
                  </div>
                  {subject.id === activeSubjectId && (
                    <svg className="w-4 h-4 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>

          {/* Actions */}
          <div className="p-2 border-t border-gray-200 dark:border-gray-700 space-y-1">
            {onCreateNew && (
              <button
                onClick={() => {
                  setIsOpen(false);
                  onCreateNew();
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-600 dark:text-blue-400 hover:bg-gray-50 dark:hover:bg-gray-700 rounded transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Create New Subject
              </button>
            )}
            {onViewAll && (
              <button
                onClick={() => {
                  setIsOpen(false);
                  onViewAll();
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700 rounded transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                </svg>
                View All Subjects
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default SubjectSelector;
