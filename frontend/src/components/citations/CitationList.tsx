'use client';

import React, { useState } from 'react';
import { Citation } from '@/lib/api';
import { CitationCard } from './CitationCard';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CitationListProps {
  citations: Citation[];
  onViewSource: (citation: Citation) => void;
  title?: string;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  maxVisible?: number;
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
  maxVisible = 5,
}: CitationListProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [showAll, setShowAll] = useState(false);
  
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
  
  return (
    <div className="mt-4 border border-gray-200 dark:border-gray-700 
                    rounded-lg overflow-hidden">
      {/* Header */}
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
      
      {/* Citation list */}
      {(!collapsible || expanded) && (
        <div className="p-4 space-y-3 bg-white dark:bg-gray-900">
          {visibleCitations.map((citation, index) => (
            <CitationCard
              key={citation.id}
              citation={citation}
              index={index}
              onViewSource={onViewSource}
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
