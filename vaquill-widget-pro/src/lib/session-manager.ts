/**
 * Unified Session Manager
 *
 * Single source of truth for session management across Voice and Chat modes.
 * Solves the conversation history inconsistency by:
 * 1. Centralizing all session_id storage and retrieval
 * 2. Coordinating between Voice and Chat modes
 * 3. Implementing robust error handling with retry logic
 * 4. Providing event-based notifications for session changes
 */

const STORAGE_KEY = 'vaquill_conversation';
const SESSION_CHANGE_EVENT = 'session_change';

// Retry configuration for network operations
const RETRY_CONFIG = {
  maxAttempts: 3,
  baseDelay: 1000,  // 1 second
  maxDelay: 5000,   // 5 seconds
  backoffMultiplier: 2
};

export type SessionState = 'idle' | 'initializing' | 'active' | 'error' | 'restoring';

export interface StoredSession {
  sessionId: string;
  createdAt: number;
  lastUsedAt: number;
  source: 'chat' | 'voice';  // Track which mode created the session
}

export interface SessionChangeEvent {
  sessionId: string | null;
  previousSessionId: string | null;
  state: SessionState;
  source: 'chat' | 'voice' | 'system';
}

type SessionChangeCallback = (event: SessionChangeEvent) => void;

class SessionManager {
  private currentSessionId: string | null = null;
  private state: SessionState = 'idle';
  private listeners: Set<SessionChangeCallback> = new Set();
  private initializationPromise: Promise<string | null> | null = null;
  private lastError: Error | null = null;

  constructor() {
    // Load session from storage on initialization
    if (typeof window !== 'undefined') {
      const stored = this.loadFromStorage();
      if (stored) {
        this.currentSessionId = stored.sessionId;
        this.state = 'active';
        console.log('[SessionManager] Initialized with stored session:', stored.sessionId);
      }
    }
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.currentSessionId;
  }

  /**
   * Get current session state
   */
  getState(): SessionState {
    return this.state;
  }

  /**
   * Get last error if any
   */
  getLastError(): Error | null {
    return this.lastError;
  }

  /**
   * Check if session is ready for use
   */
  isReady(): boolean {
    return this.state === 'active' && this.currentSessionId !== null;
  }

  /**
   * Initialize or get existing session
   * This is the main entry point - handles both restore and create
   */
  async initialize(source: 'chat' | 'voice' = 'chat'): Promise<string | null> {
    // If already initializing, return the pending promise
    if (this.initializationPromise) {
      console.log('[SessionManager] Already initializing, waiting...');
      return this.initializationPromise;
    }

    // If already active, return current session
    if (this.state === 'active' && this.currentSessionId) {
      console.log('[SessionManager] Already active with session:', this.currentSessionId);
      this.updateLastUsed();
      return this.currentSessionId;
    }

    this.initializationPromise = this.doInitialize(source);

    try {
      const sessionId = await this.initializationPromise;
      return sessionId;
    } finally {
      this.initializationPromise = null;
    }
  }

  private async doInitialize(source: 'chat' | 'voice'): Promise<string | null> {
    this.setState('initializing');

    // Try to restore existing session first
    const stored = this.loadFromStorage();

    if (stored?.sessionId) {
      console.log('[SessionManager] Attempting to restore session:', stored.sessionId);

      const restored = await this.restoreSession(stored.sessionId);
      if (restored) {
        return this.currentSessionId;
      }

      console.log('[SessionManager] Restore failed, creating new session');
    }

    // Create new session
    return this.createSession(source);
  }

  /**
   * Create a new session via Vaquill API
   */
  async createSession(source: 'chat' | 'voice' = 'chat'): Promise<string | null> {
    const previousSessionId = this.currentSessionId;
    this.setState('initializing');
    this.lastError = null;

    try {
      const sessionId = await this.retryOperation(async () => {
        const response = await fetch('/api/chat/conversations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
          throw new Error(`Failed to create conversation: ${response.status}`);
        }

        const data = await response.json();
        return data.session_id;
      });

      if (sessionId) {
        this.setSession(sessionId, source);
        this.notifyListeners({
          sessionId,
          previousSessionId,
          state: 'active',
          source
        });
        console.log('[SessionManager] Created new session:', sessionId);
        return sessionId;
      }

      throw new Error('No session_id returned from API');
    } catch (error: any) {
      this.lastError = error;
      this.setState('error');
      console.error('[SessionManager] Failed to create session:', error);
      return null;
    }
  }

  /**
   * Restore an existing session with retry logic
   */
  async restoreSession(sessionId: string): Promise<boolean> {
    this.setState('restoring');
    this.lastError = null;

    try {
      const isValid = await this.retryOperation(async () => {
        const response = await fetch(`/api/chat/conversations/${sessionId}`, {
          method: 'GET',
        });

        if (response.status === 404) {
          // Session doesn't exist - this is a definitive answer, don't retry
          console.log('[SessionManager] Session not found (404):', sessionId);
          return false;
        }

        if (!response.ok) {
          // Other errors should trigger retry
          throw new Error(`Failed to validate session: ${response.status}`);
        }

        return true;
      }, (error, attempt) => {
        // Don't retry 404s - they're definitive
        if (error.message?.includes('404')) {
          return false;
        }
        return attempt < RETRY_CONFIG.maxAttempts;
      });

      if (isValid) {
        this.setSession(sessionId, 'system' as any);
        console.log('[SessionManager] Restored session:', sessionId);
        return true;
      }

      // Session invalid - clear storage
      this.clearStorage();
      this.setState('idle');
      return false;
    } catch (error: any) {
      this.lastError = error;

      // On network error, don't clear storage - user might just be offline
      if (error.name === 'TypeError' || error.message?.includes('network')) {
        console.warn('[SessionManager] Network error during restore, keeping stored session');
        // Keep the stored session in case user comes back online
        this.currentSessionId = sessionId;
        this.setState('error');
        return false;
      }

      // For other errors, clear and start fresh
      this.clearStorage();
      this.setState('idle');
      console.error('[SessionManager] Failed to restore session:', error);
      return false;
    }
  }

  /**
   * Set session ID (called by components when they create sessions externally)
   */
  setSession(sessionId: string, source: 'chat' | 'voice' | 'system'): void {
    const previousSessionId = this.currentSessionId;

    if (previousSessionId === sessionId) {
      // Same session, just update last used
      this.updateLastUsed();
      return;
    }

    this.currentSessionId = sessionId;
    this.setState('active');
    this.saveToStorage(sessionId, source === 'system' ? 'chat' : source);

    this.notifyListeners({
      sessionId,
      previousSessionId,
      state: 'active',
      source
    });

    console.log('[SessionManager] Session set:', sessionId, 'source:', source);
  }

  /**
   * Clear current session (for new conversation)
   */
  clearSession(): void {
    const previousSessionId = this.currentSessionId;
    this.currentSessionId = null;
    this.state = 'idle';
    this.clearStorage();

    this.notifyListeners({
      sessionId: null,
      previousSessionId,
      state: 'idle',
      source: 'system'
    });

    console.log('[SessionManager] Session cleared');
  }

  /**
   * Subscribe to session changes
   */
  onSessionChange(callback: SessionChangeCallback): () => void {
    this.listeners.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Wait for session to be ready
   */
  async waitForSession(source: 'chat' | 'voice' = 'chat', timeoutMs: number = 10000): Promise<string | null> {
    if (this.isReady()) {
      return this.currentSessionId;
    }

    // If initializing, wait for it
    if (this.initializationPromise) {
      return this.initializationPromise;
    }

    // Otherwise, initialize
    return this.initialize(source);
  }

  // Private methods

  private setState(state: SessionState): void {
    this.state = state;
  }

  private loadFromStorage(): StoredSession | null {
    if (typeof window === 'undefined') return null;

    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return null;

      const data = JSON.parse(stored);

      // Validate required fields
      if (!data.sessionId || !data.createdAt) {
        this.clearStorage();
        return null;
      }

      return data as StoredSession;
    } catch (error) {
      console.error('[SessionManager] Failed to load from storage:', error);
      this.clearStorage();
      return null;
    }
  }

  private saveToStorage(sessionId: string, source: 'chat' | 'voice'): void {
    if (typeof window === 'undefined') return;

    try {
      const data: StoredSession = {
        sessionId,
        createdAt: this.loadFromStorage()?.createdAt || Date.now(),
        lastUsedAt: Date.now(),
        source
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (error) {
      console.error('[SessionManager] Failed to save to storage:', error);
    }
  }

  private updateLastUsed(): void {
    if (typeof window === 'undefined' || !this.currentSessionId) return;

    try {
      const stored = this.loadFromStorage();
      if (stored) {
        stored.lastUsedAt = Date.now();
        localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
      }
    } catch (error) {
      console.error('[SessionManager] Failed to update last used:', error);
    }
  }

  private clearStorage(): void {
    if (typeof window === 'undefined') return;

    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error('[SessionManager] Failed to clear storage:', error);
    }
  }

  private notifyListeners(event: SessionChangeEvent): void {
    this.listeners.forEach(callback => {
      try {
        callback(event);
      } catch (error) {
        console.error('[SessionManager] Listener error:', error);
      }
    });

    // Also dispatch a custom event for cross-component communication
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent(SESSION_CHANGE_EVENT, { detail: event }));
    }
  }

  private async retryOperation<T>(
    operation: () => Promise<T>,
    shouldRetry?: (error: any, attempt: number) => boolean
  ): Promise<T> {
    let lastError: any;
    let delay = RETRY_CONFIG.baseDelay;

    for (let attempt = 1; attempt <= RETRY_CONFIG.maxAttempts; attempt++) {
      try {
        return await operation();
      } catch (error: any) {
        lastError = error;

        // Check if we should retry
        if (shouldRetry && !shouldRetry(error, attempt)) {
          throw error;
        }

        if (attempt === RETRY_CONFIG.maxAttempts) {
          break;
        }

        console.log(`[SessionManager] Retry attempt ${attempt}/${RETRY_CONFIG.maxAttempts} after ${delay}ms`);
        await this.sleep(delay);

        // Exponential backoff
        delay = Math.min(delay * RETRY_CONFIG.backoffMultiplier, RETRY_CONFIG.maxDelay);
      }
    }

    throw lastError;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Export singleton instance
export const sessionManager = new SessionManager();

// Export event name for listeners
export { SESSION_CHANGE_EVENT };

// Legacy exports for backward compatibility
export function saveConversation(sessionId: string): void {
  sessionManager.setSession(sessionId, 'chat');
}

export function loadConversation(): StoredSession | null {
  const sessionId = sessionManager.getSessionId();
  if (!sessionId) return null;

  // Return in legacy format
  return {
    sessionId,
    createdAt: Date.now(),
    lastUsedAt: Date.now(),
    source: 'chat'
  };
}

export function clearConversation(): void {
  sessionManager.clearSession();
}

export function hasStoredConversation(): boolean {
  return sessionManager.getSessionId() !== null;
}
