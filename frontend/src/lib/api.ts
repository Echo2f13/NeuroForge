// NeuroForge API Client - Enhanced Version

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ---------------------------------------------------------------------------
// Subject Types
// ---------------------------------------------------------------------------

export type SubjectStatus = 'active' | 'archived';

export interface SubjectSettings {
  auto_generate_flashcards: boolean;
  default_quiz_length: number;
  preferred_difficulty: string | null;
  enable_spaced_repetition: boolean;
  daily_review_goal: number;
}

export interface Subject {
  id: string;
  name: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  status: SubjectStatus;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  last_activity_at: string | null;
  settings: SubjectSettings;
}

export interface SubjectSummary {
  id: string;
  name: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  status: SubjectStatus;
  is_default: boolean;
  document_count: number;
  chunk_count: number;
  concept_count: number;
  quiz_count: number;
  average_score: number;
  mastery_percent: number;
  last_activity_at: string | null;
}

export interface SubjectDocument {
  id: string;
  subject_id: string;
  filename: string;
  file_type: string;
  chunk_count: number;
  concept_count: number;
  file_size_bytes: number | null;
  uploaded_at: string;
}

export interface SubjectStats {
  document_count: number;
  chunk_count: number;
  concept_count: number;
  quiz_count: number;
  average_score: number;
  mastery_percent: number;
}

export interface CreateSubjectInput {
  name: string;
  description?: string;
  color?: string;
  icon?: string;
}

export interface UpdateSubjectInput {
  name?: string;
  description?: string;
  color?: string;
  icon?: string;
}

// ---------------------------------------------------------------------------
// Existing Types
// ---------------------------------------------------------------------------

export interface QuizQuestion {
  id: string;
  question: string;
  question_type: 'mcq' | 'short_answer' | 'true_false';
  options: string[] | null;
  correct_answer: string;
  explanation: string;
  topic: string;
  difficulty: string;
}

export interface Flashcard {
  id: string;
  question: string;
  answer: string;
  hint: string | null;
  mnemonic: string | null;
  related_topics: string[];
  difficulty: string;
}

export interface RevisionNote {
  topic: string;
  subtopics: Array<{
    title: string;
    points?: string[];
    key_points?: string[];
    bullet_points?: string[];
    importance: string;
  }>;
  key_terms: string[];
  formulae: string[];
  mnemonics: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  isGrounded?: boolean;
}

export interface LearningProgress {
  stats: {
    total_quizzes: number;
    total_topics: number;
    average_score: number;
    study_time_minutes: number;
    weak_count: number;
    strong_count: number;
  };
  weak_topics: string[];
  strong_topics: string[];
}

// Dashboard Types
export interface DashboardData {
  streak: {
    current_streak: number;
    longest_streak: number;
    total_cards_reviewed: number;
  };
  overall: {
    total_quizzes: number;
    total_topics: number;
    average_score: number;
    study_time_minutes: number;
    weak_count: number;
    strong_count: number;
  };
  weekly: {
    reviews_this_week: number;
    quizzes_this_week: number;
    total_this_week: number;
  };
  monthly: {
    reviews_this_month: number;
    quizzes_this_month: number;
    total_this_month: number;
  };
  due_cards: {
    today: number;
    this_week: number;
    this_month: number;
    card_ids_today: string[];
  };
  topic_mastery: Array<{
    topic: string;
    mastery_percent: number;
    mastery_level: string;
    attempts: number;
    last_attempted: string | null;
  }>;
  heatmap: Array<{
    date: string;
    count: number;
    level: number; // 0-4
  }>;
  exam_readiness: {
    score: number;
    level: 'excellent' | 'good' | 'moderate' | 'needs_work';
    message: string;
    breakdown: {
      mastery: number;
      consistency: number;
      coverage: number;
      recency: number;
    };
  };
  learning_velocity: Array<{
    week: string;
    week_start: string;
    average_score: number | null;
    quizzes: number;
  }>;
}

export interface UploadStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'extracting' | 'completed' | 'failed';
  progress: number;
  message: string;
  document_id: string | null;
  chunks_created: number;
  concepts_extracted: number;
  error: string | null;
}

export interface MindMap {
  nodes: Array<{
    id: string;
    label: string;
    type: string;
    parent_id: string | null;
  }>;
  edges: Array<{
    source: string;
    target: string;
    label?: string;
  }>;
}

// ---------------------------------------------------------------------------
// Source Attribution Types
// ---------------------------------------------------------------------------

export interface BoundingBox {
  x0: number;  // Left coordinate (0-100%)
  y0: number;  // Top coordinate (0-100%)
  x1: number;  // Right coordinate (0-100%)
  y1: number;  // Bottom coordinate (0-100%)
  page_width: number;   // Original page width in points
  page_height: number;  // Original page height in points
}

export interface Citation {
  id: string;
  chunk_id: string;
  document_id: string;
  document_name: string;
  document_format: 'pdf' | 'docx' | 'txt' | 'image' | 'markdown' | 'pptx';
  page_number: number | null;
  paragraph_number: number | null;
  excerpt: string;
  full_text: string;
  relevance_score: number;
  bounding_boxes: BoundingBox[] | null;
  start_char: number;
  end_char: number;
  line_start: number | null;
  line_end: number | null;
  section_heading: string | null;
}

export interface CitationGroup {
  item_id: string;
  item_type: 'quiz' | 'flashcard' | 'note' | 'chat' | 'solution' | 'mindmap';
  citations: Citation[];
  primary_citation_id: string | null;
}

export interface StoredDocument {
  id: string;
  subject_id: string;
  filename: string;
  format: string;
  storage_path: string;
  file_size: number;
  total_pages: number | null;
  uploaded_at: string;
  checksum: string;
  title: string | null;
  author: string | null;
}

export interface HighlightRange {
  page: number;
  bbox: BoundingBox;
  start_char: number;
  end_char: number;
}

export interface ChunkInfo {
  id: string;
  content?: string;
  metadata: {
    document_id?: string;
    chunk_index?: number;
    page_number?: number;
    paragraph_number?: number;
    section_heading?: string;
    start_char?: number;
    end_char?: number;
    source_file?: string;
    document_format?: string;
    bounding_boxes?: BoundingBox[];
  };
}

class NeuroForgeAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // Health & Stats
  async getHealth() {
    return this.request<{ status: string; message: string; components: Record<string, boolean> }>('/health');
  }

  async getStats() {
    return this.request<{
      knowledge_base: { chunks: number; concepts: number; graph_nodes: number };
      learning: LearningProgress['stats'];
    }>('/stats');
  }

  // Document Upload (Sync)
  async uploadDocument(file: File, asyncMode: boolean = false, subjectId?: string) {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams();
    if (asyncMode) params.append('async_mode', 'true');
    if (subjectId) params.append('subject_id', subjectId);
    
    const queryString = params.toString();
    const url = queryString 
      ? `${this.baseUrl}/upload?${queryString}`
      : `${this.baseUrl}/upload`;

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
  }

  // Upload Status (for async uploads)
  async getUploadStatus(jobId: string): Promise<UploadStatus> {
    return this.request<UploadStatus>(`/upload/status/${jobId}`);
  }

  // Poll upload status until complete
  async waitForUpload(
    jobId: string, 
    onProgress?: (status: UploadStatus) => void,
    pollInterval: number = 2000
  ): Promise<UploadStatus> {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const status = await this.getUploadStatus(jobId);
          onProgress?.(status);
          
          if (status.status === 'completed') {
            resolve(status);
          } else if (status.status === 'failed') {
            reject(new Error(status.error || 'Upload failed'));
          } else {
            setTimeout(poll, pollInterval);
          }
        } catch (err) {
          reject(err);
        }
      };
      poll();
    });
  }

  async uploadYouTube(url: string) {
    const formData = new FormData();
    formData.append('url', url);

    const response = await fetch(`${this.baseUrl}/upload/youtube`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'YouTube upload failed' }));
      throw new Error(error.detail || 'YouTube upload failed');
    }

    return response.json();
  }

  // Content Generation
  async generateQuiz(topic: string, numQuestions: number = 10, difficulty?: string, subjectId?: string) {
    return this.request<{ status: string; topic: string; subject_id: string; count: number; questions: QuizQuestion[] }>('/quiz', {
      method: 'POST',
      body: JSON.stringify({
        topic,
        num_questions: numQuestions,
        difficulty: difficulty || null,
        subject_id: subjectId || 'general',
      }),
    });
  }

  async generateFlashcards(topic: string, numCards: number = 10, difficulty?: string, subjectId?: string) {
    return this.request<{ status: string; topic: string; subject_id: string; count: number; flashcards: Flashcard[] }>('/flashcards', {
      method: 'POST',
      body: JSON.stringify({
        topic,
        num_cards: numCards,
        difficulty: difficulty || null,
        subject_id: subjectId || 'general',
      }),
    });
  }

  async generateNotes(topic: string, subjectId?: string) {
    return this.request<{ status: string; topic: string; subject_id: string; notes: RevisionNote }>('/notes', {
      method: 'POST',
      body: JSON.stringify({ 
        topic,
        subject_id: subjectId || 'general',
      }),
    });
  }

  async generateSolution(question: string, topic: string = 'General', marks: number = 5, subjectId?: string) {
    return this.request<{
      status: string;
      question: string;
      topic: string;
      subject_id: string;
      marks: number;
      solution: {
        question: string;
        marks: number;
        answer: string;
        marking_scheme: string[];
        key_points: string[];
        topic: string;
      };
    }>('/solution', {
      method: 'POST',
      body: JSON.stringify({ 
        question, 
        topic, 
        marks,
        subject_id: subjectId || 'general',
      }),
    });
  }

  async generateAdditionalInfo(topic: string, subjectId?: string) {
    return this.request<{
      status: string;
      topic: string;
      additional_info: {
        applications: string[];
        industry_uses: string[];
        common_mistakes: string[];
        interview_questions: string[];
      };
    }>('/additional-info', {
      method: 'POST',
      body: JSON.stringify({ 
        topic,
        subject_id: subjectId || 'general',
      }),
    });
  }

  async generateMindMap(topic: string, maxDepth: number = 3, subjectId?: string) {
    return this.request<{
      status: string;
      topic: string;
      subject_id: string;
      mindmap: MindMap;
    }>('/mindmap', {
      method: 'POST',
      body: JSON.stringify({ 
        topic, 
        max_depth: maxDepth,
        subject_id: subjectId || 'general',
      }),
    });
  }

  // Chat
  async chat(message: string, sessionId?: string, subjectId?: string) {
    return this.request<{
      answer: string;
      sources: string[];
      is_grounded: boolean;
      session_id: string;
    }>('/chat', {
      method: 'POST',
      body: JSON.stringify({ 
        message, 
        session_id: sessionId,
        subject_id: subjectId || 'general',
      }),
    });
  }

  async resetChat(sessionId: string) {
    return this.request<{ status: string; message: string }>(`/chat/${sessionId}`, {
      method: 'DELETE',
    });
  }

  // Progress
  async getProgress(subjectId?: string) {
    const params = subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : '';
    return this.request<LearningProgress & { subject_id: string }>(`/progress${params}`);
  }

  async getTopicProgress(topic: string) {
    return this.request<{
      topic: string;
      progress: any;
      mastery_level: string;
    }>(`/progress/${encodeURIComponent(topic)}`);
  }

  async recordScore(topic: string, score: number, subjectId?: string) {
    return this.request<{ status: string; topic: string; subject_id: string; score: number; mastery_level: string }>('/progress/score', {
      method: 'POST',
      body: JSON.stringify({ 
        topic, 
        score,
        subject_id: subjectId || 'general',
      }),
    });
  }

  // Spaced Repetition
  async getDueCards(date?: string) {
    const params = date ? `?date=${date}` : '';
    return this.request<{ date: string; due_count: number; card_ids: string[] }>(`/spaced-repetition/due${params}`);
  }

  async reviewCard(cardId: string, quality: number) {
    return this.request<{
      status: string;
      card_id: string;
      quality: number;
      next_review: string;
      interval_days: number;
    }>('/spaced-repetition/review', {
      method: 'POST',
      body: JSON.stringify({ card_id: cardId, quality }),
    });
  }

  // Dashboard
  async getDashboard(subjectId?: string) {
    const params = subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : '';
    return this.request<DashboardData & { subject_id: string }>(`/dashboard${params}`);
  }

  async recordReview(cardId: string, quality: number) {
    return this.request<{
      status: string;
      card_id: string;
      quality: number;
      next_review: string;
      interval_days: number;
      current_streak: number;
    }>(`/dashboard/record-review?card_id=${encodeURIComponent(cardId)}&quality=${quality}`, {
      method: 'POST',
    });
  }

  // Search
  async search(query: string, topK: number = 5, method: string = 'semantic') {
    return this.request<{ 
      query: string; 
      method: string; 
      count: number; 
      results: Array<{
        id: string;
        content: string;
        score: number;
        metadata: any;
      }>;
    }>(
      `/search?query=${encodeURIComponent(query)}&top_k=${topK}&method=${method}`
    );
  }

  // Multi-agent orchestrator
  async process(query: string) {
    return this.request<{
      status: string;
      intent: string;
      parameters: any;
      result: any;
      quality_check: any;
      memory_update: any;
    }>('/process', {
      method: 'POST',
      body: JSON.stringify({ query }),
    });
  }

  // ---------------------------------------------------------------------------
  // Subject Management
  // ---------------------------------------------------------------------------

  async createSubject(data: CreateSubjectInput) {
    return this.request<{
      status: string;
      message: string;
      subject: Subject;
    }>('/subjects', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async listSubjects(includeArchived: boolean = false, sortBy: string = 'last_activity') {
    return this.request<{
      subjects: SubjectSummary[];
      total_count: number;
      active_count: number;
      archived_count: number;
    }>(`/subjects?include_archived=${includeArchived}&sort_by=${sortBy}`);
  }

  async getSubject(subjectId: string) {
    return this.request<{
      subject: Subject;
      stats: SubjectStats;
    }>(`/subjects/${encodeURIComponent(subjectId)}`);
  }

  async updateSubject(subjectId: string, data: UpdateSubjectInput) {
    return this.request<{
      status: string;
      subject: Subject;
    }>(`/subjects/${encodeURIComponent(subjectId)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteSubject(subjectId: string, force: boolean = false) {
    return this.request<{
      status: string;
      message: string;
    }>(`/subjects/${encodeURIComponent(subjectId)}?force=${force}`, {
      method: 'DELETE',
    });
  }

  async archiveSubject(subjectId: string) {
    return this.request<{
      status: string;
      message: string;
      subject: Subject;
    }>(`/subjects/${encodeURIComponent(subjectId)}/archive`, {
      method: 'POST',
    });
  }

  async restoreSubject(subjectId: string) {
    return this.request<{
      status: string;
      message: string;
      subject: Subject;
    }>(`/subjects/${encodeURIComponent(subjectId)}/restore`, {
      method: 'POST',
    });
  }

  async getSubjectDocuments(subjectId: string) {
    return this.request<{
      subject_id: string;
      documents: SubjectDocument[];
      total_count: number;
    }>(`/subjects/${encodeURIComponent(subjectId)}/documents`);
  }

  async getSubjectStats(subjectId: string) {
    return this.request<{
      subject_id: string;
      stats: SubjectStats;
    }>(`/subjects/${encodeURIComponent(subjectId)}/stats`);
  }

  // ---------------------------------------------------------------------------
  // Source Attribution & Citations
  // ---------------------------------------------------------------------------

  /**
   * Get full citation data for a single chunk.
   */
  async getCitation(chunkId: string, subjectId: string = 'general') {
    return this.request<{
      status: string;
      citation: Citation;
    }>(`/chunks/${encodeURIComponent(chunkId)}/citation?subject_id=${encodeURIComponent(subjectId)}`);
  }

  /**
   * Get citations for multiple chunks at once.
   */
  async getCitationsBatch(chunkIds: string[], subjectId: string = 'general') {
    return this.request<{
      status: string;
      citations: Citation[];
      count: number;
    }>('/citations/batch', {
      method: 'POST',
      body: JSON.stringify({
        chunk_ids: chunkIds,
        subject_id: subjectId,
      }),
    });
  }

  /**
   * Get document file URL for viewing.
   */
  getDocumentFileUrl(subjectId: string, docId: string): string {
    return `${this.baseUrl}/subjects/${encodeURIComponent(subjectId)}/documents/${encodeURIComponent(docId)}/file`;
  }

  /**
   * Get document metadata.
   */
  async getDocumentMetadata(subjectId: string, docId: string) {
    return this.request<{
      status: string;
      document: StoredDocument;
    }>(`/subjects/${encodeURIComponent(subjectId)}/documents/${encodeURIComponent(docId)}/metadata`);
  }

  /**
   * Get all chunks from a document.
   */
  async getDocumentChunks(subjectId: string, docId: string, includeContent: boolean = true) {
    return this.request<{
      status: string;
      document_id: string;
      subject_id: string;
      chunks: ChunkInfo[];
      count: number;
    }>(`/subjects/${encodeURIComponent(subjectId)}/documents/${encodeURIComponent(docId)}/chunks?include_content=${includeContent}`);
  }

  /**
   * List all stored documents for a subject (with file viewing support).
   */
  async listStoredDocuments(subjectId: string) {
    return this.request<{
      subject_id: string;
      documents: SubjectDocument[];
      total_count: number;
    }>(`/subjects/${encodeURIComponent(subjectId)}/documents`);
  }
}

export const api = new NeuroForgeAPI();
export default api;
