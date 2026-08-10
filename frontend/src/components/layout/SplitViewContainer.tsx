'use client';

import React, { ReactNode } from 'react';
import { useCitation } from '@/contexts/CitationContext';
import { ViewerPanel } from './ViewerPanel';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SplitViewContainerProps {
  children: ReactNode;
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SplitViewContainer({ children, className = '' }: SplitViewContainerProps) {
  const { viewerOpen, viewerPosition } = useCitation();

  // When viewer is in right position and open, shrink the main content
  const mainContentClass = viewerOpen && viewerPosition === 'right' 
    ? 'mr-[45vw] max-w-[calc(100%-45vw)]' 
    : viewerOpen && viewerPosition === 'bottom'
    ? 'mb-[50vh]'
    : '';

  return (
    <div className={`relative min-h-screen ${className}`}>
      {/* Main content area */}
      <div className={`transition-all duration-300 ${mainContentClass}`}>
        {children}
      </div>
      
      {/* Viewer panel */}
      <ViewerPanel />
    </div>
  );
}

export default SplitViewContainer;
