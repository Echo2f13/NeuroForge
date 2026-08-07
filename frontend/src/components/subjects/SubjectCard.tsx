'use client';

import React, { useState } from 'react';
import { SubjectSummary } from '@/lib/api';

interface SubjectCardProps {
  subject: SubjectSummary;
  isActive?: boolean;
  isDeleting?: boolean;
  onSelect?: (subject: SubjectSummary) => void;
  onEdit?: (subject: SubjectSummary) => void;
  onArchive?: (subject: SubjectSummary) => void;
  onDelete?: (subject: SubjectSummary) => void;
  onRestore?: (subject: SubjectSummary) => void;
}

export function SubjectCard({
  subject,
  isActive = false,
  isDeleting = false,
  onSelect,
  onEdit,
  onArchive,
  onDelete,
  onRestore,
}: SubjectCardProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const isArchived = subject.status === 'archived';

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = () => {
    onDelete?.(subject);
    setShowDeleteModal(false);
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
  };

  // Get mastery level label and color
  const getMasteryLevel = (percent: number): { label: string; color: string } => {
    if (percent >= 80) return { label: 'Expert', color: 'text-green-600 bg-green-100' };
    if (percent >= 60) return { label: 'Proficient', color: 'text-blue-600 bg-blue-100' };
    if (percent >= 40) return { label: 'Intermediate', color: 'text-yellow-600 bg-yellow-100' };
    if (percent >= 20) return { label: 'Beginner', color: 'text-orange-600 bg-orange-100' };
    return { label: 'Novice', color: 'text-gray-600 bg-gray-100' };
  };

  const mastery = getMasteryLevel(subject.mastery_percent);

  // Format date
  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return date.toLocaleDateString();
  };

  return (
    <div
      className={`relative bg-white dark:bg-gray-800 rounded-xl border-2 transition-all duration-200 ${
        isActive
          ? 'border-blue-500 shadow-lg shadow-blue-500/20'
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
      } ${isArchived ? 'opacity-60' : ''}`}
      style={{
        borderLeftColor: subject.color || undefined,
        borderLeftWidth: subject.color ? '4px' : undefined,
      }}
    >
      {/* Header */}
      <div
        className="p-4 cursor-pointer"
        onClick={() => onSelect?.(subject)}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{subject.icon || '📚'}</span>
            <div>
              <h3 className="font-semibold text-lg">{subject.name}</h3>
              {subject.description && (
                <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-1">
                  {subject.description}
                </p>
              )}
            </div>
          </div>
          {subject.is_default && (
            <span className="px-2 py-1 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
              Default
            </span>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="px-4 pb-4">
        <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
          <div className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>{subject.document_count} docs</span>
          </div>
          <div className="flex items-center gap-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <span>{subject.quiz_count} quizzes</span>
          </div>
          {subject.average_score > 0 && (
            <div className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
              </svg>
              <span>{Math.round(subject.average_score)}%</span>
            </div>
          )}
        </div>

        {/* Progress Bar */}
        <div className="mt-3">
          <div className="flex items-center justify-between mb-1">
            <span className={`text-xs px-2 py-0.5 rounded ${mastery.color}`}>
              {mastery.label}
            </span>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              {Math.round(subject.mastery_percent)}% mastery
            </span>
          </div>
          <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full transition-all duration-500"
              style={{ width: `${subject.mastery_percent}%` }}
            />
          </div>
        </div>

        {/* Last Activity */}
        <div className="mt-3 text-xs text-gray-500 dark:text-gray-400">
          Last activity: {formatDate(subject.last_activity_at)}
        </div>
      </div>

      {/* Actions */}
      <div className="px-4 pb-4 flex items-center gap-2">
        {isArchived ? (
          <>
            {onRestore && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRestore(subject);
                }}
                className="flex-1 px-3 py-2 text-sm bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/40 transition-colors"
              >
                Restore
              </button>
            )}
            {onDelete && !subject.is_default && (
              <button
                onClick={handleDeleteClick}
                className="px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
              >
                Delete
              </button>
            )}
          </>
        ) : (
          <>
            {onSelect && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(subject);
                }}
                className="flex-1 px-3 py-2 text-sm bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
              >
                Open
              </button>
            )}
            {onEdit && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(subject);
                }}
                className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                Edit
              </button>
            )}
            {onArchive && !subject.is_default && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onArchive(subject);
                }}
                className="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                Archive
              </button>
            )}
          </>
        )}
      </div>

      {/* Active Indicator */}
      {isActive && (
        <div className="absolute top-2 right-2">
          <span className="flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500" />
          </span>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg max-w-md mx-4 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="flex-shrink-0 w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-gray-900 dark:text-white">Delete Subject?</h3>
            </div>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Are you sure you want to delete &quot;{subject.name}&quot;? This will permanently remove all documents, quizzes, and progress associated with this subject. This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={handleCancelDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isDeleting && (
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                )}
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SubjectCard;
