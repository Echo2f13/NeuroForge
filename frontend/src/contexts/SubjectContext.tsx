'use client';

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import api, { Subject, SubjectSummary, CreateSubjectInput, UpdateSubjectInput, SubjectStats } from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SubjectState {
  subjects: SubjectSummary[];
  activeSubjectId: string;
  activeSubject: Subject | null;
  loading: boolean;
  isCreating: boolean;
  isDeleting: boolean;
  isSwitching: boolean;
  error: string | null;
}

interface SubjectActions {
  loadSubjects: (includeArchived?: boolean) => Promise<void>;
  setActiveSubject: (subjectId: string) => Promise<void>;
  createSubject: (data: CreateSubjectInput) => Promise<Subject>;
  updateSubject: (subjectId: string, data: UpdateSubjectInput) => Promise<Subject>;
  deleteSubject: (subjectId: string, force?: boolean) => Promise<void>;
  archiveSubject: (subjectId: string) => Promise<Subject>;
  restoreSubject: (subjectId: string) => Promise<Subject>;
  refreshActiveSubject: () => Promise<void>;
  getSubjectStats: (subjectId: string) => Promise<SubjectStats>;
  clearError: () => void;
}

interface SubjectContextValue extends SubjectState, SubjectActions {}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'neuroforge_active_subject';
const DEFAULT_SUBJECT_ID = 'general';

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const SubjectContext = createContext<SubjectContextValue | undefined>(undefined);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface SubjectProviderProps {
  children: ReactNode;
}

export function SubjectProvider({ children }: SubjectProviderProps) {
  const [state, setState] = useState<SubjectState>({
    subjects: [],
    activeSubjectId: DEFAULT_SUBJECT_ID,
    activeSubject: null,
    loading: true,
    isCreating: false,
    isDeleting: false,
    isSwitching: false,
    error: null,
  });

  // Load active subject from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      setState(prev => ({ ...prev, activeSubjectId: stored }));
    }
  }, []);

  // Persist active subject to localStorage
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, state.activeSubjectId);
  }, [state.activeSubjectId]);

  // Load subjects on mount
  useEffect(() => {
    loadSubjects();
  }, []);

  // Load active subject details when activeSubjectId changes
  useEffect(() => {
    if (state.activeSubjectId) {
      refreshActiveSubject();
    }
  }, [state.activeSubjectId]);

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const loadSubjects = useCallback(async (includeArchived = false) => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await api.listSubjects(includeArchived);
      setState(prev => ({
        ...prev,
        subjects: response.subjects,
        loading: false,
      }));
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load subjects',
      }));
    }
  }, []);

  const setActiveSubject = useCallback(async (subjectId: string) => {
    setState(prev => ({ ...prev, activeSubjectId: subjectId, isSwitching: true }));
    
    try {
      const response = await api.getSubject(subjectId);
      setState(prev => ({
        ...prev,
        activeSubject: response.subject,
        isSwitching: false,
      }));
    } catch (err) {
      setState(prev => ({
        ...prev,
        isSwitching: false,
        error: err instanceof Error ? err.message : 'Failed to load subject',
      }));
    }
  }, []);

  const refreshActiveSubject = useCallback(async () => {
    if (!state.activeSubjectId) return;
    
    try {
      const response = await api.getSubject(state.activeSubjectId);
      setState(prev => ({
        ...prev,
        activeSubject: response.subject,
      }));
    } catch (err) {
      // If subject not found, fallback to default
      if (state.activeSubjectId !== DEFAULT_SUBJECT_ID) {
        setState(prev => ({
          ...prev,
          activeSubjectId: DEFAULT_SUBJECT_ID,
        }));
      }
    }
  }, [state.activeSubjectId]);

  const createSubject = useCallback(async (data: CreateSubjectInput): Promise<Subject> => {
    setState(prev => ({ ...prev, isCreating: true, error: null }));
    
    try {
      const response = await api.createSubject(data);
      await loadSubjects();
      setState(prev => ({ ...prev, isCreating: false }));
      return response.subject;
    } catch (err) {
      setState(prev => ({
        ...prev,
        isCreating: false,
        error: err instanceof Error ? err.message : 'Failed to create subject',
      }));
      throw err;
    }
  }, [loadSubjects]);

  const updateSubject = useCallback(async (subjectId: string, data: UpdateSubjectInput): Promise<Subject> => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await api.updateSubject(subjectId, data);
      await loadSubjects();
      
      // Refresh active subject if it was updated
      if (subjectId === state.activeSubjectId) {
        setState(prev => ({ ...prev, activeSubject: response.subject }));
      }
      
      return response.subject;
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to update subject',
      }));
      throw err;
    }
  }, [loadSubjects, state.activeSubjectId]);

  const deleteSubject = useCallback(async (subjectId: string, force = false) => {
    setState(prev => ({ ...prev, isDeleting: true, error: null }));
    
    try {
      await api.deleteSubject(subjectId, force);
      await loadSubjects();
      
      // Switch to default if deleted subject was active
      if (subjectId === state.activeSubjectId) {
        setState(prev => ({
          ...prev,
          activeSubjectId: DEFAULT_SUBJECT_ID,
          isDeleting: false,
        }));
      } else {
        setState(prev => ({ ...prev, isDeleting: false }));
      }
    } catch (err) {
      setState(prev => ({
        ...prev,
        isDeleting: false,
        error: err instanceof Error ? err.message : 'Failed to delete subject',
      }));
      throw err;
    }
  }, [loadSubjects, state.activeSubjectId]);

  const archiveSubject = useCallback(async (subjectId: string): Promise<Subject> => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await api.archiveSubject(subjectId);
      await loadSubjects();
      
      // Switch to default if archived subject was active
      if (subjectId === state.activeSubjectId) {
        setState(prev => ({
          ...prev,
          activeSubjectId: DEFAULT_SUBJECT_ID,
        }));
      }
      
      return response.subject;
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to archive subject',
      }));
      throw err;
    }
  }, [loadSubjects, state.activeSubjectId]);

  const restoreSubject = useCallback(async (subjectId: string): Promise<Subject> => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await api.restoreSubject(subjectId);
      await loadSubjects();
      return response.subject;
    } catch (err) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to restore subject',
      }));
      throw err;
    }
  }, [loadSubjects]);

  const getSubjectStats = useCallback(async (subjectId: string): Promise<SubjectStats> => {
    const response = await api.getSubjectStats(subjectId);
    return response.stats;
  }, []);

  const clearError = useCallback(() => {
    setState(prev => ({ ...prev, error: null }));
  }, []);

  // ---------------------------------------------------------------------------
  // Context Value
  // ---------------------------------------------------------------------------

  const value: SubjectContextValue = {
    ...state,
    loadSubjects,
    setActiveSubject,
    createSubject,
    updateSubject,
    deleteSubject,
    archiveSubject,
    restoreSubject,
    refreshActiveSubject,
    getSubjectStats,
    clearError,
  };

  return (
    <SubjectContext.Provider value={value}>
      {children}
    </SubjectContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSubject(): SubjectContextValue {
  const context = useContext(SubjectContext);
  
  if (context === undefined) {
    throw new Error('useSubject must be used within a SubjectProvider');
  }
  
  return context;
}

// ---------------------------------------------------------------------------
// Utility Hook - Get current subject ID for API calls
// ---------------------------------------------------------------------------

export function useActiveSubjectId(): string {
  const { activeSubjectId } = useSubject();
  return activeSubjectId;
}

export default SubjectContext;
