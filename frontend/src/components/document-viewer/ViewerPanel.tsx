'use client';

import React, { useEffect, useState } from 'react';
import { useCitation } from '@/contexts/CitationContext';
import { DocumentViewer } from './DocumentViewer';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ViewerPanelProps {
  position?: 'right' | 'bottom' | 'modal';
  width?: string;
  height?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ViewerPanel({
  position: propPosition,
  width = '400px',
  height = '300px',
}: ViewerPanelProps) {
  const {
    viewerOpen,
    viewerPosition,
    currentDocument,
    activeCitation,
    highlightRanges,
    documentLoading,
    documentError,
    closeCitation,
    setCurrentPage,
  } = useCitation();
  
  const [isAnimating, setIsAnimating] = useState(false);
  
  const position = propPosition || viewerPosition;
  
  // Handle animation state
  useEffect(() => {
    if (viewerOpen) {
      setIsAnimating(true);
    }
  }, [viewerOpen]);
  
  const handleAnimationEnd = () => {
    if (!viewerOpen) {
      setIsAnimating(false);
    }
  };
  
  // Don't render if closed and not animating
  if (!viewerOpen && !isAnimating) {
    return null;
  }
  
  // Modal position
  if (position === 'modal') {
    return (
      <div 
        className={`fixed inset-0 z-50 flex items-center justify-center
                   bg-black/50 transition-opacity duration-300
                   ${viewerOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={(e) => {
          if (e.target === e.currentTarget) closeCitation();
        }}
        onTransitionEnd={handleAnimationEnd}
      >
        <div 
          className={`w-[90vw] h-[85vh] max-w-5xl
                     bg-white dark:bg-gray-900 
                     rounded-xl shadow-2xl overflow-hidden
                     transition-transform duration-300
                     ${viewerOpen ? 'scale-100' : 'scale-95'}`}
        >
          {renderContent()}
        </div>
      </div>
    );
  }
  
  // Right panel position
  if (position === 'right') {
    return (
      <div 
        className={`h-full border-l border-gray-200 dark:border-gray-700
                   bg-white dark:bg-gray-900
                   transition-all duration-300 overflow-hidden
                   ${viewerOpen ? 'opacity-100' : 'opacity-0'}`}
        style={{ 
          width: viewerOpen ? width : '0',
          minWidth: viewerOpen ? width : '0',
        }}
        onTransitionEnd={handleAnimationEnd}
      >
        <div className="h-full" style={{ width }}>
          {renderContent()}
        </div>
      </div>
    );
  }
  
  // Bottom panel position
  return (
    <div 
      className={`w-full border-t border-gray-200 dark:border-gray-700
                 bg-white dark:bg-gray-900
                 transition-all duration-300 overflow-hidden
                 ${viewerOpen ? 'opacity-100' : 'opacity-0'}`}
      style={{ 
        height: viewerOpen ? height : '0',
        minHeight: viewerOpen ? height : '0',
      }}
      onTransitionEnd={handleAnimationEnd}
    >
      <div className="h-full" style={{ height }}>
        {renderContent()}
      </div>
    </div>
  );
  
  // Render the viewer content
  function renderContent() {
    if (documentLoading) {
      return (
        <div className="h-full flex items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent 
                           rounded-full animate-spin" />
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Loading document...
            </span>
          </div>
        </div>
      );
    }
    
    if (documentError) {
      return (
        <div className="h-full flex items-center justify-center p-4">
          <div className="text-center">
            <svg className="w-12 h-12 mx-auto text-red-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-gray-600 dark:text-gray-400 mb-2">{documentError}</p>
            <button
              onClick={closeCitation}
              className="text-blue-600 hover:underline"
            >
              Close
            </button>
          </div>
        </div>
      );
    }
    
    if (!currentDocument) {
      return (
        <div className="h-full flex items-center justify-center p-4">
          <div className="text-center text-gray-500 dark:text-gray-400">
            <p>No document selected</p>
          </div>
        </div>
      );
    }
    
    return (
      <DocumentViewer
        document={currentDocument}
        targetPage={activeCitation?.page_number || 1}
        highlightRanges={highlightRanges.map(r => ({
          page: r.page,
          startChar: r.startChar,
          endChar: r.endChar,
          boundingBoxes: r.boundingBoxes?.map(bb => ({
            x0: bb.x0,
            y0: bb.y0,
            x1: bb.x1,
            y1: bb.y1,
          })),
        }))}
        onClose={closeCitation}
        onPageChange={setCurrentPage}
      />
    );
  }
}

export default ViewerPanel;
