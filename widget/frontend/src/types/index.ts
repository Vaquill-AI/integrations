export interface Source {
  caseName?: string | null;
  citation?: string | null;
  court?: string | null;
  excerpt?: string | null;
  pdfUrl?: string | null;
  relevanceScore?: number | null;
}

export interface ChatHistoryItem {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  questionInterpreted?: string | null;
  mode?: string | null;
  processingTimeMs?: number | null;
}

export interface WidgetInfo {
  title: string;
  mode: string;
  branding: {
    primaryColor: string;
    logoText: string;
  };
  suggestedQuestions: string[];
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  id: string;
  sources?: Source[];
  questionInterpreted?: string | null;
  mode?: string | null;
}
