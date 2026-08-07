// NeuroForge API Client - Enhanced Version

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  async uploadDocument(file: File, asyncMode: boolean = false) {
    const formData = new FormData();
    formData.append('file', file);

    const url = asyncMode 
      ? `${this.baseUrl}/upload?async_mode=true`
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
  async generateQuiz(topic: string, numQuestions: number = 10, difficulty?: string) {
    return this.request<{ status: string; topic: string; count: number; questions: QuizQuestion[] }>('/quiz', {
      method: 'POST',
      body: JSON.stringify({
        topic,
        num_questions: numQuestions,
        difficulty: difficulty || null,
      }),
    });
  }

  async generateFlashcards(topic: string, numCards: number = 10, difficulty?: string) {
    return this.request<{ status: string; topic: string; count: number; flashcards: Flashcard[] }>('/flashcards', {
      method: 'POST',
      body: JSON.stringify({
        topic,
        num_cards: numCards,
        difficulty: difficulty || null,
      }),
    });
  }

  async generateNotes(topic: string) {
    return this.request<{ status: string; topic: string; notes: RevisionNote }>('/notes', {
      method: 'POST',
      body: JSON.stringify({ topic }),
    });
  }

  async generateSolution(question: string, topic: string = 'General', marks: number = 5) {
    return this.request<{
      status: string;
      question: string;
      topic: string;
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
      body: JSON.stringify({ question, topic, marks }),
    });
  }

  async generateAdditionalInfo(topic: string) {
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
      body: JSON.stringify({ topic }),
    });
  }

  async generateMindMap(topic: string, maxDepth: number = 3) {
    return this.request<{
      status: string;
      topic: string;
      mindmap: MindMap;
    }>('/mindmap', {
      method: 'POST',
      body: JSON.stringify({ topic, max_depth: maxDepth }),
    });
  }

  // Chat
  async chat(message: string, sessionId?: string) {
    return this.request<{
      answer: string;
      sources: string[];
      is_grounded: boolean;
      session_id: string;
    }>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, session_id: sessionId }),
    });
  }

  async resetChat(sessionId: string) {
    return this.request<{ status: string; message: string }>(`/chat/${sessionId}`, {
      method: 'DELETE',
    });
  }

  // Progress
  async getProgress() {
    return this.request<LearningProgress>('/progress');
  }

  async getTopicProgress(topic: string) {
    return this.request<{
      topic: string;
      progress: any;
      mastery_level: string;
    }>(`/progress/${encodeURIComponent(topic)}`);
  }

  async recordScore(topic: string, score: number) {
    return this.request<{ status: string; topic: string; score: number; mastery_level: string }>('/progress/score', {
      method: 'POST',
      body: JSON.stringify({ topic, score }),
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
  async getDashboard() {
    return this.request<DashboardData>('/dashboard');
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
}

export const api = new NeuroForgeAPI();
export default api;
