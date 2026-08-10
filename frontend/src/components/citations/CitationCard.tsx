'use client';

import React, { useState, useCallback } from 'react';
import { Citation } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CitationCardProps {
  citation: Citation;
  index: number;
  onViewSource: (citation: Citation) => void;
  compact?: boolean;
}

// ---------------------------------------------------------------------------
// Helper Functions
// ---------------------------------------------------------------------------

function getDocumentIcon(format: string): string {
  switch (format.toLowerCase()) {
    case 'pdf':
      return '📄';
    case 'docx':
      return '📝';
    case 'txt':
    case 'text':
      return '📃';
    case 'markdown':
    case 'md':
      return '📋';
    case 'pptx':
      return '📊';
    case 'image':
      return '🖼️';
    default:
      return '📄';
  }
}

function getRelevanceColor(score: number): string {
  if (score >= 0.8) return 'text-green-600 dark:text-green-400';
  if (score >= 0.6) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-gray-500 dark:text-gray-400';
}

function getRelevanceLabel(score: number): string {
  if (score >= 0.9) return 'Highly relevant';
  if (score >= 0.7) return 'Relevant';
  if (score >= 0.5) return 'Somewhat relevant';
  return 'Low relevance';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CitationCard({ 
  citation, 
  index, 
  onViewSource,
  compact = false 
}: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);
  
  const relevancePercent = Math.round(citation.relevance_score * 100);
  const citationId = `citation-${citation.id}`;
  const contentId = `${citationId}-content`;
  
  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setExpanded(!expanded);
    }
  }, [expanded]);
  
  const handleViewKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onViewSource(citation);
    }
  }, [citation, onViewSource]);
  
  if (compact) {
    // Compact inline badge version
    return (
      <button
        onClick={() => onViewSource(citation)}
        onKeyDown={handleViewKeyDown}
        className="inline-flex items-center gap-1 px-2 py-0.5 text-xs 
                   bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300
                   rounded-full hover:bg-blue-200 dark:hover:bg-blue-800/50
                   focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1
                   transition-colors cursor-pointer"
        aria-label={`Source ${index + 1}: ${citation.document_name}${citation.page_number ? `, page ${citation.page_number}` : ''}. Click to view in document.`}
        title={`View source: ${citation.document_name}${citation.page_number ? `, p.${citation.page_number}` : ''}`}
      >
        <span className="font-medium">[{index + 1}]</span>
      </button>
    );
  }
  
  return (
    <div 
      className="border border-gray-200 dark:border-gray-700 rounded-lg 
                 bg-white dark:bg-gray-800 overflow-hidden
                 transition-all duration-200"
      role="article"
      aria-labelledby={citationId}
    >
      {/* Header - Always visible */}
      <button
        id={citationId}
        onClick={() => setExpanded(!expanded)}
        onKeyDown={handleKeyDown}
        aria-expanded={expanded}
        aria-controls={contentId}
        className="w-full px-4 py-3 flex items-center gap-3 
                   hover:bg-gray-50 dark:hover:bg-gray-700/50
                   focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500
                   transition-colors text-left"
      >
        {/* Citation number */}
        <span 
          className="flex-shrink-0 w-6 h-6 rounded-full 
                     bg-blue-100 dark:bg-blue-900/50 
                     text-blue-700 dark:text-blue-300
                     flex items-center justify-center text-sm font-medium"
          aria-hidden="true"
        >
          {index + 1}
        </span>
        
        {/* Source info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-base" aria-hidden="true">{getDocumentIcon(citation.document_format)}</span>
            <span className="font-medium text-gray-900 dark:text-white truncate">
              {citation.document_name}
            </span>
            {citation.page_number && (
              <span className="text-sm text-gray-500 dark:text-gray-400 flex-shrink-0">
                p. {citation.page_number}
              </span>
            )}
          </div>
          {citation.section_heading && (
            <div className="text-sm text-gray-500 dark:text-gray-400 truncate mt-0.5">
              § {citation.section_heading}
            </div>
          )}
        </div>
        
        {/* Relevance score */}
        <div 
          className={`flex-shrink-0 text-sm font-medium ${getRelevanceColor(citation.relevance_score)}`}
          aria-label={`${relevancePercent}% relevance`}
        >
          {relevancePercent}%
        </div>
        
        {/* Expand indicator */}
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform duration-200 
                     ${expanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      
      {/* Expanded content */}
      {expanded && (
        <div 
          id={contentId}
          className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700"
          role="region"
          aria-label={`Details for source ${index + 1}`}
        >
          {/* Relevance label */}
          <div className="mt-3 mb-2">
            <span className={`text-xs font-medium ${getRelevanceColor(citation.relevance_score)}`}>
              {getRelevanceLabel(citation.relevance_score)}
            </span>
          </div>
          
          {/* Excerpt */}
          <blockquote 
            className="relative pl-4 pr-2 py-2 
                       border-l-2 border-blue-300 dark:border-blue-600
                       bg-gray-50 dark:bg-gray-900/50 rounded-r
                       text-sm text-gray-700 dark:text-gray-300
                       italic"
            aria-label="Excerpt from source"
          >
            &ldquo;{citation.excerpt}&rdquo;
          </blockquote>
          
          {/* Action button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onViewSource(citation);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                onViewSource(citation);
              }
            }}
            className="mt-3 inline-flex items-center gap-2 px-4 py-2
                       bg-blue-600 hover:bg-blue-700 
                       text-white text-sm font-medium rounded-lg
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                       transition-colors"
            aria-label={`View ${citation.document_name} in document viewer${citation.page_number ? ` at page ${citation.page_number}` : ''}`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            View in Document
          </button>
        </div>
      )}
    </div>
  );
}

export default CitationCard;
