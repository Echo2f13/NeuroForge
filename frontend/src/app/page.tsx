'use client';

import { useState, useEffect, useCallback } from 'react';
import api, { 
  QuizQuestion, Flashcard, RevisionNote, ChatMessage, 
  MindMap, DashboardData, Subject, SubjectSummary, Citation
} from '@/lib/api';
import { useSubject } from '@/contexts/SubjectContext';
import { useCitation } from '@/contexts/CitationContext';

// Layout Components
import { Sidebar, SubjectHeader, SplitViewContainer } from '@/components/layout';
import type { FeatureTab } from '@/components/layout';

// UI Components
import { 
  Button, Card, CardHeader, CardContent,
  Input, Badge, LoadingSpinner,
  ProgressBar, Modal,
  QuizSkeleton, FlashcardSkeleton, NotesSkeleton, DashboardSkeleton,
  EmptyState, KeyboardShortcutsHelp
} from '@/components/ui';

// Feature Components
import { 
  QuizSession, FlashcardDeck, MindMapViewer, ChatInterface, DocumentsPanel 
} from '@/components/features';
import { SubjectForm } from '@/components/subjects';
import { CitationList } from '@/components/citations';

// Hooks
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';

// ============================================================================
// Types
// ============================================================================

type GlobalView = 'subject' | 'upload' | 'dashboard';

interface SubjectStats {
  documents: number;
  quizzes: number;
  mastery: number;
  streak: number;
}

// ============================================================================
// Main Component
// ============================================================================

export default function Home() {
  // Subject context
  const { 
    subjects, 
    activeSubjectId, 
    activeSubject, 
    setActiveSubject,
    createSubject,
    updateSubject,
    deleteSubject,
    loading: subjectLoading,
    loadSubjects,
  } = useSubject();
  
  // Citation context
  const { viewerOpen, toggleViewer, currentDocument } = useCitation();

  // Navigation state
  const [globalView, setGlobalView] = useState<GlobalView>('subject');
  const [activeFeatureTab, setActiveFeatureTab] = useState<FeatureTab>('documents');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topic, setTopic] = useState('');
  const [showSubjectForm, setShowSubjectForm] = useState(false);
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
  const [showShortcutsHelp, setShowShortcutsHelp] = useState(false);
  
  // Subject stats
  const [subjectStats, setSubjectStats] = useState<SubjectStats>({ documents: 0, quizzes: 0, mastery: 0, streak: 0 });
  const [subjectDocuments, setSubjectDocuments] = useState<any[]>([]);
  
  // Feature state
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([]);
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [notes, setNotes] = useState<RevisionNote | null>(null);
  const [notesCitations, setNotesCitations] = useState<Citation[]>([]);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [mindMap, setMindMap] = useState<MindMap | null>(null);
  const [citationWarning, setCitationWarning] = useState<string | null>(null);
  
  // Dashboard state
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);

  // ============================================================================
  // Keyboard Shortcuts
  // ============================================================================
  
  useKeyboardShortcuts([
    // Feature tab shortcuts (1-6)
    { key: '1', handler: () => globalView === 'subject' && setActiveFeatureTab('documents') },
    { key: '2', handler: () => globalView === 'subject' && setActiveFeatureTab('quiz') },
    { key: '3', handler: () => globalView === 'subject' && setActiveFeatureTab('flashcards') },
    { key: '4', handler: () => globalView === 'subject' && setActiveFeatureTab('notes') },
    { key: '5', handler: () => globalView === 'subject' && setActiveFeatureTab('chat') },
    { key: '6', handler: () => globalView === 'subject' && setActiveFeatureTab('mindmap') },
    // Global shortcuts
    { key: 'b', ctrl: true, handler: () => setSidebarCollapsed(prev => !prev) },
    { key: '?', shift: true, handler: () => setShowShortcutsHelp(true) },
  ]);

  // ============================================================================
  // Effects
  // ============================================================================
  
  // Load subject data when active subject changes
  useEffect(() => {
    if (activeSubjectId) {
      loadSubjectData();
    }
  }, [activeSubjectId]);

  // ============================================================================
  // Data Loading Functions
  // ============================================================================

  const loadSubjectData = async () => {
    try {
      // Load subject details if not general
      if (activeSubjectId !== 'general') {
        const subjectData = await api.getSubject(activeSubjectId);
        // Documents would come from a separate API call or the subject context
        // For now, we'll use an empty array as documents are loaded separately
        setSubjectDocuments([]);
      } else {
        setSubjectDocuments([]);
      }
      
      // Calculate stats (simplified - in real app would come from API)
      setSubjectStats({
        documents: subjectDocuments.length,
        quizzes: 0,
        mastery: 0,
        streak: 0,
      });
    } catch (err) {
      console.error('Failed to load subject data:', err);
    }
  };

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const data = await api.getDashboard(activeSubjectId !== 'general' ? activeSubjectId : undefined);
      setDashboard(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ============================================================================
  // Subject Handlers
  // ============================================================================

  const handleSelectSubject = (subjectId: string) => {
    setActiveSubject(subjectId);
    setGlobalView('subject');
    setActiveFeatureTab('documents');
    // Reset feature state
    setQuizQuestions([]);
    setFlashcards([]);
    setNotes(null);
    setMindMap(null);
    setChatMessages([]);
    setSessionId(undefined);
  };

  const handleCreateSubject = async (data: any) => {
    try {
      const newSubject = await createSubject(data);
      setShowSubjectForm(false);
      if (newSubject) {
        handleSelectSubject(newSubject.id);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleUpdateSubject = async (data: any) => {
    if (!editingSubject) return;
    try {
      await updateSubject(editingSubject.id, data);
      setEditingSubject(null);
      setShowSubjectForm(false);
      loadSubjects();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleEditSubject = async () => {
    if (activeSubjectId === 'general') return;
    try {
      const res = await api.getSubject(activeSubjectId);
      setEditingSubject(res.subject);
      setShowSubjectForm(true);
    } catch (err: any) {
      setError(err.message);
    }
  };

  // ============================================================================
  // Feature Handlers
  // ============================================================================

  const generateQuiz = async () => {
    if (!topic.trim()) { setError('Please enter a topic'); return; }
    setLoading(true);
    setError(null);
    setCitationWarning(null);
    setQuizQuestions([]);
    
    try {
      const result = await api.generateQuiz(topic, 5, undefined, activeSubjectId);
      setQuizQuestions(result.questions);
      if (result.citation_warning) setCitationWarning(result.citation_warning);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQuizComplete = async (score: number, total: number) => {
    try {
      await api.recordScore(topic, (score / total) * 100, activeSubjectId);
    } catch (err) {
      console.error('Failed to record score:', err);
    }
  };

  const generateFlashcards = async () => {
    if (!topic.trim()) { setError('Please enter a topic'); return; }
    setLoading(true);
    setError(null);
    setCitationWarning(null);
    setFlashcards([]);
    
    try {
      const result = await api.generateFlashcards(topic, 5, undefined, activeSubjectId);
      setFlashcards(result.flashcards);
      if (result.citation_warning) setCitationWarning(result.citation_warning);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const generateNotes = async () => {
    if (!topic.trim()) { setError('Please enter a topic'); return; }
    setLoading(true);
    setError(null);
    setCitationWarning(null);
    setNotes(null);
    setNotesCitations([]);
    
    try {
      const result = await api.generateNotes(topic, activeSubjectId);
      setNotes(result.notes);
      if (result.citations) setNotesCitations(result.citations);
      if (result.citation_warning) setCitationWarning(result.citation_warning);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const sendChatMessage = async (message: string) => {
    setChatMessages(prev => [...prev, { role: 'user', content: message }]);
    setLoading(true);
    
    try {
      const result = await api.chat(message, sessionId, activeSubjectId);
      setSessionId(result.session_id);
      setChatMessages(prev => [...prev, { 
        role: 'assistant', 
        content: result.answer,
        sources: result.sources,
        isGrounded: result.is_grounded,
        citations: result.citations,
        citationWarning: result.citation_warning,
      }]);
    } catch (err: any) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const resetChat = async () => {
    if (sessionId) {
      try { await api.resetChat(sessionId); } catch (e) {}
    }
    setChatMessages([]);
    setSessionId(undefined);
  };

  const generateMindMap = async () => {
    if (!topic.trim()) { setError('Please enter a topic'); return; }
    setLoading(true);
    setError(null);
    setMindMap(null);
    
    try {
      const result = await api.generateMindMap(topic, 3, activeSubjectId);
      setMindMap(result.mindmap);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ============================================================================
  // Render Helpers
  // ============================================================================

  const renderFeatureContent = () => {
    const subjectColor = activeSubject?.color || '#6366f1';
    
    switch (activeFeatureTab) {
      case 'documents':
        return (
          <DocumentsPanel
            subjectId={activeSubjectId}
            subjectName={activeSubject?.name || 'General'}
            subjectColor={subjectColor}
            documents={subjectDocuments}
            onDocumentUploaded={loadSubjectData}
            loading={loading}
          />
        );
        
      case 'quiz':
        return (
          <div className="space-y-6">
            <TopicInputSection 
              topic={topic} 
              onTopicChange={setTopic} 
              onGenerate={generateQuiz}
              loading={loading}
              buttonLabel="Generate Quiz"
              buttonIcon="🎯"
              color={subjectColor}
            />
            {loading && quizQuestions.length === 0 && <QuizSkeleton />}
            {quizQuestions.length > 0 && (
              <QuizSession 
                questions={quizQuestions}
                subjectId={activeSubjectId}
                onComplete={handleQuizComplete}
              />
            )}
            {!loading && quizQuestions.length === 0 && (
              <EmptyState
                icon={EmptyState.icons.quiz}
                title="No quiz yet"
                description="Enter a topic and generate a quiz to test your knowledge"
              />
            )}
          </div>
        );
        
      case 'flashcards':
        return (
          <div className="space-y-6">
            <TopicInputSection 
              topic={topic} 
              onTopicChange={setTopic} 
              onGenerate={generateFlashcards}
              loading={loading}
              buttonLabel="Generate Flashcards"
              buttonIcon="🎴"
              color={subjectColor}
            />
            {loading && flashcards.length === 0 && <FlashcardSkeleton />}
            {flashcards.length > 0 && (
              <FlashcardDeck flashcards={flashcards} subjectId={activeSubjectId} />
            )}
            {!loading && flashcards.length === 0 && (
              <EmptyState
                icon={EmptyState.icons.flashcard}
                title="No flashcards yet"
                description="Enter a topic and generate flashcards to study"
              />
            )}
          </div>
        );

      case 'notes':
        return (
          <div className="space-y-6">
            <TopicInputSection 
              topic={topic} 
              onTopicChange={setTopic} 
              onGenerate={generateNotes}
              loading={loading}
              buttonLabel="Generate Notes"
              buttonIcon="📚"
              color={subjectColor}
            />
            {loading && !notes && <NotesSkeleton />}
            {notes && (
              <NotesDisplay notes={notes} citations={notesCitations} subjectId={activeSubjectId} color={subjectColor} />
            )}
            {!loading && !notes && (
              <EmptyState
                icon={EmptyState.icons.notes}
                title="No notes yet"
                description="Enter a topic and generate revision notes"
              />
            )}
          </div>
        );
        
      case 'chat':
        return (
          <ChatInterface
            messages={chatMessages}
            onSendMessage={sendChatMessage}
            onReset={resetChat}
            isLoading={loading}
            subjectId={activeSubjectId}
            placeholder={`Ask about ${activeSubject?.name || 'your study materials'}...`}
          />
        );
        
      case 'mindmap':
        return (
          <div className="space-y-6">
            <TopicInputSection 
              topic={topic} 
              onTopicChange={setTopic} 
              onGenerate={generateMindMap}
              loading={loading}
              buttonLabel="Generate Mind Map"
              buttonIcon="🗺️"
              color={subjectColor}
            />
            <MindMapViewer mindmap={mindMap} topic={topic} />
          </div>
        );
        
      default:
        return null;
    }
  };

  // ============================================================================
  // Main Render
  // ============================================================================

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950">
      {/* Sidebar */}
      <Sidebar
        subjects={subjects}
        activeSubjectId={activeSubjectId}
        onSelectSubject={handleSelectSubject}
        onCreateSubject={() => { setShowSubjectForm(true); setEditingSubject(null); }}
        onNavigate={(view) => {
          setGlobalView(view as GlobalView);
          if (view === 'dashboard') loadDashboard();
        }}
        currentView={globalView}
        loading={subjectLoading}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <SplitViewContainer>
          {globalView === 'subject' && (
            <>
              {/* Subject Header with Feature Tabs */}
              <SubjectHeader
                subject={activeSubject}
                activeTab={activeFeatureTab}
                onTabChange={setActiveFeatureTab}
                onEditSubject={handleEditSubject}
                stats={subjectStats}
              />

              {/* Feature Content */}
              <main className="flex-1 overflow-y-auto p-6">
                {/* Error Alert */}
                {error && (
                  <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-400 flex items-center gap-3">
                    <span>⚠️</span>
                    <span className="flex-1">{error}</span>
                    <button onClick={() => setError(null)} className="hover:text-red-900 dark:hover:text-red-300">×</button>
                  </div>
                )}
                
                {/* Citation Warning */}
                {citationWarning && (
                  <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl text-yellow-800 dark:text-yellow-400 flex items-center gap-3">
                    <span>📎</span>
                    <span className="flex-1">{citationWarning}</span>
                    <button onClick={() => setCitationWarning(null)} className="hover:text-yellow-900">×</button>
                  </div>
                )}

                {renderFeatureContent()}
              </main>
            </>
          )}

          {globalView === 'upload' && (
            <main className="flex-1 overflow-y-auto p-6">
              <div className="max-w-4xl mx-auto">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">📤 Quick Upload</h1>
                <p className="text-gray-600 dark:text-gray-400 mb-6">Upload to any subject quickly</p>
                
                <Card>
                  <CardContent>
                    {/* Subject Quick Select */}
                    <div className="mb-6">
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Upload to subject:
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          onClick={() => setActiveSubject('general')}
                          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                            activeSubjectId === 'general'
                              ? 'bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300'
                              : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                          }`}
                        >
                          📚 General
                        </button>
                        {subjects.filter(s => s.status !== 'archived').map(subject => (
                          <button
                            key={subject.id}
                            onClick={() => setActiveSubject(subject.id)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                              activeSubjectId === subject.id
                                ? 'text-white'
                                : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                            }`}
                            style={activeSubjectId === subject.id ? { backgroundColor: subject.color || '#6366f1' } : undefined}
                          >
                            {subject.icon} {subject.name}
                          </button>
                        ))}
                      </div>
                    </div>
                    
                    <DocumentsPanel
                      subjectId={activeSubjectId}
                      subjectName={activeSubject?.name || 'General'}
                      subjectColor={activeSubject?.color || '#6366f1'}
                      documents={[]}
                      onDocumentUploaded={loadSubjectData}
                    />
                  </CardContent>
                </Card>
              </div>
            </main>
          )}

          {globalView === 'dashboard' && (
            <main className="flex-1 overflow-y-auto p-6">
              <div className="max-w-6xl mx-auto">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">📊 Learning Dashboard</h1>
                
                {loading ? (
                  <DashboardSkeleton />
                ) : dashboard ? (
                  <DashboardContent dashboard={dashboard} />
                ) : (
                  <EmptyState
                    icon={EmptyState.icons.dashboard}
                    title="No Progress Data Yet"
                    description="Complete some quizzes to start tracking your progress!"
                    action={<Button onClick={loadDashboard}>Refresh</Button>}
                  />
                )}
              </div>
            </main>
          )}
        </SplitViewContainer>
      </div>

      {/* Subject Form Modal */}
      <Modal
        isOpen={showSubjectForm}
        onClose={() => { setShowSubjectForm(false); setEditingSubject(null); }}
        title={editingSubject ? 'Edit Subject' : 'Create New Subject'}
      >
        <SubjectForm
          subject={editingSubject}
          onSubmit={editingSubject ? handleUpdateSubject : handleCreateSubject}
          onCancel={() => { setShowSubjectForm(false); setEditingSubject(null); }}
          isLoading={subjectLoading}
        />
      </Modal>

      {/* Keyboard Shortcuts Help */}
      <KeyboardShortcutsHelp 
        isOpen={showShortcutsHelp} 
        onClose={() => setShowShortcutsHelp(false)} 
      />
    </div>
  );
}


// ============================================================================
// Helper Components
// ============================================================================

function TopicInputSection({
  topic,
  onTopicChange,
  onGenerate,
  loading,
  buttonLabel,
  buttonIcon,
  color,
}: {
  topic: string;
  onTopicChange: (value: string) => void;
  onGenerate: () => void;
  loading: boolean;
  buttonLabel: string;
  buttonIcon: string;
  color: string;
}) {
  return (
    <Card>
      <CardContent>
        <div className="flex gap-4">
          <div className="flex-1">
            <Input
              value={topic}
              onChange={onTopicChange}
              placeholder="Enter a topic (e.g., Machine Learning, Data Structures...)"
              onKeyDown={(e: any) => e.key === 'Enter' && !loading && onGenerate()}
            />
          </div>
          <Button 
            onClick={onGenerate} 
            disabled={loading || !topic.trim()} 
            loading={loading}
            style={{ backgroundColor: !loading && topic.trim() ? color : undefined }}
          >
            {buttonIcon} {buttonLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}


function NotesDisplay({
  notes,
  citations,
  subjectId,
  color,
}: {
  notes: RevisionNote;
  citations: Citation[];
  subjectId: string;
  color: string;
}) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white">
          📚 {notes.topic}
        </h2>
      </CardHeader>
      <CardContent>
        {/* Subtopics */}
        {notes.subtopics?.map((subtopic, idx) => (
          <div 
            key={idx} 
            className="mb-6 p-5 rounded-xl border"
            style={{ backgroundColor: `${color}05`, borderColor: `${color}20` }}
          >
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{subtopic.title}</h3>
              <Badge variant={subtopic.importance === 'high' ? 'error' : subtopic.importance === 'medium' ? 'warning' : 'success'}>
                {subtopic.importance}
              </Badge>
            </div>
            <ul className="space-y-2">
              {(subtopic.points || subtopic.key_points || subtopic.bullet_points || []).map((point, i) => (
                <li key={i} className="flex items-start gap-2 text-gray-700 dark:text-gray-300">
                  <span style={{ color }} className="mt-1">•</span>
                  <span>{point}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {/* Key Terms */}
        {notes.key_terms?.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">📖 Key Terms</h3>
            <div className="flex flex-wrap gap-2">
              {notes.key_terms.map((term, i) => (
                <Badge key={i} variant="info">{term}</Badge>
              ))}
            </div>
          </div>
        )}

        {/* Formulae */}
        {notes.formulae?.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">📐 Formulae</h3>
            <div className="space-y-2">
              {notes.formulae.map((formula, i) => (
                <code key={i} className="block p-3 bg-gray-900 text-green-400 rounded-lg font-mono text-sm">
                  {formula}
                </code>
              ))}
            </div>
          </div>
        )}

        {/* Mnemonics */}
        {notes.mnemonics?.length > 0 && (
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">🧠 Mnemonics</h3>
            <div className="space-y-2">
              {notes.mnemonics.map((m, i) => (
                <div key={i} className="flex items-start gap-2 p-3 bg-purple-50 dark:bg-purple-900/20 text-purple-800 dark:text-purple-300 rounded-lg">
                  <span>💡</span>
                  <span>{m}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Citations */}
        {citations.length > 0 && (
          <div className="pt-6 border-t border-gray-200 dark:border-gray-700">
            <CitationList 
              citations={citations}
              title="Sources"
              collapsible={true}
              defaultCollapsed={false}
              subjectId={subjectId}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}


function DashboardContent({ dashboard }: { dashboard: DashboardData }) {
  return (
    <div className="space-y-6">
      {/* Top Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Streak */}
        <Card className="bg-gradient-to-br from-orange-50 to-red-50 dark:from-orange-900/20 dark:to-red-900/20">
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-orange-600 dark:text-orange-400">Current Streak</p>
                <p className="text-4xl font-bold text-orange-600 dark:text-orange-400">
                  🔥 {dashboard.streak.current_streak}
                  <span className="text-lg font-normal ml-2">days</span>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Due Cards */}
        <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20">
          <CardContent>
            <p className="text-sm font-medium text-blue-600 dark:text-blue-400 mb-3">Cards Due</p>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="p-2 bg-white/60 dark:bg-gray-800/60 rounded-lg">
                <p className="text-xl font-bold text-blue-600">{dashboard.due_cards.today}</p>
                <p className="text-xs text-gray-500">Today</p>
              </div>
              <div className="p-2 bg-white/60 dark:bg-gray-800/60 rounded-lg">
                <p className="text-xl font-bold text-indigo-600">{dashboard.due_cards.this_week}</p>
                <p className="text-xs text-gray-500">Week</p>
              </div>
              <div className="p-2 bg-white/60 dark:bg-gray-800/60 rounded-lg">
                <p className="text-xl font-bold text-purple-600">{dashboard.due_cards.this_month}</p>
                <p className="text-xs text-gray-500">Month</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Exam Readiness */}
        <Card className={`border-2 ${
          dashboard.exam_readiness.level === 'excellent' ? 'bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 border-green-200 dark:border-green-800' :
          dashboard.exam_readiness.level === 'good' ? 'bg-gradient-to-br from-blue-50 to-cyan-50 dark:from-blue-900/20 border-blue-200 dark:border-blue-800' :
          'bg-gradient-to-br from-yellow-50 to-amber-50 dark:from-yellow-900/20 border-yellow-200 dark:border-yellow-800'
        }`}>
          <CardContent>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Exam Readiness</p>
                <p className="text-4xl font-bold text-green-600 dark:text-green-400">
                  {dashboard.exam_readiness.score}%
                </p>
                <p className="text-xs text-gray-500 mt-1">{dashboard.exam_readiness.message}</p>
              </div>
              <span className="text-4xl">
                {dashboard.exam_readiness.level === 'excellent' ? '🏆' : dashboard.exam_readiness.level === 'good' ? '📈' : '📊'}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="text-center"><CardContent>
          <p className="text-2xl font-bold text-indigo-600">{dashboard.overall.total_quizzes}</p>
          <p className="text-xs text-gray-500">Quizzes</p>
        </CardContent></Card>
        <Card className="text-center"><CardContent>
          <p className="text-2xl font-bold text-purple-600">{dashboard.overall.total_topics}</p>
          <p className="text-xs text-gray-500">Topics</p>
        </CardContent></Card>
        <Card className="text-center"><CardContent>
          <p className="text-2xl font-bold text-green-600">{dashboard.overall.average_score.toFixed(0)}%</p>
          <p className="text-xs text-gray-500">Avg Score</p>
        </CardContent></Card>
        <Card className="text-center"><CardContent>
          <p className="text-2xl font-bold text-blue-600">{dashboard.streak.total_cards_reviewed}</p>
          <p className="text-xs text-gray-500">Reviews</p>
        </CardContent></Card>
        <Card className="text-center"><CardContent>
          <p className="text-2xl font-bold text-orange-600">{dashboard.weekly.total_this_week}</p>
          <p className="text-xs text-gray-500">This Week</p>
        </CardContent></Card>
      </div>

      {/* Topic Mastery */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">🎯 Topic Mastery</h3>
        </CardHeader>
        <CardContent>
          {dashboard.topic_mastery.length > 0 ? (
            <div className="space-y-4">
              {dashboard.topic_mastery.slice(0, 6).map((topic, i) => (
                <div key={i}>
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 truncate">{topic.topic}</span>
                    <span className="text-sm font-bold text-indigo-600">{topic.mastery_percent.toFixed(0)}%</span>
                  </div>
                  <ProgressBar progress={topic.mastery_percent} size="sm" />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-4">Complete quizzes to track mastery</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
