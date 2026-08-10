'use client';

import React, { useState } from 'react';
import { Citation } from '@/lib/api';
import { CitationCard } from './CitationCard';
import { useCitation } from '@/contexts/CitationContext';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CitationListProps {
  citations: Citation[];
  onViewSource?: (citation: Citation) => void;
  title?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  defaultCollapsed?: boolean;  // Alias for !defaultExpanded
  maxVisible?: number;
  compact?: boolean;
  subjectId?: string;
  loading?: boolean;
}

// ---------------------------------------------------------------------------
// Loading Skeleton Components
// ---------------------------------------------------------------------------

function CitationSkeleton() {
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 animate-pulse">
      <div className="flex items-center gap-3">
        <div className="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-700" />
        <div className="flex-1">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2" />
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
        </div>
        <div className="w-8 h-4 bg-gray-200 dark:bg-gray-700 rounded" />
      </div>
    </div>
  );
}

function LoadingState({ count = 2 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <CitationSkeleton key={i} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CitationList({
  citations,
  onViewSource,
  title = 'Sources',
  collapsible = true,
  defaultExpanded = false,
  defaultCollapsed,
  maxVisible = 5,
  compact = false,
  subjectId,
  loading = false,
}: CitationListProps) {
  // If defaultCollapsed is explicitly set, use it to determine expanded state
  const initialExpanded = defaultCollapsed !== undefined ? !defaultCollapsed : defaultExpanded;
  const [expanded, setExpanded] = useState(initialExpanded);
  const [showAll, setShowAll] = useState(false);
  
  // Use citation context for default view source behavior
  const { openCitation } = useCitation();
  
  const handleViewSource = (citation: Citation) => {
    if (onViewSource) {
      onViewSource(citation);
    } else {
      // Default behavior: use context to open citation
      openCitation(citation, subjectId);
    }
  };
  
  // Show loading skeleton
  if (loading) {
    return (
      <div className="mt-4 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
        {title && (
          <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 flex items-center gap-3">
            <svg 
              className="w-5 h-5 text-gray-500 dark:text-gray-400" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="font-medium text-gray-900 dark:text-white">{title}</span>
            <div className="w-4 h-4 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
          </div>
        )}
        <div className="p-4">
          <LoadingState count={2} />
        </div>
      </div>
    );
  }
  
  if (!citations || citations.length === 0) {
    return null;
  }
  
  const visibleCitations = showAll ? citations : citations.slice(0, maxVisible);
  const hasMore = citations.length > maxVisible;
  
  // Get unique document count
  const uniqueDocs = new Set(citations.map(c => c.document_id)).size;
  
  // Get page range
  const pages = citations
    .filter(c => c.page_number)
    .map(c => c.page_number!)
    .sort((a, b) => a - b);
  const pageRange = pages.length > 0
    ? pages.length === 1
      ? `p. ${pages[0]}`
      : `pp. ${pages[0]}-${pages[pages.length - 1]}`
    : null;
  
  // Compact mode: just show citation badges inline
  if (compact) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-gray-500 dark:text-gray-400">Sources:</span>
        {citations.slice(0, 3).map((citation, index) => (
          <button
            key={citation.id}
            onClick={() => handleViewSource(citation)}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs 
                       bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300
                       rounded-full hover:bg-blue-200 dark:hover:bg-blue-800/50
                       transition-colors cursor-pointer"
            title={`${citation.document_name}${citation.page_number ? `, p.${citation.page_number}` : ''}`}
          >
            [{index + 1}]
          </button>
        ))}
        {citations.length > 3 && (
          <span className="text-xs text-gray-500">+{citations.length - 3} more</span>
        )}
      </div>
    );
  }
  
  return (
    <div className="mt-4 border border-gray-200 dark:border-gray-700 
                    rounded-lg overflow-hidden">
      {/* Header */}
      {title && (
        <button
          onClick={() => collapsible && setExpanded(!expanded)}
          disabled={!collapsible}
          className={`w-full px-4 py-3 flex items-center justify-between
                     bg-gray-50 dark:bg-gray-800/50
                     ${collapsible ? 'hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer' : ''}
                     transition-colors`}
        >
          <div className="flex items-center gap-3">
            {/* Icon */}
            <svg 
              className="w-5 h-5 text-gray-500 dark:text-gray-400" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            
            <span className="font-medium text-gray-900 dark:text-white">
              {title}
            </span>
            
            {/* Count badge */}
            <span className="px-2 py-0.5 text-xs font-medium 
                            bg-blue-100 dark:bg-blue-900/50 
                            text-blue-700 dark:text-blue-300 
                            rounded-full">
              {citations.length} {citations.length === 1 ? 'source' : 'sources'}
            </span>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Summary info */}
            <div className="hidden sm:flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              {uniqueDocs > 1 && (
                <span>{uniqueDocs} documents</span>
              )}
              {pageRange && (
                <span>{pageRange}</span>
              )}
            </div>
            
            {/* Expand indicator */}
            {collapsible && (
              <svg
                className={`w-5 h-5 text-gray-400 transition-transform duration-200 
                           ${expanded ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            )}
          </div>
        </button>
      )}
      
      {/* Citation list */}
      {(!collapsible || expanded || !title) && (
        <div className="p-4 space-y-3 bg-white dark:bg-gray-900">
          {visibleCitations.map((citation, index) => (
            <CitationCard
              key={citation.id}
              citation={citation}
              index={index}
              onViewSource={handleViewSource}
            />
          ))}
          
          {/* Show more/less button */}
          {hasMore && (
            <button
              onClick={() => setShowAll(!showAll)}
              className="w-full py-2 text-sm font-medium
                        text-blue-600 dark:text-blue-400
                        hover:text-blue-700 dark:hover:text-blue-300
                        transition-colors"
            >
              {showAll 
                ? `Show less` 
                : `Show ${citations.length - maxVisible} more sources`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default CitationList;
