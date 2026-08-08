'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Citation } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CitationBadgeProps {
  citation: Citation;
  index: number;
  onViewSource: (citation: Citation) => void;
  showPreview?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CitationBadge({
  citation,
  index,
  onViewSource,
  showPreview = true,
}: CitationBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState<'top' | 'bottom'>('top');
  const badgeRef = useRef<HTMLButtonElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  
  // Determine tooltip position based on available space
  useEffect(() => {
    if (showTooltip && badgeRef.current) {
      const rect = badgeRef.current.getBoundingClientRect();
      const spaceAbove = rect.top;
      const spaceBelow = window.innerHeight - rect.bottom;
      
      // Show tooltip below if not enough space above
      setTooltipPosition(spaceAbove < 200 ? 'bottom' : 'top');
    }
  }, [showTooltip]);
  
  // Close tooltip on click outside
  useEffect(() => {
    if (!showTooltip) return;
    
    const handleClickOutside = (e: MouseEvent) => {
      if (
        tooltipRef.current &&
        !tooltipRef.current.contains(e.target as Node) &&
        badgeRef.current &&
        !badgeRef.current.contains(e.target as Node)
      ) {
        setShowTooltip(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showTooltip]);
  
  const handleClick = () => {
    if (showPreview) {
      setShowTooltip(!showTooltip);
    } else {
      onViewSource(citation);
    }
  };
  
  return (
    <span className="relative inline-block">
      <button
        ref={badgeRef}
        onClick={handleClick}
        onMouseEnter={() => showPreview && setShowTooltip(true)}
        onMouseLeave={() => showPreview && setShowTooltip(false)}
        className="inline-flex items-center justify-center
                   min-w-[1.25rem] h-5 px-1
                   text-xs font-medium
                   bg-blue-100 dark:bg-blue-900/40
                   text-blue-700 dark:text-blue-300
                   rounded hover:bg-blue-200 dark:hover:bg-blue-800/60
                   transition-colors cursor-pointer
                   align-super"
        aria-label={`Citation ${index + 1}: ${citation.document_name}`}
      >
        {index + 1}
      </button>
      
      {/* Tooltip/Preview */}
      {showPreview && showTooltip && (
        <div
          ref={tooltipRef}
          className={`absolute z-50 w-72 p-3
                     bg-white dark:bg-gray-800
                     border border-gray-200 dark:border-gray-700
                     rounded-lg shadow-lg
                     ${tooltipPosition === 'top' 
                       ? 'bottom-full mb-2' 
                       : 'top-full mt-2'}
                     left-1/2 -translate-x-1/2`}
        >
          {/* Arrow */}
          <div 
            className={`absolute left-1/2 -translate-x-1/2 w-2 h-2
                       bg-white dark:bg-gray-800
                       border-gray-200 dark:border-gray-700
                       transform rotate-45
                       ${tooltipPosition === 'top'
                         ? 'bottom-0 translate-y-1/2 border-r border-b'
                         : 'top-0 -translate-y-1/2 border-l border-t'}`}
          />
          
          {/* Content */}
          <div className="relative">
            {/* Document name */}
            <div className="flex items-center gap-2 mb-2">
              <span className="text-base">📄</span>
              <span className="font-medium text-sm text-gray-900 dark:text-white truncate">
                {citation.document_name}
              </span>
            </div>
            
            {/* Page info */}
            {citation.page_number && (
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                Page {citation.page_number}
                {citation.section_heading && ` • ${citation.section_heading}`}
              </div>
            )}
            
            {/* Excerpt */}
            <p className="text-xs text-gray-600 dark:text-gray-300 
                         line-clamp-3 italic mb-3">
              &ldquo;{citation.excerpt}&rdquo;
            </p>
            
            {/* View button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setShowTooltip(false);
                onViewSource(citation);
              }}
              className="w-full py-1.5 text-xs font-medium
                        bg-blue-600 hover:bg-blue-700
                        text-white rounded
                        transition-colors"
            >
              View in Document →
            </button>
          </div>
        </div>
      )}
    </span>
  );
}

export default CitationBadge;
