'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { Citation, StoredDocument } from '@/lib/api';
import api from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ViewerPosition = 'right' | 'bottom' | 'modal';

export interface HighlightRange {
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

interface CitationContextValue {
  // Citation state
  activeCitation: Citation | null;
  citations: Citation[];
  
  // Viewer state
  viewerOpen: boolean;
  viewerPosition: ViewerPosition;
  
  // Document state
  currentDocument: StoredDocument | null;
  currentPage: number;
  highlightRanges: HighlightRange[];
  documentLoading: boolean;
  documentError: string | null;
  
  // Actions
  openCitation: (citation: Citation, subjectId?: string) => Promise<void>;
  closeCitation: () => void;
  setCitations: (citations: Citation[]) => void;
  clearCitations: () => void;
  setViewerPosition: (position: ViewerPosition) => void;
  setCurrentPage: (page: number) => void;
  toggleViewer: () => void;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const CitationContext = createContext<CitationContextValue | undefined>(undefined);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface CitationProviderProps {
  children: ReactNode;
  defaultPosition?: ViewerPosition;
}

export function CitationProvider({ 
  children, 
  defaultPosition = 'right' 
}: CitationProviderProps) {
  // Citation state
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [citations, setCitationsState] = useState<Citation[]>([]);
  
  // Viewer state
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerPosition, setViewerPositionState] = useState<ViewerPosition>(defaultPosition);
  
  // Document state
  const [currentDocument, setCurrentDocument] = useState<StoredDocument | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [highlightRanges, setHighlightRanges] = useState<HighlightRange[]>([]);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [documentError, setDocumentError] = useState<string | null>(null);
  
  // Load persisted viewer position
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('neuroforge-viewer-position');
      if (saved && ['right', 'bottom', 'modal'].includes(saved)) {
        setViewerPositionState(saved as ViewerPosition);
      }
    }
  }, []);
  
  // Persist viewer position
  const setViewerPosition = useCallback((position: ViewerPosition) => {
    setViewerPositionState(position);
    if (typeof window !== 'undefined') {
      localStorage.setItem('neuroforge-viewer-position', position);
    }
  }, []);
  
  // Open a citation and load its document
  const openCitation = useCallback(async (citation: Citation, subjectId?: string) => {
    setActiveCitation(citation);
    setDocumentError(null);
    
    // Set highlight ranges from citation
    const ranges: HighlightRange[] = [];
    if (citation.page_number) {
      ranges.push({
        page: citation.page_number,
        startChar: citation.start_char,
        endChar: citation.end_char,
        boundingBoxes: citation.bounding_boxes?.map(bb => ({
          x0: bb.x0,
          y0: bb.y0,
          x1: bb.x1,
          y1: bb.y1,
        })),
      });
    }
    setHighlightRanges(ranges);
    
    // Set page to citation's page
    if (citation.page_number) {
      setCurrentPage(citation.page_number);
    }
    
    // Load document metadata if not already loaded
    const effectiveSubjectId = subjectId || 'general';
    
    if (!currentDocument || currentDocument.id !== citation.document_id) {
      setDocumentLoading(true);
      try {
        const response = await api.getDocumentMetadata(effectiveSubjectId, citation.document_id);
        setCurrentDocument(response.document);
      } catch (error) {
        console.error('Failed to load document metadata:', error);
        setDocumentError('Failed to load document');
        // Still open viewer to show error
      } finally {
        setDocumentLoading(false);
      }
    }
    
    setViewerOpen(true);
  }, [currentDocument]);
  
  // Close citation viewer
  const closeCitation = useCallback(() => {
    setViewerOpen(false);
    // Don't clear citation immediately for animation
    setTimeout(() => {
      setActiveCitation(null);
      setHighlightRanges([]);
    }, 300);
  }, []);
  
  // Set citations list
  const setCitations = useCallback((newCitations: Citation[]) => {
    setCitationsState(newCitations);
  }, []);
  
  // Clear all citations
  const clearCitations = useCallback(() => {
    setCitationsState([]);
    setActiveCitation(null);
    setViewerOpen(false);
    setCurrentDocument(null);
    setHighlightRanges([]);
  }, []);
  
  // Toggle viewer
  const toggleViewer = useCallback(() => {
    setViewerOpen(prev => !prev);
  }, []);
  
  const value: CitationContextValue = {
    activeCitation,
    citations,
    viewerOpen,
    viewerPosition,
    currentDocument,
    currentPage,
    highlightRanges,
    documentLoading,
    documentError,
    openCitation,
    closeCitation,
    setCitations,
    clearCitations,
    setViewerPosition,
    setCurrentPage,
    toggleViewer,
  };
  
  return (
    <CitationContext.Provider value={value}>
      {children}
    </CitationContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCitation() {
  const context = useContext(CitationContext);
  if (context === undefined) {
    throw new Error('useCitation must be used within a CitationProvider');
  }
  return context;
}

export default CitationContext;
