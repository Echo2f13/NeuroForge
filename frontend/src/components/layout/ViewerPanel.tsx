'use client';

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useCitation, ViewerPosition } from '@/contexts/CitationContext';
import { DocumentViewer } from '@/components/document-viewer';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ViewerPanelProps {
  className?: string;
}

// ---------------------------------------------------------------------------
// Hook for screen size detection
// ---------------------------------------------------------------------------

function useScreenSize() {
  const [isMobile, setIsMobile] = useState(false);
  const [isTablet, setIsTablet] = useState(false);

  useEffect(() => {
    const checkSize = () => {
      setIsMobile(window.innerWidth < 640);
      setIsTablet(window.innerWidth >= 640 && window.innerWidth < 1024);
    };
    
    checkSize();
    window.addEventListener('resize', checkSize);
    return () => window.removeEventListener('resize', checkSize);
  }, []);

  return { isMobile, isTablet };
}

// ---------------------------------------------------------------------------
// Hook for swipe-to-dismiss
// ---------------------------------------------------------------------------

interface SwipeHandlers {
  onTouchStart: (e: React.TouchEvent) => void;
  onTouchMove: (e: React.TouchEvent) => void;
  onTouchEnd: (e: React.TouchEvent) => void;
  translateY: number;
  isDragging: boolean;
}

function useSwipeToDismiss(
  onDismiss: () => void,
  enabled: boolean,
  threshold: number = 150
): SwipeHandlers {
  const [translateY, setTranslateY] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const startY = useRef(0);
  const currentY = useRef(0);

  const onTouchStart = useCallback((e: React.TouchEvent) => {
    if (!enabled) return;
    // Only allow swipe from the handle area (top 60px)
    const target = e.target as HTMLElement;
    const rect = target.getBoundingClientRect();
    const touchY = e.touches[0].clientY - rect.top;
    if (touchY > 60) return;
    
    startY.current = e.touches[0].clientY;
    currentY.current = e.touches[0].clientY;
    setIsDragging(true);
  }, [enabled]);

  const onTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isDragging || !enabled) return;
    currentY.current = e.touches[0].clientY;
    const diff = currentY.current - startY.current;
    // Only allow downward swipe
    if (diff > 0) {
      setTranslateY(diff);
    }
  }, [isDragging, enabled]);

  const onTouchEnd = useCallback((e: React.TouchEvent) => {
    if (!isDragging || !enabled) return;
    const diff = currentY.current - startY.current;
    
    if (diff > threshold) {
      // Dismiss with animation
      setTranslateY(window.innerHeight);
      setTimeout(() => {
        onDismiss();
        setTranslateY(0);
      }, 200);
    } else {
      // Snap back
      setTranslateY(0);
    }
    setIsDragging(false);
  }, [isDragging, enabled, threshold, onDismiss]);

  return { onTouchStart, onTouchMove, onTouchEnd, translateY, isDragging };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ViewerPanel({ className = '' }: ViewerPanelProps) {
  const {
    viewerOpen,
    viewerPosition,
    currentDocument,
    currentPage,
    highlightRanges,
    documentLoading,
    documentError,
    closeCitation,
    setCurrentPage,
    setViewerPosition,
  } = useCitation();
  
  const { isMobile, isTablet } = useScreenSize();
  const [isFullscreen, setIsFullscreen] = useState(false);
  
  // Swipe to dismiss for mobile modal
  const swipeHandlers = useSwipeToDismiss(
    closeCitation,
    isMobile && viewerPosition === 'modal',
    100
  );

  // Auto-adjust position for mobile/tablet
  useEffect(() => {
    if (viewerOpen) {
      if (isMobile && viewerPosition !== 'modal') {
        // Mobile always uses modal
        setViewerPosition('modal');
      } else if (isTablet && viewerPosition === 'right') {
        // Tablet defaults to bottom if set to right
        setViewerPosition('bottom');
      }
    }
  }, [isMobile, isTablet, viewerOpen, viewerPosition, setViewerPosition]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && viewerOpen) {
        if (isFullscreen) {
          setIsFullscreen(false);
        } else {
          closeCitation();
        }
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [viewerOpen, isFullscreen, closeCitation]);

  // Lock body scroll on mobile when modal is open
  useEffect(() => {
    if (isMobile && viewerOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [isMobile, viewerOpen]);

  if (!viewerOpen) return null;

  // Position-specific classes - responsive adjustments
  const positionClasses: Record<ViewerPosition, string> = {
    right: 'fixed top-0 right-0 h-full w-full sm:w-[60vw] lg:w-[45vw] max-w-2xl shadow-2xl border-l border-gray-200 dark:border-gray-700 z-50',
    bottom: 'fixed bottom-0 left-0 right-0 h-[60vh] sm:h-[50vh] shadow-2xl border-t border-gray-200 dark:border-gray-700 z-50',
    modal: isFullscreen 
      ? 'fixed inset-0 shadow-2xl z-50'
      : 'fixed inset-0 sm:inset-4 md:inset-8 lg:inset-16 shadow-2xl sm:rounded-2xl border-0 sm:border border-gray-200 dark:border-gray-700 z-50',
  };

  const panelClass = positionClasses[viewerPosition] || positionClasses.right;
  
  // Transform style for swipe animation
  const transformStyle = swipeHandlers.translateY > 0 
    ? { 
        transform: `translateY(${swipeHandlers.translateY}px)`,
        transition: swipeHandlers.isDragging ? 'none' : 'transform 0.2s ease-out'
      }
    : undefined;

  return (
    <>
      {/* Backdrop for modal mode or mobile */}
      {(viewerPosition === 'modal' || isMobile) && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={closeCitation}
          style={{ 
            opacity: swipeHandlers.translateY > 0 
              ? Math.max(0, 1 - swipeHandlers.translateY / 300) 
              : 1 
          }}
        />
      )}
      
      {/* Panel */}
      <div 
        className={`${panelClass} bg-white dark:bg-gray-900 flex flex-col ${className}`}
        style={transformStyle}
        onTouchStart={swipeHandlers.onTouchStart}
        onTouchMove={swipeHandlers.onTouchMove}
        onTouchEnd={swipeHandlers.onTouchEnd}
      >
        {/* Mobile swipe handle indicator */}
        {isMobile && viewerPosition === 'modal' && (
          <div className="flex justify-center py-2 cursor-grab active:cursor-grabbing">
            <div className="w-12 h-1.5 bg-gray-300 dark:bg-gray-600 rounded-full" />
          </div>
        )}
        
        {/* Position toggle and close */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
          {/* Only show position toggles on desktop */}
          <div className="hidden lg:flex items-center gap-1">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              View:
            </span>
            <button
              onClick={() => setViewerPosition('right')}
              className={`p-1.5 rounded transition-colors ${viewerPosition === 'right' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700'}`}
              title="Right sidebar"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
            </button>
            <button
              onClick={() => setViewerPosition('bottom')}
              className={`p-1.5 rounded transition-colors ${viewerPosition === 'bottom' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700'}`}
              title="Bottom panel"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm0 8a1 1 0 011-1h14a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6z" />
              </svg>
            </button>
            <button
              onClick={() => setViewerPosition('modal')}
              className={`p-1.5 rounded transition-colors ${viewerPosition === 'modal' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400' : 'text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700'}`}
              title="Modal"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            </button>
          </div>
          
          {/* Mobile/tablet: show document name */}
          <div className="lg:hidden flex-1 min-w-0">
            {currentDocument && (
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">
                📄 {currentDocument.filename}
              </p>
            )}
          </div>
          
          {/* Action buttons */}
          <div className="flex items-center gap-1">
            {/* Fullscreen toggle (mobile only) */}
            {isMobile && viewerPosition === 'modal' && (
              <button
                onClick={() => setIsFullscreen(!isFullscreen)}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  {isFullscreen ? (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
                  )}
                </svg>
              </button>
            )}
            
            {/* Close button - larger touch target on mobile */}
            <button
              onClick={closeCitation}
              className={`rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors ${isMobile ? 'p-3' : 'p-1.5'}`}
              title="Close viewer"
            >
              <svg className={`text-gray-500 ${isMobile ? 'w-6 h-6' : 'w-5 h-5'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        
        {/* Swipe hint for mobile (shown briefly) */}
        {isMobile && viewerPosition === 'modal' && !isFullscreen && (
          <MobileSwipeHint />
        )}
        
        {/* Document viewer content */}
        <div className="flex-1 overflow-hidden">
          {documentLoading ? (
            <div className="h-full flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm text-gray-500">Loading document...</span>
              </div>
            </div>
          ) : documentError ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center p-4">
                <svg className="w-12 h-12 mx-auto text-red-500 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <p className="text-gray-600 dark:text-gray-400">{documentError}</p>
              </div>
            </div>
          ) : currentDocument ? (
            <DocumentViewer
              document={currentDocument}
              targetPage={currentPage}
              highlightRanges={highlightRanges}
              onClose={closeCitation}
              onPageChange={setCurrentPage}
            />
          ) : (
            <div className="h-full flex items-center justify-center">
              <p className="text-gray-500">No document selected</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Mobile swipe hint component
// ---------------------------------------------------------------------------

function MobileSwipeHint() {
  const [visible, setVisible] = useState(true);
  
  useEffect(() => {
    // Check if user has seen the hint before
    const hasSeenHint = localStorage.getItem('neuroforge_swipe_hint_seen');
    if (hasSeenHint) {
      setVisible(false);
      return;
    }
    
    // Hide after 3 seconds
    const timer = setTimeout(() => {
      setVisible(false);
      localStorage.setItem('neuroforge_swipe_hint_seen', 'true');
    }, 3000);
    
    return () => clearTimeout(timer);
  }, []);
  
  if (!visible) return null;
  
  return (
    <div className="absolute top-16 left-1/2 -translate-x-1/2 z-10 animate-fade-in">
      <div className="bg-gray-900/80 text-white text-sm px-4 py-2 rounded-full flex items-center gap-2">
        <svg className="w-4 h-4 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
        Swipe down to close
      </div>
    </div>
  );
}

export default ViewerPanel;
