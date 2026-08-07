'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import api, { 
  QuizQuestion, Flashcard, RevisionNote, ChatMessage, 
  UploadStatus, MindMap, DashboardData, Subject, SubjectSummary
} from '@/lib/api';
import { useSubject, useActiveSubjectId } from '@/contexts/SubjectContext';
import { SubjectSelector, SubjectList, SubjectForm, SubjectCard } from '@/components/subjects';

// ============================================================================
// Types & Constants
// ============================================================================

type Tab = 'upload' | 'quiz' | 'flashcards' | 'notes' | 'chat' | 'solution' | 'mindmap' | 'dashboard' | 'subjects';

const TABS: { id: Tab; label: string; icon: string; color: string }[] = [
  { id: 'subjects', label: 'Subjects', icon: '📚', color: 'from-cyan-500 to-cyan-600' },
  { id: 'upload', label: 'Upload', icon: '📤', color: 'from-blue-500 to-blue-600' },
  { id: 'quiz', label: 'Quiz', icon: '📝', color: 'from-green-500 to-green-600' },
  { id: 'flashcards', label: 'Flashcards', icon: '🎴', color: 'from-purple-500 to-purple-600' },
  { id: 'notes', label: 'Notes', icon: '📖', color: 'from-orange-500 to-orange-600' },
  { id: 'chat', label: 'AI Tutor', icon: '💬', color: 'from-pink-500 to-pink-600' },
  { id: 'solution', label: 'Solutions', icon: '💡', color: 'from-yellow-500 to-yellow-600' },
  { id: 'mindmap', label: 'Mind Map', icon: '🗺️', color: 'from-teal-500 to-teal-600' },
  { id: 'dashboard', label: 'Dashboard', icon: '📊', color: 'from-indigo-500 to-indigo-600' },
];

// ============================================================================
// Utility Components
// ============================================================================

const LoadingSpinner = ({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) => {
  const sizeClasses = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' };
  return (
    <div className={`${sizeClasses[size]} border-2 border-indigo-200 border-t-indigo-600 rounded-full animate-spin`} />
  );
};

const ProgressBar = ({ progress, className = '' }: { progress: number; className?: string }) => (
  <div className={`h-2 bg-gray-200 rounded-full overflow-hidden ${className}`}>
    <div 
      className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500 ease-out"
      style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
    />
  </div>
);


const Card = ({ children, className = '', hover = true }: { 
  children: React.ReactNode; 
  className?: string;
  hover?: boolean;
}) => (
  <div className={`
    bg-white rounded-2xl shadow-sm border border-gray-100 
    ${hover ? 'hover:shadow-md hover:border-gray-200 transition-all duration-200' : ''}
    ${className}
  `}>
    {children}
  </div>
);

const Button = ({ 
  children, 
  onClick, 
  disabled = false, 
  variant = 'primary',
  size = 'md',
  className = '',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) => {
  const variants = {
    primary: 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white hover:from-indigo-600 hover:to-purple-700 shadow-md hover:shadow-lg',
    secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200',
    ghost: 'bg-transparent text-gray-600 hover:bg-gray-100',
  };
  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-5 py-2.5 text-base',
    lg: 'px-7 py-3.5 text-lg',
  };
  
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        font-medium rounded-xl transition-all duration-200 
        disabled:opacity-50 disabled:cursor-not-allowed
        ${variants[variant]} ${sizes[size]} ${className}
      `}
    >
      {children}
    </button>
  );
};

const Input = ({ 
  value, 
  onChange, 
  placeholder = '', 
  type = 'text',
  className = '',
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
  className?: string;
}) => (
  <input
    type={type}
    value={value}
    onChange={(e) => onChange(e.target.value)}
    placeholder={placeholder}
    className={`
      w-full px-4 py-3 border border-gray-200 rounded-xl
      focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 
      outline-none transition-all duration-200
      placeholder:text-gray-400
      ${className}
    `}
  />
);


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
    archiveSubject,
    restoreSubject,
    loadSubjects,
    loading: subjectLoading,
  } = useSubject();

  // Core state
  const [activeTab, setActiveTab] = useState<Tab>('upload');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [topic, setTopic] = useState('');
  
  // Subject form state
  const [showSubjectForm, setShowSubjectForm] = useState(false);
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
  
  // Upload state
  const [uploadProgress, setUploadProgress] = useState<UploadStatus | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  
  // Quiz state
  const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([]);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showExplanation, setShowExplanation] = useState(false);
  const [quizScore, setQuizScore] = useState(0);
  const [quizCompleted, setQuizCompleted] = useState(false);
  
  // Flashcards state
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [currentCard, setCurrentCard] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [cardFlipped, setCardFlipped] = useState(false);
  
  // Notes state
  const [notes, setNotes] = useState<RevisionNote | null>(null);
  
  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [sessionId, setSessionId] = useState<string | undefined>();
  const chatEndRef = useRef<HTMLDivElement>(null);
  
  // Solution state
  const [solutionQuestion, setSolutionQuestion] = useState('');
  const [solutionMarks, setSolutionMarks] = useState(5);
  const [solution, setSolution] = useState<any>(null);
  
  // Mind map state
  const [mindMap, setMindMap] = useState<MindMap | null>(null);
  
  // Dashboard state (replaces old progress)
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);

  // Effects
  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);


  // Data loading functions
  const loadStats = async () => {
    try {
      const data = await api.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
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

  // Subject handlers
  const handleCreateSubject = async (data: any) => {
    try {
      await createSubject(data);
      setShowSubjectForm(false);
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
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDeleteSubject = async (subject: SubjectSummary) => {
    if (!confirm(`Are you sure you want to delete "${subject.name}"? This will permanently delete all documents and progress.`)) {
      return;
    }
    try {
      await deleteSubject(subject.id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleArchiveSubject = async (subject: SubjectSummary) => {
    try {
      await archiveSubject(subject.id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRestoreSubject = async (subject: SubjectSummary) => {
    try {
      await restoreSubject(subject.id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  // Upload handlers
  const handleFileDrop = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    
    setLoading(true);
    setError(null);
    setUploadProgress(null);
    
    try {
      // Use async mode for better UX, pass active subject ID
      const result = await api.uploadDocument(file, true, activeSubjectId);
      
      if (result.status === 'processing') {
        // Poll for status
        await api.waitForUpload(
          result.document_id,
          (status) => setUploadProgress(status),
          1500
        );
      }
      
      loadStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
      setTimeout(() => setUploadProgress(null), 3000);
    }
  }, [activeSubjectId]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileDrop(e.dataTransfer.files);
  };

  const handleYouTubeUpload = async () => {
    const url = prompt('Enter YouTube URL:');
    if (!url) return;
    
    setLoading(true);
    setError(null);
    try {
      const result = await api.uploadYouTube(url);
      alert(`Success! Processed ${result.chunks_created} chunks from "${result.title}"`);
      loadStats();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };


  // Quiz handlers
  const generateQuiz = async () => {
    if (!topic.trim()) { setError('Please enter a topic'); return; }
    setLoading(true);
    setError(null);
    setQuizQuestions([]);
    setCurrentQuestion(0);
    setQuizScore(0);
    setQuizCompleted(false);
    setSelectedAnswer(null);
    setShowExplanation(false);
    
    try {
      const result = await api.generateQuiz(topic, 5, undefined, activeSubjectId);
      setQuizQuestions(result.questions);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleQuizAnswer = (answer: string) => {
    setSelectedAnswer(answer);
    setShowExplanation(true);
    if (answer === quizQuestions[currentQuestion].correct_answer) {
      setQuizScore(prev => prev + 1);
    }
  };

  const nextQuestion = () => {
    if (currentQuestion < quizQuestions.length - 1) {
      setCurrentQuestion(prev => prev + 1);
      setSelectedAnswer(null);
      setShowExplanation(false);
    } else {
      setQuizCompleted(true);
      api.recordScore(topic, (quizScore / quizQuestions.length) * 100, activeSubjectId).catch(console.error);
    }
  };

  // Flashcard handlers
  const generateFlashcards = async () => {
    if (!topic.trim()) { setError('Please enter a topic'); return; }
    setLoading(true);
    setError(null);
    setFlashcards([]);
    setCurrentCard(0);
    setShowAnswer(false);
    setCardFlipped(false);
    
    try {
      const result = await api.generateFlashcards(topic, 5, undefined, activeSubjectId);
      setFlashcards(result.flashcards);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const flipCard = () => {
    setCardFlipped(!cardFlipped);
    setShowAnswer(!showAnswer);
  };

  const nextCard = () => {
    setCurrentCard(prev => Math.min(flashcards.length - 1, prev + 1));
    setCardFlipped(false);
    setShowAnswer(false);
  };

  const prevCard = () => {
    setCurrentCard(prev => Math.max(0, prev - 1));
    setCardFlipped(false);
    setShowAnswer(false);
  };


  // Notes handler
  const generateNotes = async () => {
    if (!topic.trim()) { setError('Please enter a topic'); return; }
    setLoading(true);
    setError(null);
    setNotes(null);
    
    try {
      const result = await api.generateNotes(topic, activeSubjectId);
      setNotes(result.notes);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Chat handler
  const sendChatMessage = async () => {
    if (!chatInput.trim()) return;
    const message = chatInput;
    setChatInput('');
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
      }]);
    } catch (err: any) {
      setChatMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const resetChat = async () => {
    if (sessionId) {
      try {
        await api.resetChat(sessionId);
      } catch (e) {}
    }
    setChatMessages([]);
    setSessionId(undefined);
  };

  // Solution handler
  const generateSolution = async () => {
    if (!solutionQuestion.trim()) { setError('Please enter a question'); return; }
    setLoading(true);
    setError(null);
    setSolution(null);
    
    try {
      const result = await api.generateSolution(solutionQuestion, topic || 'General', solutionMarks, activeSubjectId);
      setSolution(result.solution);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Mind map handler
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
  // Render
  // ============================================================================

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-gray-100 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg shadow-indigo-200">
                <span className="text-white font-bold text-xl">N</span>
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                  NeuroForge
                </h1>
                <p className="text-xs text-gray-500 font-medium">Adaptive Learning Engine</p>
              </div>
            </div>
            
            {/* Subject Selector */}
            <div className="flex items-center gap-6">
              <SubjectSelector 
                onCreateNew={() => {
                  setShowSubjectForm(true);
                  setEditingSubject(null);
                }}
                onViewAll={() => setActiveTab('subjects')}
              />
              
              {stats && (
                <div className="hidden md:flex items-center gap-8">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900">{stats.knowledge_base.chunks}</p>
                    <p className="text-xs text-gray-500 font-medium">Chunks</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-indigo-600">{stats.knowledge_base.concepts}</p>
                    <p className="text-xs text-gray-500 font-medium">Concepts</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-purple-600">{stats.learning.total_quizzes}</p>
                    <p className="text-xs text-gray-500 font-medium">Quizzes</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Tab Navigation */}
      <nav className="bg-white/60 backdrop-blur-sm border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex gap-1 overflow-x-auto py-3 scrollbar-hide">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => { 
                  setActiveTab(tab.id); 
                  setError(null);
                  if (tab.id === 'dashboard') loadDashboard();
                }}
                className={`
                  flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium 
                  transition-all duration-200 whitespace-nowrap
                  ${activeTab === tab.id 
                    ? `bg-gradient-to-r ${tab.color} text-white shadow-md` 
                    : 'text-gray-600 hover:bg-gray-100'
                  }
                `}
              >
                <span className="text-lg">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </nav>


      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Error Alert */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center gap-3">
            <span className="text-xl">⚠️</span>
            <span className="flex-1">{error}</span>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-700 text-xl">×</button>
          </div>
        )}

        {/* Topic Input (shared across features) */}
        {['quiz', 'flashcards', 'notes', 'mindmap'].includes(activeTab) && (
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">📌 Topic</label>
            <Input
              value={topic}
              onChange={setTopic}
              placeholder="Enter a topic (e.g., Machine Learning, Engineering Materials, Data Structures)"
            />
          </div>
        )}

        {/* ============ SUBJECTS TAB ============ */}
        {activeTab === 'subjects' && (
          <div className="space-y-6">
            <Card className="p-8">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">📚 Study Subjects</h2>
                  <p className="text-gray-600">Organize your learning materials into separate subjects</p>
                </div>
              </div>
              
              <SubjectList
                subjects={subjects}
                activeSubjectId={activeSubjectId}
                onSelect={(subject) => setActiveSubject(subject.id)}
                onEdit={(subject) => {
                  // Fetch full subject details for editing
                  api.getSubject(subject.id).then(res => {
                    setEditingSubject(res.subject);
                    setShowSubjectForm(true);
                  });
                }}
                onArchive={handleArchiveSubject}
                onDelete={handleDeleteSubject}
                onRestore={handleRestoreSubject}
                onCreateNew={() => {
                  setShowSubjectForm(true);
                  setEditingSubject(null);
                }}
                loading={subjectLoading}
                showArchived={true}
              />
            </Card>
          </div>
        )}

        {/* Subject Form Modal */}
        {showSubjectForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
              <h2 className="text-xl font-bold text-gray-900 mb-6">
                {editingSubject ? 'Edit Subject' : 'Create New Subject'}
              </h2>
              <SubjectForm
                subject={editingSubject}
                onSubmit={editingSubject ? handleUpdateSubject : handleCreateSubject}
                onCancel={() => {
                  setShowSubjectForm(false);
                  setEditingSubject(null);
                }}
                isLoading={subjectLoading}
              />
            </Card>
          </div>
        )}

        {/* ============ UPLOAD TAB ============ */}
        {activeTab === 'upload' && (
          <div className="space-y-6">
            <Card className="p-8">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">📤 Upload Study Material</h2>
              <p className="text-gray-600 mb-2">Upload documents to build your personal knowledge base</p>
              
              {/* Active Subject Indicator */}
              <div className="mb-6 flex items-center gap-2 text-sm">
                <span className="text-gray-500">Uploading to:</span>
                <span 
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full font-medium"
                  style={{ 
                    backgroundColor: activeSubject?.color ? `${activeSubject.color}15` : '#f3f4f6',
                    color: activeSubject?.color || '#4b5563'
                  }}
                >
                  <span>{activeSubject?.icon || '📚'}</span>
                  {activeSubject?.name || 'General'}
                </span>
                <button 
                  onClick={() => setActiveTab('subjects')}
                  className="text-indigo-600 hover:text-indigo-700 hover:underline"
                >
                  Change
                </button>
              </div>
              
              <div className="grid md:grid-cols-2 gap-6">
                {/* File Upload Zone */}
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`
                    relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer
                    transition-all duration-200
                    ${isDragging 
                      ? 'border-indigo-500 bg-indigo-50 scale-[1.02]' 
                      : 'border-gray-300 hover:border-indigo-400 hover:bg-indigo-50/50'
                    }
                  `}
                >
                  <input
                    type="file"
                    className="absolute inset-0 opacity-0 cursor-pointer"
                    accept=".pdf,.pptx,.docx,.png,.jpg,.jpeg,.txt,.md"
                    onChange={(e) => handleFileDrop(e.target.files)}
                    disabled={loading}
                  />
                  <div className="text-5xl mb-4">📄</div>
                  <p className="font-semibold text-gray-900 mb-1">Drop files here or click to upload</p>
                  <p className="text-sm text-gray-500">PDF, PPTX, DOCX, Images, Text</p>
                </div>
                
                {/* YouTube Upload */}
                <button
                  onClick={handleYouTubeUpload}
                  disabled={loading}
                  className="border-2 border-dashed border-gray-300 rounded-2xl p-8 text-center hover:border-red-400 hover:bg-red-50/50 transition-all duration-200"
                >
                  <div className="text-5xl mb-4">🎬</div>
                  <p className="font-semibold text-gray-900 mb-1">YouTube Video</p>
                  <p className="text-sm text-gray-500">Extract from video transcripts</p>
                </button>
              </div>
              
              {/* Upload Progress */}
              {uploadProgress && (
                <div className="mt-6 p-4 bg-indigo-50 rounded-xl">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-indigo-900">{uploadProgress.message}</span>
                    <span className="text-sm text-indigo-600">{uploadProgress.progress}%</span>
                  </div>
                  <ProgressBar progress={uploadProgress.progress} />
                  {uploadProgress.status === 'completed' && (
                    <p className="mt-2 text-sm text-green-600">
                      ✅ Created {uploadProgress.chunks_created} chunks, extracted {uploadProgress.concepts_extracted} concepts
                    </p>
                  )}
                </div>
              )}
              
              {loading && !uploadProgress && (
                <div className="mt-6 flex items-center justify-center gap-3 text-indigo-600">
                  <LoadingSpinner />
                  <span>Processing document...</span>
                </div>
              )}
            </Card>
          </div>
        )}


        {/* ============ QUIZ TAB ============ */}
        {activeTab === 'quiz' && (
          <div className="space-y-6">
            <Button onClick={generateQuiz} disabled={loading} size="lg">
              {loading ? <><LoadingSpinner size="sm" /> Generating...</> : '🎯 Generate Quiz'}
            </Button>

            {quizQuestions.length > 0 && !quizCompleted && (
              <Card className="p-8">
                <div className="flex justify-between items-center mb-6">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-500">Question</span>
                    <span className="px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm font-bold">
                      {currentQuestion + 1} / {quizQuestions.length}
                    </span>
                  </div>
                  <span className="px-4 py-1 bg-green-100 text-green-700 rounded-full text-sm font-bold">
                    Score: {quizScore}
                  </span>
                </div>
                
                <h3 className="text-xl font-semibold text-gray-900 mb-6 leading-relaxed">
                  {quizQuestions[currentQuestion].question}
                </h3>
                
                {quizQuestions[currentQuestion].question_type === 'mcq' && quizQuestions[currentQuestion].options && (
                  <div className="space-y-3">
                    {quizQuestions[currentQuestion].options!.map((option, idx) => (
                      <button
                        key={idx}
                        onClick={() => !showExplanation && handleQuizAnswer(option)}
                        disabled={showExplanation}
                        className={`
                          w-full p-4 text-left rounded-xl border-2 transition-all duration-200
                          ${showExplanation 
                            ? option === quizQuestions[currentQuestion].correct_answer
                              ? 'border-green-500 bg-green-50 text-green-800'
                              : option === selectedAnswer
                                ? 'border-red-500 bg-red-50 text-red-800'
                                : 'border-gray-200 text-gray-500'
                            : 'border-gray-200 hover:border-indigo-400 hover:bg-indigo-50'
                          }
                        `}
                      >
                        <span className="font-medium">{String.fromCharCode(65 + idx)}.</span> {option}
                      </button>
                    ))}
                  </div>
                )}
                
                {quizQuestions[currentQuestion].question_type === 'true_false' && (
                  <div className="flex gap-4">
                    {['True', 'False'].map((option) => (
                      <button
                        key={option}
                        onClick={() => !showExplanation && handleQuizAnswer(option)}
                        disabled={showExplanation}
                        className={`
                          flex-1 p-4 rounded-xl border-2 font-semibold transition-all duration-200
                          ${showExplanation 
                            ? option === quizQuestions[currentQuestion].correct_answer
                              ? 'border-green-500 bg-green-50 text-green-800'
                              : option === selectedAnswer
                                ? 'border-red-500 bg-red-50 text-red-800'
                                : 'border-gray-200 text-gray-500'
                            : 'border-gray-200 hover:border-indigo-400 hover:bg-indigo-50'
                          }
                        `}
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                )}

                {showExplanation && (
                  <div className="mt-6 p-5 bg-blue-50 border border-blue-200 rounded-xl">
                    <p className="font-semibold text-blue-900 mb-2">💡 Explanation</p>
                    <p className="text-blue-800 leading-relaxed">{quizQuestions[currentQuestion].explanation}</p>
                    <Button onClick={nextQuestion} className="mt-4">
                      {currentQuestion < quizQuestions.length - 1 ? 'Next Question →' : '🎉 Finish Quiz'}
                    </Button>
                  </div>
                )}
              </Card>
            )}

            {quizCompleted && (
              <Card className="p-8 text-center">
                <div className="text-6xl mb-4">🎉</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-2">Quiz Complete!</h3>
                <p className="text-5xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent mb-4">
                  {Math.round((quizScore / quizQuestions.length) * 100)}%
                </p>
                <p className="text-gray-600">You got {quizScore} out of {quizQuestions.length} questions correct</p>
                <Button onClick={generateQuiz} className="mt-6">Try Another Quiz</Button>
              </Card>
            )}
          </div>
        )}


        {/* ============ FLASHCARDS TAB ============ */}
        {activeTab === 'flashcards' && (
          <div className="space-y-6">
            <Button onClick={generateFlashcards} disabled={loading} size="lg">
              {loading ? <><LoadingSpinner size="sm" /> Generating...</> : '🎴 Generate Flashcards'}
            </Button>

            {flashcards.length > 0 && (
              <div className="max-w-2xl mx-auto">
                {/* Card Counter */}
                <div className="flex justify-center mb-4">
                  <span className="px-4 py-2 bg-purple-100 text-purple-700 rounded-full text-sm font-bold">
                    Card {currentCard + 1} of {flashcards.length}
                  </span>
                </div>
                
                {/* Flashcard */}
                <div 
                  onClick={flipCard}
                  className="relative h-80 cursor-pointer perspective-1000"
                >
                  <div className={`
                    absolute inset-0 transition-transform duration-500 transform-style-3d
                    ${cardFlipped ? 'rotate-y-180' : ''}
                  `}>
                    {/* Front */}
                    <Card className={`
                      absolute inset-0 p-8 flex flex-col items-center justify-center backface-hidden
                      ${cardFlipped ? 'invisible' : ''}
                    `}>
                      <p className="text-sm text-gray-500 mb-4">Question</p>
                      <h3 className="text-xl font-semibold text-gray-900 text-center mb-6">
                        {flashcards[currentCard].question}
                      </h3>
                      {flashcards[currentCard].hint && (
                        <p className="text-sm text-indigo-600 bg-indigo-50 px-4 py-2 rounded-lg">
                          💡 Hint: {flashcards[currentCard].hint}
                        </p>
                      )}
                      <p className="text-xs text-gray-400 mt-auto">Click to reveal answer</p>
                    </Card>
                    
                    {/* Back */}
                    <Card className={`
                      absolute inset-0 p-8 flex flex-col items-center justify-center
                      bg-gradient-to-br from-indigo-50 to-purple-50
                      ${cardFlipped ? '' : 'invisible'}
                    `}>
                      <p className="text-sm text-purple-600 mb-4">Answer</p>
                      <p className="text-2xl font-bold text-gray-900 text-center mb-6">
                        {flashcards[currentCard].answer}
                      </p>
                      {flashcards[currentCard].mnemonic && (
                        <p className="text-sm text-purple-600 bg-purple-100 px-4 py-2 rounded-lg">
                          🧠 {flashcards[currentCard].mnemonic}
                        </p>
                      )}
                    </Card>
                  </div>
                </div>
                
                {/* Navigation */}
                <div className="flex justify-center gap-4 mt-6">
                  <Button onClick={prevCard} disabled={currentCard === 0} variant="secondary">
                    ← Previous
                  </Button>
                  <Button onClick={nextCard} disabled={currentCard === flashcards.length - 1}>
                    Next →
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}


        {/* ============ NOTES TAB ============ */}
        {activeTab === 'notes' && (
          <div className="space-y-6">
            <Button onClick={generateNotes} disabled={loading} size="lg">
              {loading ? <><LoadingSpinner size="sm" /> Generating...</> : '📚 Generate Revision Notes'}
            </Button>

            {notes && (
              <Card className="p-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-6">
                  📚 Revision Notes: {notes.topic || topic}
                </h2>
                
                {/* Subtopics */}
                {notes.subtopics?.map((subtopic, idx) => (
                  <div key={idx} className="mb-6 p-5 bg-gray-50 rounded-xl border border-gray-100">
                    <div className="flex items-center gap-3 mb-3">
                      <h3 className="text-lg font-semibold text-gray-900">{subtopic.title}</h3>
                      <span className={`
                        px-2 py-0.5 text-xs font-medium rounded-full
                        ${subtopic.importance === 'high' ? 'bg-red-100 text-red-700' :
                          subtopic.importance === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-green-100 text-green-700'}
                      `}>
                        {subtopic.importance}
                      </span>
                    </div>
                    <ul className="space-y-2">
                      {(subtopic.points || subtopic.key_points || subtopic.bullet_points || []).map((point, i) => (
                        <li key={i} className="flex items-start gap-2 text-gray-700">
                          <span className="text-indigo-500 mt-1">•</span>
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}

                {/* Key Terms */}
                {notes.key_terms?.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">📖 Key Terms</h3>
                    <div className="flex flex-wrap gap-2">
                      {notes.key_terms.map((term, i) => (
                        <span key={i} className="px-3 py-1.5 bg-indigo-100 text-indigo-700 rounded-full text-sm font-medium">
                          {term}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Formulae */}
                {notes.formulae?.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">📐 Formulae</h3>
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
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-3">🧠 Mnemonics</h3>
                    <div className="space-y-2">
                      {notes.mnemonics.map((m, i) => (
                        <div key={i} className="flex items-start gap-2 p-3 bg-purple-50 text-purple-800 rounded-lg">
                          <span>💡</span>
                          <span>{m}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            )}
          </div>
        )}


        {/* ============ CHAT TAB ============ */}
        {activeTab === 'chat' && (
          <Card className="h-[600px] flex flex-col overflow-hidden">
            {/* Chat Header */}
            <div className="p-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">💬 AI Tutor</h2>
                <p className="text-sm text-gray-500">Ask questions about your study material</p>
              </div>
              {chatMessages.length > 0 && (
                <Button onClick={resetChat} variant="ghost" size="sm">🔄 Reset</Button>
              )}
            </div>
            
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {chatMessages.length === 0 && (
                <div className="text-center text-gray-400 mt-20">
                  <div className="text-5xl mb-4">💬</div>
                  <p>Start a conversation by asking a question!</p>
                  <p className="text-sm mt-2">Try: "Explain the main concepts" or "What is X?"</p>
                </div>
              )}
              
              {chatMessages.map((msg, idx) => (
                <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`
                    max-w-[80%] p-4 rounded-2xl
                    ${msg.role === 'user' 
                      ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-br-md' 
                      : 'bg-gray-100 text-gray-900 rounded-bl-md'
                    }
                  `}>
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-200/30">
                        <p className="text-xs opacity-70 flex items-center gap-1">
                          {msg.isGrounded ? '✅' : '⚠️'} {msg.sources.length} sources
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 p-4 rounded-2xl rounded-bl-md">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}} />
                      <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>
            
            {/* Input */}
            <div className="p-4 border-t border-gray-100">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask a question..."
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendChatMessage()}
                  className="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all duration-200 placeholder:text-gray-400"
                />
                <Button onClick={sendChatMessage} disabled={loading || !chatInput.trim()}>
                  Send
                </Button>
              </div>
            </div>
          </Card>
        )}


        {/* ============ SOLUTION TAB ============ */}
        {activeTab === 'solution' && (
          <div className="space-y-6">
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">💡 Solution Generator</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Question</label>
                  <textarea
                    value={solutionQuestion}
                    onChange={(e) => setSolutionQuestion(e.target.value)}
                    placeholder="Enter the question you need a solution for..."
                    rows={3}
                    className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none resize-none"
                  />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Topic (optional)</label>
                    <Input value={topic} onChange={setTopic} placeholder="e.g., Heat Treatment" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Marks: {solutionMarks}</label>
                    <input
                      type="range"
                      min="1"
                      max="20"
                      value={solutionMarks}
                      onChange={(e) => setSolutionMarks(parseInt(e.target.value))}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                    />
                  </div>
                </div>
                
                <Button onClick={generateSolution} disabled={loading} size="lg" className="w-full">
                  {loading ? <><LoadingSpinner size="sm" /> Generating...</> : '💡 Generate Solution'}
                </Button>
              </div>
            </Card>

            {solution && (
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">📝 Solution ({solution.marks} marks)</h3>
                
                <div className="prose prose-indigo max-w-none">
                  <div className="p-4 bg-gray-50 rounded-xl mb-4 whitespace-pre-wrap leading-relaxed">
                    {solution.answer}
                  </div>
                </div>
                
                {solution.key_points?.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-semibold text-gray-900 mb-2">🎯 Key Points</h4>
                    <ul className="space-y-1">
                      {solution.key_points.map((point: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-gray-700">
                          <span className="text-green-500">✓</span>
                          <span>{point}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {solution.marking_scheme?.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-semibold text-gray-900 mb-2">📋 Marking Scheme</h4>
                    <ul className="space-y-1">
                      {solution.marking_scheme.map((item: string, i: number) => (
                        <li key={i} className="text-sm text-gray-600 bg-yellow-50 px-3 py-1 rounded">
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </Card>
            )}
          </div>
        )}


        {/* ============ MIND MAP TAB ============ */}
        {activeTab === 'mindmap' && (
          <div className="space-y-6">
            <Button onClick={generateMindMap} disabled={loading} size="lg">
              {loading ? <><LoadingSpinner size="sm" /> Generating...</> : '🗺️ Generate Mind Map'}
            </Button>

            {mindMap && (
              <Card className="p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  🗺️ Mind Map: {topic}
                </h3>
                
                <div className="min-h-[400px] bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl p-6">
                  {/* Simple tree visualization */}
                  <div className="flex flex-col items-center">
                    {mindMap.nodes.map((node, idx) => {
                      const isRoot = !node.parent_id;
                      const level = isRoot ? 0 : 1;
                      
                      return (
                        <div 
                          key={node.id}
                          className={`
                            mb-4 px-6 py-3 rounded-xl shadow-md
                            ${isRoot 
                              ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-xl font-bold' 
                              : 'bg-white text-gray-800 border border-gray-200'
                            }
                            ${level > 0 ? 'ml-8' : ''}
                          `}
                        >
                          {node.label}
                        </div>
                      );
                    })}
                  </div>
                  
                  {/* Stats */}
                  <div className="mt-6 flex justify-center gap-8 text-sm text-gray-600">
                    <span>📍 {mindMap.nodes.length} nodes</span>
                    <span>🔗 {mindMap.edges.length} connections</span>
                  </div>
                </div>
                
                <p className="mt-4 text-sm text-gray-500 text-center">
                  💡 Tip: For a better visualization, export to a mind mapping tool
                </p>
              </Card>
            )}
          </div>
        )}


        {/* ============ DASHBOARD TAB ============ */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {loading ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner size="lg" />
              </div>
            ) : dashboard ? (
              <>
                {/* Top Stats Row: Streak + Due Cards + Exam Readiness */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Streak Card */}
                  <Card className="p-6 bg-gradient-to-br from-orange-50 to-red-50 border-orange-100">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-orange-600">Current Streak</p>
                        <p className="text-4xl font-bold text-orange-600 flex items-center gap-2">
                          🔥 {dashboard.streak.current_streak}
                          <span className="text-lg font-normal text-orange-500">days</span>
                        </p>
                        <p className="text-xs text-orange-500 mt-1">
                          Best: {dashboard.streak.longest_streak} days
                        </p>
                      </div>
                      <div className="text-6xl opacity-20">🔥</div>
                    </div>
                  </Card>

                  {/* Due Cards Summary */}
                  <Card className="p-6 bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-100">
                    <p className="text-sm font-medium text-blue-600 mb-3">Cards Due</p>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="p-2 bg-white/60 rounded-lg">
                        <p className="text-2xl font-bold text-blue-600">{dashboard.due_cards.today}</p>
                        <p className="text-xs text-blue-500">Today</p>
                      </div>
                      <div className="p-2 bg-white/60 rounded-lg">
                        <p className="text-2xl font-bold text-indigo-600">{dashboard.due_cards.this_week}</p>
                        <p className="text-xs text-indigo-500">This Week</p>
                      </div>
                      <div className="p-2 bg-white/60 rounded-lg">
                        <p className="text-2xl font-bold text-purple-600">{dashboard.due_cards.this_month}</p>
                        <p className="text-xs text-purple-500">This Month</p>
                      </div>
                    </div>
                  </Card>

                  {/* Exam Readiness */}
                  <Card className={`p-6 border-2 ${
                    dashboard.exam_readiness.level === 'excellent' ? 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200' :
                    dashboard.exam_readiness.level === 'good' ? 'bg-gradient-to-br from-blue-50 to-cyan-50 border-blue-200' :
                    dashboard.exam_readiness.level === 'moderate' ? 'bg-gradient-to-br from-yellow-50 to-amber-50 border-yellow-200' :
                    'bg-gradient-to-br from-red-50 to-orange-50 border-red-200'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-600">Exam Readiness</p>
                        <p className={`text-4xl font-bold ${
                          dashboard.exam_readiness.level === 'excellent' ? 'text-green-600' :
                          dashboard.exam_readiness.level === 'good' ? 'text-blue-600' :
                          dashboard.exam_readiness.level === 'moderate' ? 'text-yellow-600' :
                          'text-red-600'
                        }`}>
                          {dashboard.exam_readiness.score}%
                        </p>
                        <p className="text-xs text-gray-500 mt-1">{dashboard.exam_readiness.message}</p>
                      </div>
                      <div className="text-5xl">
                        {dashboard.exam_readiness.level === 'excellent' ? '🏆' :
                         dashboard.exam_readiness.level === 'good' ? '📈' :
                         dashboard.exam_readiness.level === 'moderate' ? '📊' : '📚'}
                      </div>
                    </div>
                  </Card>
                </div>

                {/* Overall Stats Row */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <Card className="p-4 text-center">
                    <p className="text-2xl font-bold text-indigo-600">{dashboard.overall.total_quizzes}</p>
                    <p className="text-xs text-gray-500">Quizzes Taken</p>
                  </Card>
                  <Card className="p-4 text-center">
                    <p className="text-2xl font-bold text-purple-600">{dashboard.overall.total_topics}</p>
                    <p className="text-xs text-gray-500">Topics Studied</p>
                  </Card>
                  <Card className="p-4 text-center">
                    <p className="text-2xl font-bold text-green-600">{dashboard.overall.average_score.toFixed(0)}%</p>
                    <p className="text-xs text-gray-500">Average Score</p>
                  </Card>
                  <Card className="p-4 text-center">
                    <p className="text-2xl font-bold text-blue-600">{dashboard.streak.total_cards_reviewed}</p>
                    <p className="text-xs text-gray-500">Cards Reviewed</p>
                  </Card>
                  <Card className="p-4 text-center">
                    <p className="text-2xl font-bold text-orange-600">{dashboard.weekly.total_this_week}</p>
                    <p className="text-xs text-gray-500">This Week</p>
                  </Card>
                </div>

                {/* Activity Heatmap */}
                <Card className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    📅 Activity Calendar
                  </h3>
                  <div className="overflow-x-auto">
                    <div className="min-w-[800px]">
                      {/* Heatmap Grid */}
                      <div className="flex gap-1">
                        {/* Group by weeks */}
                        {Array.from({ length: 53 }, (_, weekIndex) => (
                          <div key={weekIndex} className="flex flex-col gap-1">
                            {Array.from({ length: 7 }, (_, dayIndex) => {
                              const dataIndex = weekIndex * 7 + dayIndex;
                              const day = dashboard.heatmap[dataIndex];
                              if (!day) return <div key={dayIndex} className="w-3 h-3" />;
                              
                              const colors = [
                                'bg-gray-100',
                                'bg-green-200',
                                'bg-green-300',
                                'bg-green-400',
                                'bg-green-600',
                              ];
                              
                              return (
                                <div
                                  key={dayIndex}
                                  className={`w-3 h-3 rounded-sm ${colors[day.level]} cursor-pointer transition-transform hover:scale-125`}
                                  title={`${day.date}: ${day.count} activities`}
                                />
                              );
                            })}
                          </div>
                        ))}
                      </div>
                      {/* Legend */}
                      <div className="flex items-center justify-end gap-2 mt-3 text-xs text-gray-500">
                        <span>Less</span>
                        <div className="w-3 h-3 rounded-sm bg-gray-100" />
                        <div className="w-3 h-3 rounded-sm bg-green-200" />
                        <div className="w-3 h-3 rounded-sm bg-green-300" />
                        <div className="w-3 h-3 rounded-sm bg-green-400" />
                        <div className="w-3 h-3 rounded-sm bg-green-600" />
                        <span>More</span>
                      </div>
                    </div>
                  </div>
                </Card>

                {/* Topic Mastery + Learning Velocity Row */}
                <div className="grid md:grid-cols-2 gap-6">
                  {/* Topic Mastery */}
                  <Card className="p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      🎯 Topic Mastery
                    </h3>
                    {dashboard.topic_mastery.length > 0 ? (
                      <div className="space-y-4">
                        {dashboard.topic_mastery.slice(0, 8).map((topic, i) => (
                          <div key={i}>
                            <div className="flex justify-between items-center mb-1">
                              <span className="text-sm font-medium text-gray-700 truncate max-w-[200px]">
                                {topic.topic}
                              </span>
                              <span className={`text-sm font-bold ${
                                topic.mastery_percent >= 85 ? 'text-green-600' :
                                topic.mastery_percent >= 60 ? 'text-blue-600' :
                                topic.mastery_percent >= 40 ? 'text-yellow-600' :
                                'text-red-600'
                              }`}>
                                {topic.mastery_percent.toFixed(0)}%
                              </span>
                            </div>
                            <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                              <div 
                                className={`h-full rounded-full transition-all duration-500 ${
                                  topic.mastery_percent >= 85 ? 'bg-gradient-to-r from-green-400 to-green-600' :
                                  topic.mastery_percent >= 60 ? 'bg-gradient-to-r from-blue-400 to-blue-600' :
                                  topic.mastery_percent >= 40 ? 'bg-gradient-to-r from-yellow-400 to-yellow-600' :
                                  'bg-gradient-to-r from-red-400 to-red-600'
                                }`}
                                style={{ width: `${topic.mastery_percent}%` }}
                              />
                            </div>
                            <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                              <span>{topic.attempts} attempts</span>
                              <span className={`px-1.5 py-0.5 rounded text-xs ${
                                topic.mastery_level === 'mastered' ? 'bg-green-100 text-green-700' :
                                topic.mastery_level === 'familiar' ? 'bg-blue-100 text-blue-700' :
                                topic.mastery_level === 'learning' ? 'bg-yellow-100 text-yellow-700' :
                                'bg-gray-100 text-gray-600'
                              }`}>
                                {topic.mastery_level}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-gray-500 text-center py-8">Complete quizzes to see topic mastery</p>
                    )}
                  </Card>

                  {/* Learning Velocity Chart */}
                  <Card className="p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                      📈 Learning Velocity
                    </h3>
                    <div className="space-y-3">
                      {dashboard.learning_velocity.map((week, i) => (
                        <div key={i} className="flex items-center gap-3">
                          <span className="text-xs text-gray-500 w-16">{week.week}</span>
                          <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden relative">
                            {week.average_score !== null ? (
                              <>
                                <div 
                                  className="h-full bg-gradient-to-r from-indigo-400 to-purple-500 rounded-full transition-all duration-500"
                                  style={{ width: `${week.average_score}%` }}
                                />
                                <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white mix-blend-difference">
                                  {week.average_score.toFixed(0)}%
                                </span>
                              </>
                            ) : (
                              <span className="absolute inset-0 flex items-center justify-center text-xs text-gray-400">
                                No data
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-gray-400 w-12">{week.quizzes} quiz</span>
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-gray-400 mt-4 text-center">
                      Weekly average scores over the last 8 weeks
                    </p>
                  </Card>
                </div>

                {/* Readiness Breakdown */}
                <Card className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    🎯 Readiness Breakdown
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-4 bg-purple-50 rounded-xl">
                      <p className="text-2xl font-bold text-purple-600">{dashboard.exam_readiness.breakdown.mastery}%</p>
                      <p className="text-xs text-purple-500 mt-1">Mastery (40%)</p>
                      <div className="w-full h-1.5 bg-purple-200 rounded-full mt-2">
                        <div className="h-full bg-purple-500 rounded-full" style={{ width: `${dashboard.exam_readiness.breakdown.mastery}%` }} />
                      </div>
                    </div>
                    <div className="text-center p-4 bg-blue-50 rounded-xl">
                      <p className="text-2xl font-bold text-blue-600">{dashboard.exam_readiness.breakdown.consistency}%</p>
                      <p className="text-xs text-blue-500 mt-1">Consistency (30%)</p>
                      <div className="w-full h-1.5 bg-blue-200 rounded-full mt-2">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${dashboard.exam_readiness.breakdown.consistency}%` }} />
                      </div>
                    </div>
                    <div className="text-center p-4 bg-green-50 rounded-xl">
                      <p className="text-2xl font-bold text-green-600">{dashboard.exam_readiness.breakdown.coverage}%</p>
                      <p className="text-xs text-green-500 mt-1">Coverage (20%)</p>
                      <div className="w-full h-1.5 bg-green-200 rounded-full mt-2">
                        <div className="h-full bg-green-500 rounded-full" style={{ width: `${dashboard.exam_readiness.breakdown.coverage}%` }} />
                      </div>
                    </div>
                    <div className="text-center p-4 bg-orange-50 rounded-xl">
                      <p className="text-2xl font-bold text-orange-600">{dashboard.exam_readiness.breakdown.recency}%</p>
                      <p className="text-xs text-orange-500 mt-1">Recency (10%)</p>
                      <div className="w-full h-1.5 bg-orange-200 rounded-full mt-2">
                        <div className="h-full bg-orange-500 rounded-full" style={{ width: `${dashboard.exam_readiness.breakdown.recency}%` }} />
                      </div>
                    </div>
                  </div>
                </Card>
              </>
            ) : (
              <Card className="p-12 text-center">
                <div className="text-5xl mb-4">📊</div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">No Progress Data Yet</h3>
                <p className="text-gray-500 mb-4">Complete some quizzes to start tracking your progress!</p>
                <Button onClick={loadDashboard}>Refresh Dashboard</Button>
              </Card>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-100 mt-12 py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
          <p>NeuroForge — Adaptive Learning Engine • Built with ❤️ for better learning</p>
        </div>
      </footer>
    </div>
  );
}
