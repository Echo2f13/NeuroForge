'use client';

import React, { useState } from 'react';
import { SubjectSummary } from '@/lib/api';
import { SubjectCard } from './SubjectCard';

interface SubjectListProps {
  subjects: SubjectSummary[];
  activeSubjectId?: string;
  onSelect?: (subject: SubjectSummary) => void;
  onEdit?: (subject: SubjectSummary) => void;
  onArchive?: (subject: SubjectSummary) => void;
  onDelete?: (subject: SubjectSummary) => void;
  onRestore?: (subject: SubjectSummary) => void;
  onCreateNew?: () => void;
  loading?: boolean;
  isDeleting?: boolean;
  emptyMessage?: string;
  showArchived?: boolean;
}

type SortOption = 'name' | 'last_activity' | 'mastery' | 'document_count';
type ViewMode = 'grid' | 'list';

export function SubjectList({
  subjects,
  activeSubjectId,
  onSelect,
  onEdit,
  onArchive,
  onDelete,
  onRestore,
  onCreateNew,
  loading = false,
  isDeleting = false,
  emptyMessage = 'No subjects found',
  showArchived = false,
}: SubjectListProps) {
  const [sortBy, setSortBy] = useState<SortOption>('last_activity');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [filterStatus, setFilterStatus] = useState<'all' | 'active' | 'archived'>('active');

  // Filter subjects
  const filteredSubjects = subjects.filter(subject => {
    if (filterStatus === 'active') return subject.status === 'active';
    if (filterStatus === 'archived') return subject.status === 'archived';
    return true;
  });

  // Sort subjects
  const sortedSubjects = [...filteredSubjects].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.name.localeCompare(b.name);
      case 'mastery':
        return b.mastery_percent - a.mastery_percent;
      case 'document_count':
        return b.document_count - a.document_count;
      case 'last_activity':
      default:
        const aDate = a.last_activity_at ? new Date(a.last_activity_at).getTime() : 0;
        const bDate = b.last_activity_at ? new Date(b.last_activity_at).getTime() : 0;
        return bDate - aDate;
    }
  });

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-4">
        {/* Header skeleton */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="h-10 w-48 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          <div className="flex items-center gap-3">
            <div className="h-10 w-32 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
            <div className="h-10 w-20 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
            <div className="h-10 w-32 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          </div>
        </div>
        {/* Cards skeleton */}
        <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-4'}>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 animate-pulse"
            >
              {/* Header */}
              <div className="flex items-start gap-3 mb-4">
                <div className="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-lg" />
                <div className="flex-1">
                  <div className="h-5 w-32 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
                  <div className="h-3 w-48 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
              </div>
              {/* Stats */}
              <div className="flex items-center gap-4 mb-3">
                <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
                <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
              </div>
              {/* Progress bar */}
              <div className="mb-3">
                <div className="flex justify-between mb-1">
                  <div className="h-4 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
                  <div className="h-4 w-12 bg-gray-200 dark:bg-gray-700 rounded" />
                </div>
                <div className="h-2 w-full bg-gray-200 dark:bg-gray-700 rounded-full" />
              </div>
              {/* Last activity */}
              <div className="h-3 w-24 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
              {/* Actions */}
              <div className="flex items-center gap-2">
                <div className="flex-1 h-9 bg-gray-200 dark:bg-gray-700 rounded-lg" />
                <div className="h-9 w-16 bg-gray-200 dark:bg-gray-700 rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Filter Tabs */}
        {showArchived && (
          <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            {(['active', 'archived', 'all'] as const).map((status) => (
              <button
                key={status}
                onClick={() => setFilterStatus(status)}
                className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                  filterStatus === status
                    ? 'bg-white dark:bg-gray-700 shadow text-blue-600 dark:text-blue-400'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
        )}

        {/* Sort & View Controls */}
        <div className="flex items-center gap-3">
          {/* Sort Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="px-3 py-2 text-sm bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="last_activity">Last Activity</option>
            <option value="name">Name</option>
            <option value="mastery">Mastery</option>
            <option value="document_count">Documents</option>
          </select>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-colors ${
                viewMode === 'grid'
                  ? 'bg-white dark:bg-gray-700 shadow'
                  : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-colors ${
                viewMode === 'list'
                  ? 'bg-white dark:bg-gray-700 shadow'
                  : 'text-gray-500 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>

          {/* Create Button */}
          {onCreateNew && (
            <button
              onClick={onCreateNew}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Subject
            </button>
          )}
        </div>
      </div>

      {/* Subject Grid/List */}
      {sortedSubjects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="text-6xl mb-4">📚</div>
          <h3 className="text-lg font-medium mb-2">{emptyMessage}</h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            {filterStatus === 'archived'
              ? 'No archived subjects. Subjects you archive will appear here.'
              : 'Create your first subject to organize your learning materials.'}
          </p>
          {onCreateNew && filterStatus !== 'archived' && (
            <button
              onClick={onCreateNew}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create Subject
            </button>
          )}
        </div>
      ) : (
        <div
          className={
            viewMode === 'grid'
              ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'
              : 'space-y-4'
          }
        >
          {sortedSubjects.map((subject) => (
            <SubjectCard
              key={subject.id}
              subject={subject}
              isActive={subject.id === activeSubjectId}
              isDeleting={isDeleting}
              onSelect={onSelect}
              onEdit={onEdit}
              onArchive={onArchive}
              onDelete={onDelete}
              onRestore={onRestore}
            />
          ))}
        </div>
      )}

      {/* Stats Summary */}
      {sortedSubjects.length > 0 && (
        <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
          <div className="flex flex-wrap items-center justify-center gap-6 text-sm text-gray-600 dark:text-gray-400">
            <div>
              <span className="font-medium text-gray-900 dark:text-white">
                {sortedSubjects.length}
              </span>{' '}
              {sortedSubjects.length === 1 ? 'subject' : 'subjects'}
            </div>
            <div>
              <span className="font-medium text-gray-900 dark:text-white">
                {sortedSubjects.reduce((sum, s) => sum + s.document_count, 0)}
              </span>{' '}
              total documents
            </div>
            <div>
              <span className="font-medium text-gray-900 dark:text-white">
                {Math.round(
                  sortedSubjects.reduce((sum, s) => sum + s.mastery_percent, 0) /
                    sortedSubjects.length
                )}
                %
              </span>{' '}
              average mastery
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SubjectList;
