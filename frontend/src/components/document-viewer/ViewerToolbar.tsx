'use client';

import React from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ViewerToolbarProps {
  documentName: string;
  documentFormat: string;
  currentPage?: number;
  totalPages?: number;
  zoom?: number;
  onPageChange?: (page: number) => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onZoomReset?: () => void;
  onDownload?: () => void;
  onClose?: () => void;
  downloadUrl?: string;
  showPageControls?: boolean;
  showZoomControls?: boolean;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function getDocumentIcon(format: string): string {
  switch (format.toLowerCase()) {
    case 'pdf':
      return '📄';
    case 'docx':
    case 'doc':
      return '📝';
    case 'txt':
    case 'text':
      return '📃';
    case 'md':
    case 'markdown':
      return '📋';
    case 'pptx':
    case 'ppt':
      return '📊';
    default:
      return '📄';
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ViewerToolbar({
  documentName,
  documentFormat,
  currentPage,
  totalPages,
  zoom = 100,
  onPageChange,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onDownload,
  onClose,
  downloadUrl,
  showPageControls = true,
  showZoomControls = true,
  className = '',
}: ViewerToolbarProps) {
  const hasPageControls = showPageControls && totalPages && totalPages > 1;
  const hasZoomControls = showZoomControls && (onZoomIn || onZoomOut);

  return (
    <div
      className={`flex items-center justify-between px-4 py-2 
                  bg-white dark:bg-gray-800 
                  border-b border-gray-200 dark:border-gray-700 
                  ${className}`}
    >
      {/* Left: Document info */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="text-xl flex-shrink-0" aria-hidden="true">
          {getDocumentIcon(documentFormat)}
        </span>
        <div className="min-w-0">
          <h3 className="font-medium text-gray-900 dark:text-white truncate text-sm">
            {documentName}
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 uppercase">
            {documentFormat}
          </p>
        </div>
      </div>

      {/* Center: Page navigation */}
      {hasPageControls && (
        <div className="flex items-center gap-2 mx-4">
          <button
            onClick={() => onPageChange?.(Math.max(1, (currentPage || 1) - 1))}
            disabled={!currentPage || currentPage <= 1}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 
                      disabled:opacity-50 disabled:cursor-not-allowed 
                      transition-colors"
            aria-label="Previous page"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>

          <div className="flex items-center gap-1 text-sm">
            <input
              type="number"
              value={currentPage || 1}
              onChange={(e) => {
                const page = parseInt(e.target.value) || 1;
                onPageChange?.(Math.max(1, Math.min(page, totalPages || 1)));
              }}
              className="w-10 px-1 py-0.5 text-center text-sm
                        border border-gray-300 dark:border-gray-600 
                        rounded bg-white dark:bg-gray-700 
                        text-gray-900 dark:text-white"
              min={1}
              max={totalPages}
              aria-label="Current page"
            />
            <span className="text-gray-500 dark:text-gray-400">/ {totalPages}</span>
          </div>

          <button
            onClick={() => onPageChange?.(Math.min(totalPages || 1, (currentPage || 1) + 1))}
            disabled={!currentPage || !totalPages || currentPage >= totalPages}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 
                      disabled:opacity-50 disabled:cursor-not-allowed 
                      transition-colors"
            aria-label="Next page"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}

      {/* Right: Zoom and actions */}
      <div className="flex items-center gap-2">
        {hasZoomControls && (
          <>
            <button
              onClick={onZoomOut}
              disabled={zoom <= 50}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 
                        disabled:opacity-50 transition-colors"
              aria-label="Zoom out"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
              </svg>
            </button>

            <button
              onClick={onZoomReset}
              className="px-2 py-0.5 text-xs text-gray-600 dark:text-gray-400 
                        hover:bg-gray-100 dark:hover:bg-gray-700 
                        rounded transition-colors min-w-[3rem] text-center"
              title="Reset zoom"
            >
              {zoom}%
            </button>

            <button
              onClick={onZoomIn}
              disabled={zoom >= 300}
              className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 
                        disabled:opacity-50 transition-colors"
              aria-label="Zoom in"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </button>

            <div className="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1" />
          </>
        )}

        {/* Download button */}
        {(downloadUrl || onDownload) && (
          <a
            href={downloadUrl}
            download
            onClick={onDownload ? (e) => { e.preventDefault(); onDownload(); } : undefined}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Download document"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </a>
        )}

        {/* Close button */}
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label="Close viewer"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}

export default ViewerToolbar;
