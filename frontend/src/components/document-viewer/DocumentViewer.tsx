'use client';

import React, { useState, useEffect } from 'react';
import { StoredDocument } from '@/lib/api';
import api from '@/lib/api';
import { PdfViewer } from './PdfViewer';
import { TextViewer } from './TextViewer';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HighlightRange {
  page: number;
  startChar: number;
  endChar: number;
  boundingBoxes?: Array<{
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  }>;
}

interface DocumentViewerProps {
  document: StoredDocument;
  targetPage?: number;
  highlightRanges?: HighlightRange[];
  onClose: () => void;
  onPageChange?: (page: number) => void;
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function getFormatDisplayName(format: string): string {
  const formats: Record<string, string> = {
    pdf: 'PDF Document',
    docx: 'Word Document',
    txt: 'Text File',
    text: 'Text File',
    markdown: 'Markdown File',
    md: 'Markdown File',
    pptx: 'PowerPoint',
    image: 'Image',
  };
  return formats[format.toLowerCase()] || 'Document';
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentViewer({
  document,
  targetPage = 1,
  highlightRanges = [],
  onClose,
  onPageChange,
}: DocumentViewerProps) {
  const [currentPage, setCurrentPage] = useState(targetPage);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  
  const documentUrl = api.getDocumentFileUrl(document.subject_id, document.id);
  const format = document.format.toLowerCase();
  const isTextBased = ['txt', 'text', 'markdown', 'md'].includes(format);
  
  // Load text content for text-based documents
  useEffect(() => {
    if (isTextBased) {
      setLoading(true);
      fetch(documentUrl)
        .then(res => {
          if (!res.ok) throw new Error('Failed to load document');
          return res.text();
        })
        .then(text => {
          setTextContent(text);
          setLoading(false);
        })
        .catch(err => {
          setError(err.message);
          setLoading(false);
        });
    }
  }, [documentUrl, isTextBased]);
  
  useEffect(() => {
    setCurrentPage(targetPage);
  }, [targetPage]);
  
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    onPageChange?.(page);
  };
  
  // Render the appropriate viewer
  const renderViewer = () => {
    if (loading) {
      return (
        <div className="flex-1 flex items-center justify-center">
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
    
    if (error) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center p-4">
            <svg className="w-12 h-12 mx-auto text-red-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p className="text-gray-600 dark:text-gray-400">{error}</p>
            <button
              onClick={() => window.open(documentUrl, '_blank')}
              className="mt-2 text-blue-600 hover:underline"
            >
              Try opening in new tab
            </button>
          </div>
        </div>
      );
    }
    
    switch (format) {
      case 'pdf':
        return (
          <PdfViewer
            url={documentUrl}
            targetPage={currentPage}
            highlightRanges={highlightRanges}
            onPageChange={handlePageChange}
            onError={setError}
          />
        );
      
      case 'txt':
      case 'text':
      case 'markdown':
      case 'md':
        if (textContent) {
          return (
            <TextViewer
              content={textContent}
              highlightRanges={highlightRanges.map(h => ({
                startChar: h.startChar,
                endChar: h.endChar,
              }))}
              showLineNumbers={true}
            />
          );
        }
        return null;
      
      case 'docx':
        // DOCX would need mammoth.js for proper rendering
        // For now, show a message to download
        return (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="text-center max-w-md">
              <svg className="w-16 h-16 mx-auto text-blue-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                Word Document
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                This document is in Word format. Download it to view the full content with formatting.
              </p>
              <a
                href={documentUrl}
                download={document.filename}
                className="inline-flex items-center gap-2 px-4 py-2
                          bg-blue-600 hover:bg-blue-700
                          text-white font-medium rounded-lg
                          transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download Document
              </a>
            </div>
          </div>
        );
      
      default:
        return (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="text-center">
              <p className="text-gray-600 dark:text-gray-400 mb-4">
                Preview not available for this format.
              </p>
              <a
                href={documentUrl}
                download={document.filename}
                className="text-blue-600 hover:underline"
              >
                Download file
              </a>
            </div>
          </div>
        );
    }
  };
  
  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 
                     border-b border-gray-200 dark:border-gray-700
                     bg-gray-50 dark:bg-gray-800">
        <div className="flex items-center gap-3 min-w-0">
          {/* Document icon */}
          <span className="text-2xl flex-shrink-0">📄</span>
          
          <div className="min-w-0">
            <h3 className="font-medium text-gray-900 dark:text-white truncate">
              {document.filename}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {getFormatDisplayName(document.format)}
              {document.total_pages && ` • ${document.total_pages} pages`}
              {' • '}
              {formatFileSize(document.file_size)}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Download button */}
          <a
            href={documentUrl}
            download={document.filename}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700
                      transition-colors"
            aria-label="Download document"
          >
            <svg className="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </a>
          
          {/* Close button */}
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700
                      transition-colors"
            aria-label="Close viewer"
          >
            <svg className="w-5 h-5 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
      
      {/* Viewer content */}
      <div className="flex-1 overflow-hidden">
        {renderViewer()}
      </div>
    </div>
  );
}

export default DocumentViewer;
