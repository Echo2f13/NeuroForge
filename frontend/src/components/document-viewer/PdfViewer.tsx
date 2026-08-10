'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

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
  startChar?: number;
  endChar?: number;
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
  const [numPages, setNumPages] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(targetPage);
  const [scale, setScale] = useState(1.0);
  const [error, setError] = useState<string | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(600);
  const [pdfComponents, setPdfComponents] = useState<{
    Document: any;
    Page: any;
  } | null>(null);

  // Dynamically import react-pdf on mount (client-side only)
  useEffect(() => {
    let mounted = true;
    
    Promise.all([
      import('react-pdf'),
      import('react-pdf/dist/Page/AnnotationLayer.css'),
      import('react-pdf/dist/Page/TextLayer.css'),
    ]).then(([reactPdf]) => {
      if (!mounted) return;
      
      // Configure worker
      reactPdf.pdfjs.GlobalWorkerOptions.workerSrc = 
        `//unpkg.com/pdfjs-dist@${reactPdf.pdfjs.version}/build/pdf.worker.min.mjs`;
      
      setPdfComponents({
        Document: reactPdf.Document,
        Page: reactPdf.Page,
      });
    }).catch((err) => {
      if (!mounted) return;
      console.error('Failed to load react-pdf:', err);
      setError('Failed to load PDF viewer');
      onError?.('Failed to load PDF viewer');
    });
    
    return () => { mounted = false; };
  }, [onError]);

  // Update page when targetPage changes
  useEffect(() => {
    if (targetPage >= 1 && (!numPages || targetPage <= numPages)) {
      setCurrentPage(targetPage);
    }
  }, [targetPage, numPages]);

  // Measure container width for responsive scaling
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width;
      if (width) {
        setContainerWidth(width - 48); // Account for padding
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Notify parent of page changes
  useEffect(() => {
    onPageChange?.(currentPage);
  }, [currentPage, onPageChange]);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setError(null);
    onLoad?.(numPages);
  }, [onLoad]);

  const onDocumentLoadError = useCallback((err: Error) => {
    setError(err.message || 'Failed to load PDF');
    onError?.(err.message || 'Failed to load PDF');
  }, [onError]);

  const goToPage = useCallback((page: number) => {
    if (numPages) {
      setCurrentPage(Math.max(1, Math.min(page, numPages)));
    }
  }, [numPages]);

  const zoomIn = useCallback(() => {
    setScale((s) => Math.min(3, s + 0.25));
  }, []);

  const zoomOut = useCallback(() => {
    setScale((s) => Math.max(0.5, s - 0.25));
  }, []);

  const fitToWidth = useCallback(() => {
    setScale(1.0);
  }, []);

  // Get highlights for current page
  const currentHighlights = highlightRanges.filter((h) => h.page === currentPage);

  return (
    <div className="h-full flex flex-col bg-gray-100 dark:bg-gray-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
        {/* Page navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
              onChange={(e) => goToPage(parseInt(e.target.value) || 1)}
              className="w-12 px-2 py-1 text-center border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              min={1}
              max={numPages || 1}
            />
            <span className="text-gray-500 dark:text-gray-400">/ {numPages || '?'}</span>
          </div>

          <button
            onClick={() => goToPage(currentPage + 1)}
            disabled={!numPages || currentPage >= numPages}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
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
            onClick={zoomOut}
            disabled={scale <= 0.5}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
            aria-label="Zoom out"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
            </svg>
          </button>

          <button
            onClick={fitToWidth}
            className="px-2 py-1 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors min-w-[4rem] text-center"
            title="Fit to width"
          >
            {Math.round(scale * 100)}%
          </button>

          <button
            onClick={zoomIn}
            disabled={scale >= 3}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
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
          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          aria-label="Download PDF"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
        </a>
      </div>

      {/* PDF display area */}
      <div ref={containerRef} className="flex-1 overflow-auto p-6">
        {error ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center p-4">
              <svg className="w-12 h-12 mx-auto text-red-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-gray-600 dark:text-gray-400 mb-2">{error}</p>
              <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                Open in new tab
              </a>
            </div>
          </div>
        ) : !pdfComponents ? (
          <div className="flex flex-col items-center gap-2 py-12">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-gray-500 dark:text-gray-400">Initializing PDF viewer...</span>
          </div>
        ) : (
          <div className="flex justify-center">
            <pdfComponents.Document
              file={url}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading={
                <div className="flex flex-col items-center gap-2 py-12">
                  <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm text-gray-500 dark:text-gray-400">Loading PDF...</span>
                </div>
              }
              className="pdf-document"
            >
              <div className="relative inline-block shadow-lg">
                <pdfComponents.Page
                  pageNumber={currentPage}
                  scale={scale}
                  width={containerWidth}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  loading={
                    <div className="flex items-center justify-center p-12 bg-white">
                      <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                  }
                />

                {/* Highlight overlays */}
                {currentHighlights.map((highlight, idx) =>
                  highlight.boundingBoxes?.map((bbox, bboxIdx) => (
                    <div
                      key={`${idx}-${bboxIdx}`}
                      className="absolute bg-yellow-300/40 border-2 border-yellow-400/60 rounded-sm pointer-events-none animate-pulse"
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
            </pdfComponents.Document>
          </div>
        )}
      </div>

      {/* Page indicator for mobile */}
      {numPages && numPages > 1 && (
        <div className="sm:hidden flex justify-center py-2 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
          <span className="text-sm text-gray-500">
            Page {currentPage} of {numPages}
          </span>
        </div>
      )}
    </div>
  );
}

export default PdfViewer;
