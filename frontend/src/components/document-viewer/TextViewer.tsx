'use client';

import React, { useEffect, useRef, useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HighlightRange {
  startChar: number;
  endChar: number;
}

interface TextViewerProps {
  content: string;
  highlightRanges?: HighlightRange[];
  showLineNumbers?: boolean;
  onLoad?: () => void;
  onError?: (error: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TextViewer({
  content,
  highlightRanges = [],
  showLineNumbers = true,
  onLoad,
  onError,
}: TextViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [lines, setLines] = useState<string[]>([]);
  
  // Split content into lines
  useEffect(() => {
    try {
      const contentLines = content.split('\n');
      setLines(contentLines);
      onLoad?.();
    } catch (e) {
      onError?.('Failed to parse text content');
    }
  }, [content, onLoad, onError]);
  
  // Scroll to first highlight
  useEffect(() => {
    if (highlightRanges.length > 0 && containerRef.current) {
      const firstHighlight = highlightRanges[0];
      // Calculate which line contains the start of the highlight
      let charCount = 0;
      for (let i = 0; i < lines.length; i++) {
        const lineEnd = charCount + lines[i].length + 1; // +1 for newline
        if (firstHighlight.startChar < lineEnd) {
          // Scroll to this line
          const lineElement = containerRef.current.querySelector(`[data-line="${i}"]`);
          lineElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          break;
        }
        charCount = lineEnd;
      }
    }
  }, [highlightRanges, lines]);
  
  // Render text with highlights
  const renderContent = () => {
    if (highlightRanges.length === 0) {
      return lines.map((line, i) => (
        <div key={i} data-line={i} className="flex">
          {showLineNumbers && (
            <span className="select-none text-gray-400 dark:text-gray-600 
                           w-12 pr-4 text-right flex-shrink-0">
              {i + 1}
            </span>
          )}
          <span className="flex-1 whitespace-pre-wrap break-words">
            {line || '\u00A0'}
          </span>
        </div>
      ));
    }
    
    // With highlights - need to track character positions
    let charOffset = 0;
    
    return lines.map((line, lineIndex) => {
      const lineStart = charOffset;
      const lineEnd = charOffset + line.length;
      charOffset = lineEnd + 1; // +1 for newline
      
      // Find highlights that overlap with this line
      const lineHighlights = highlightRanges.filter(
        h => h.startChar < lineEnd && h.endChar > lineStart
      );
      
      if (lineHighlights.length === 0) {
        return (
          <div key={lineIndex} data-line={lineIndex} className="flex">
            {showLineNumbers && (
              <span className="select-none text-gray-400 dark:text-gray-600 
                             w-12 pr-4 text-right flex-shrink-0">
                {lineIndex + 1}
              </span>
            )}
            <span className="flex-1 whitespace-pre-wrap break-words">
              {line || '\u00A0'}
            </span>
          </div>
        );
      }
      
      // Render line with highlights
      const segments: React.ReactNode[] = [];
      let pos = 0;
      
      for (const highlight of lineHighlights) {
        // Calculate local positions within the line
        const highlightStart = Math.max(0, highlight.startChar - lineStart);
        const highlightEnd = Math.min(line.length, highlight.endChar - lineStart);
        
        // Text before highlight
        if (highlightStart > pos) {
          segments.push(
            <span key={`${lineIndex}-${pos}`}>
              {line.slice(pos, highlightStart)}
            </span>
          );
        }
        
        // Highlighted text
        segments.push(
          <mark 
            key={`${lineIndex}-hl-${highlightStart}`}
            className="bg-yellow-200 dark:bg-yellow-800/50 
                      text-gray-900 dark:text-yellow-100 
                      rounded px-0.5"
          >
            {line.slice(highlightStart, highlightEnd)}
          </mark>
        );
        
        pos = highlightEnd;
      }
      
      // Text after last highlight
      if (pos < line.length) {
        segments.push(
          <span key={`${lineIndex}-end`}>
            {line.slice(pos)}
          </span>
        );
      }
      
      return (
        <div key={lineIndex} data-line={lineIndex} className="flex">
          {showLineNumbers && (
            <span className="select-none text-gray-400 dark:text-gray-600 
                           w-12 pr-4 text-right flex-shrink-0">
              {lineIndex + 1}
            </span>
          )}
          <span className="flex-1 whitespace-pre-wrap break-words">
            {segments.length > 0 ? segments : '\u00A0'}
          </span>
        </div>
      );
    });
  };
  
  return (
    <div 
      ref={containerRef}
      className="h-full overflow-auto bg-gray-50 dark:bg-gray-900 
                 font-mono text-sm leading-relaxed p-4"
    >
      {renderContent()}
    </div>
  );
}

export default TextViewer;
