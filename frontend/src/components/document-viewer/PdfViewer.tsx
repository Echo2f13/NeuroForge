'use client';

import React, { useState, useEffect, useRef } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BoundingBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

interface HighlightRange {
  page: number;
  boundingBoxes?: BoundingBox[];
}

interface PdfViewerProps {
  url: string;
  targetPage?: number;
  highlightRanges?: HighlightRange[];
  onLoad?: (numPages: number) => void;
  onError?: (error: string) => void;
  onPageChange?: (page: number) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PdfViewer({
  url,
  targetPage = 1,
  highlightRanges = [],
  onLoad,
  onError,
  onPageChange,
}: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [currentPage, setCurrentPage] = useState(targetPage);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [scale, setScale] = useState(1.0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // For this implementation, we'll use an iframe with the browser's native PDF viewer
  // For a full implementation, you would use react-pdf or PDF.js
  
  useEffect(() => {
    setCurrentPage(targetPage);
  }, [targetPage]);
  
  useEffect(() => {
    onPageChange?.(currentPage);
  }, [currentPage, onPageChange]);
  
  // Get highlights for current page
  const currentHighlights = highlightRanges.filter(h => h.page === currentPage);
  
  const handleIframeLoad = () => {
    setLoading(false);
    // Note: Can't reliably get page count from iframe
    onLoad?.(1);
  };
  
  const handleIframeError = () => {
    setLoading(false);
    setError('Failed to load PDF');
    onError?.('Failed to load PDF');
  };
  
  // Construct URL with page parameter
  const pdfUrl = `${url}#page=${currentPage}`;
  
  return (
    <div className="h-full flex flex-col bg-gray-100 dark:bg-gray-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 
                     bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        {/* Page navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700
                      disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Previous page"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          
          <div className="flex items-center gap-1 text-sm">
            <input
              type="number"
              value={currentPage}
              onChange={(e) => {
                const page = parseInt(e.target.value) || 1;
                setCurrentPage(Math.max(1, page));
              }}
              className="w-12 px-2 py-1 text-center border border-gray-300 dark:border-gray-600
                        rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              min={1}
            />
            {numPages && (
              <span className="text-gray-500 dark:text-gray-400">
                / {numPages}
              </span>
            )}
          </div>
          
          <button
            onClick={() => setCurrentPage(p => p + 1)}
            disabled={numPages !== null && currentPage >= numPages}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700
                      disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Next page"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
        
        {/* Zoom controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="Zoom out"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>
          
          <span className="text-sm text-gray-600 dark:text-gray-400 min-w-[4rem] text-center">
            {Math.round(scale * 100)}%
          </span>
          
          <button
            onClick={() => setScale(s => Math.min(2, s + 0.1))}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
            aria-label="Zoom in"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
        
        {/* Download button */}
        <a
          href={url}
          download
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Download PDF"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </a>
      </div>
      
      {/* PDF display area */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-auto relative"
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center 
                         bg-gray-100 dark:bg-gray-900">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent 
                             rounded-full animate-spin" />
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Loading PDF...
              </span>
            </div>
          </div>
        )}
        
        {error ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center p-4">
              <svg className="w-12 h-12 mx-auto text-red-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-gray-600 dark:text-gray-400">{error}</p>
              <a 
                href={url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="mt-2 inline-block text-blue-600 hover:underline"
              >
                Open in new tab
              </a>
            </div>
          </div>
        ) : (
          <div 
            className="h-full"
            style={{ 
              transform: `scale(${scale})`,
              transformOrigin: 'top left',
              width: `${100 / scale}%`,
              height: `${100 / scale}%`,
            }}
          >
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              onLoad={handleIframeLoad}
              onError={handleIframeError}
              title="PDF Document"
            />
            
            {/* Highlight overlay - for bounding boxes */}
            {currentHighlights.length > 0 && (
              <div className="absolute inset-0 pointer-events-none">
                {currentHighlights.map((highlight, idx) =>
                  highlight.boundingBoxes?.map((bbox, bboxIdx) => (
                    <div
                      key={`${idx}-${bboxIdx}`}
                      className="absolute bg-yellow-300/40 border border-yellow-500/50"
                      style={{
                        left: `${bbox.x0}%`,
                        top: `${bbox.y0}%`,
                        width: `${bbox.x1 - bbox.x0}%`,
                        height: `${bbox.y1 - bbox.y0}%`,
                      }}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default PdfViewer;
