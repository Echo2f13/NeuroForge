'use client';

import React, { useState, useEffect, useRef } from 'react';
import mammoth from 'mammoth';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HighlightRange {
  startChar: number;
  endChar: number;
}

interface DocxViewerProps {
  url: string;
  highlightRanges?: HighlightRange[];
  onLoad?: () => void;
  onError?: (error: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocxViewer({
  url,
  highlightRanges = [],
  onLoad,
  onError,
}: DocxViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [htmlContent, setHtmlContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rawText, setRawText] = useState<string>('');

  // Load and convert DOCX to HTML
  useEffect(() => {
    let mounted = true;

    const loadDocument = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch the document
        const response = await fetch(url);
        if (!response.ok) {
          throw new Error(`Failed to fetch document: ${response.statusText}`);
        }

        const arrayBuffer = await response.arrayBuffer();

        // Convert to HTML using mammoth
        const result = await mammoth.convertToHtml(
          { arrayBuffer },
          {
            styleMap: [
              "p[style-name='Heading 1'] => h1:fresh",
              "p[style-name='Heading 2'] => h2:fresh",
              "p[style-name='Heading 3'] => h3:fresh",
              "b => strong",
              "i => em",
              "u => u",
            ],
          }
        );

        // Also get raw text for highlighting
        const textResult = await mammoth.extractRawText({ arrayBuffer });

        if (mounted) {
          setHtmlContent(result.value);
          setRawText(textResult.value);
          setLoading(false);
          onLoad?.();

          // Log any warnings
          if (result.messages.length > 0) {
            console.warn('Mammoth warnings:', result.messages);
          }
        }
      } catch (err) {
        if (mounted) {
          const message = err instanceof Error ? err.message : 'Failed to load document';
          setError(message);
          setLoading(false);
          onError?.(message);
        }
      }
    };

    loadDocument();

    return () => {
      mounted = false;
    };
  }, [url, onLoad, onError]);

  // Scroll to highlighted content
  useEffect(() => {
    if (highlightRanges.length > 0 && containerRef.current && htmlContent) {
      // For DOCX, we'd need to map character offsets to the rendered HTML
      // This is a simplified version - for full support, you'd need to
      // track text positions during the mammoth conversion
      const highlightedElement = containerRef.current.querySelector('.docx-highlight');
      highlightedElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightRanges, htmlContent]);

  // Apply highlights to HTML content
  const applyHighlights = (html: string): string => {
    if (highlightRanges.length === 0 || !rawText) {
      return html;
    }

    // This is a simplified implementation
    // For proper highlighting, you'd need to:
    // 1. Parse the HTML into a DOM
    // 2. Track text positions across elements
    // 3. Insert highlight spans at the correct positions
    
    // For now, we'll add a class to indicate highlighting is needed
    // A full implementation would require more complex DOM manipulation
    return html;
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-gray-500 dark:text-gray-400">Loading document...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center bg-white dark:bg-gray-900">
        <div className="text-center p-8 max-w-md">
          <svg className="w-16 h-16 mx-auto text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Failed to Load Document
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-4">{error}</p>
          <a
            href={url}
            download
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Download Instead
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white dark:bg-gray-900">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>Word Document</span>
        </div>

        <a
          href={url}
          download
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Download
        </a>
      </div>

      {/* Document content */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-8 max-w-4xl mx-auto w-full"
      >
        <div
          className="docx-content prose prose-sm sm:prose lg:prose-lg dark:prose-invert max-w-none
                     prose-headings:text-gray-900 dark:prose-headings:text-white
                     prose-p:text-gray-700 dark:prose-p:text-gray-300
                     prose-strong:text-gray-900 dark:prose-strong:text-white
                     prose-a:text-blue-600 dark:prose-a:text-blue-400"
          dangerouslySetInnerHTML={{ __html: htmlContent || '' }}
        />
      </div>

      {/* Note about formatting */}
      <div className="px-4 py-2 bg-yellow-50 dark:bg-yellow-900/20 border-t border-yellow-200 dark:border-yellow-800 text-center">
        <p className="text-xs text-yellow-700 dark:text-yellow-300">
          📝 Some formatting may differ from the original. Download for full fidelity.
        </p>
      </div>
    </div>
  );
}

export default DocxViewer;
