/**
 * useSession Hook
 *
 * React hook for accessing the unified SessionManager.
 * Provides reactive session state and methods for both Chat and Voice modes.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  sessionManager,
  SessionState,
  SessionChangeEvent,
  SESSION_CHANGE_EVENT
} from '@/lib/session-manager';

export interface UseSessionOptions {
  /**
   * Source mode - 'chat' or 'voice'
   * Used for tracking which mode created/uses the session
   */
  source: 'chat' | 'voice';

  /**
   * Auto-initialize session on mount
   * Default: true
   */
  autoInitialize?: boolean;

  /**
   * Callback when session changes
   */
  onSessionChange?: (event: SessionChangeEvent) => void;
}

export interface UseSessionReturn {
  /**
   * Current session ID (null if not initialized)
   */
  sessionId: string | null;

  /**
   * Current session state
   */
  state: SessionState;

  /**
   * Whether session is ready for use
   */
  isReady: boolean;

  /**
   * Whether session is currently loading/initializing
   */
  isLoading: boolean;

  /**
   * Last error if any
   */
  error: Error | null;

  /**
   * Initialize or restore session
   */
  initialize: () => Promise<string | null>;

  /**
   * Create a new session (clears current one)
   */
  createNewSession: () => Promise<string | null>;

  /**
   * Clear current session
   */
  clearSession: () => void;

  /**
   * Set session ID (for external session creation)
   */
  setSession: (sessionId: string) => void;

  /**
   * Wait for session to be ready
   */
  waitForSession: () => Promise<string | null>;
}

export function useSession(options: UseSessionOptions): UseSessionReturn {
  const { source, autoInitialize = true, onSessionChange } = options;

  // State
  const [sessionId, setSessionId] = useState<string | null>(() => sessionManager.getSessionId());
  const [state, setState] = useState<SessionState>(() => sessionManager.getState());
  const [error, setError] = useState<Error | null>(() => sessionManager.getLastError());

  // Refs for cleanup
  const isMountedRef = useRef(true);
  const initializingRef = useRef(false);
  const onSessionChangeRef = useRef(onSessionChange);

  // Keep callback ref updated
  useEffect(() => {
    onSessionChangeRef.current = onSessionChange;
  }, [onSessionChange]);

  // Sync state from SessionManager
  const syncState = useCallback(() => {
    if (!isMountedRef.current) return;

    setSessionId(sessionManager.getSessionId());
    setState(sessionManager.getState());
    setError(sessionManager.getLastError());
  }, []);

  // Subscribe to session changes
  useEffect(() => {
    isMountedRef.current = true;

    const unsubscribe = sessionManager.onSessionChange((event) => {
      if (!isMountedRef.current) return;

      syncState();

      // Call user's callback if provided
      if (onSessionChangeRef.current) {
        onSessionChangeRef.current(event);
      }
    });

    // Also listen for cross-component events
    const handleWindowEvent = (e: Event) => {
      if (!isMountedRef.current) return;
      syncState();
    };

    window.addEventListener(SESSION_CHANGE_EVENT, handleWindowEvent);

    // Initial sync
    syncState();

    return () => {
      isMountedRef.current = false;
      unsubscribe();
      window.removeEventListener(SESSION_CHANGE_EVENT, handleWindowEvent);
    };
  }, [syncState]);

  // Auto-initialize on mount
  useEffect(() => {
    if (!autoInitialize) return;
    if (sessionManager.isReady()) return;
    if (initializingRef.current) return;

    initializingRef.current = true;

    sessionManager.initialize(source).finally(() => {
      initializingRef.current = false;
      if (isMountedRef.current) {
        syncState();
      }
    });
  }, [autoInitialize, source, syncState]);

  // Methods
  const initialize = useCallback(async (): Promise<string | null> => {
    if (initializingRef.current) {
      return sessionManager.waitForSession(source);
    }

    initializingRef.current = true;

    try {
      const newSessionId = await sessionManager.initialize(source);
      syncState();
      return newSessionId;
    } finally {
      initializingRef.current = false;
    }
  }, [source, syncState]);

  const createNewSession = useCallback(async (): Promise<string | null> => {
    sessionManager.clearSession();

    initializingRef.current = true;

    try {
      const newSessionId = await sessionManager.createSession(source);
      syncState();
      return newSessionId;
    } finally {
      initializingRef.current = false;
    }
  }, [source, syncState]);

  const clearSession = useCallback(() => {
    sessionManager.clearSession();
    syncState();
  }, [syncState]);

  const setSessionExternal = useCallback((newSessionId: string) => {
    sessionManager.setSession(newSessionId, source);
    syncState();
  }, [source, syncState]);

  const waitForSession = useCallback(async (): Promise<string | null> => {
    return sessionManager.waitForSession(source);
  }, [source]);

  // Derived state
  const isReady = state === 'active' && sessionId !== null;
  const isLoading = state === 'initializing' || state === 'restoring';

  return {
    sessionId,
    state,
    isReady,
    isLoading,
    error,
    initialize,
    createNewSession,
    clearSession,
    setSession: setSessionExternal,
    waitForSession
  };
}

/**
 * Simplified hook for components that only need the session ID
 * Does not auto-initialize - assumes parent component handles initialization
 */
export function useSessionId(): string | null {
  const [sessionId, setSessionId] = useState<string | null>(() => sessionManager.getSessionId());

  useEffect(() => {
    const unsubscribe = sessionManager.onSessionChange(() => {
      setSessionId(sessionManager.getSessionId());
    });

    return unsubscribe;
  }, []);

  return sessionId;
}

/**
 * Hook to check if session is ready
 * Useful for conditional rendering
 */
export function useSessionReady(): boolean {
  const [isReady, setIsReady] = useState(() => sessionManager.isReady());

  useEffect(() => {
    const unsubscribe = sessionManager.onSessionChange(() => {
      setIsReady(sessionManager.isReady());
    });

    return unsubscribe;
  }, []);

  return isReady;
}
