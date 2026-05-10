/**
 * useConversationSync Hook
 *
 * Monitors ChatContainer DOM and syncs conversation metadata to storage.
 * This allows chat history tracking without modifying ChatContainer internals.
 *
 * Syncs to the new storage system (IndexedDB/localStorage) used by useConversationHistory.
 *
 * Improvements:
 * - Uses unified SessionManager instead of direct localStorage access
 * - Implements completion-based detection for restore (not fixed timeout)
 * - Extended sync window with message count validation
 */

import { useEffect, useRef, useCallback } from 'react';
import { sessionManager } from '@/lib/session-manager';
import { indexedDBStorage, isIndexedDBAvailable, type ConversationRecord } from '@/lib/storage/indexeddb';
import { localStorageFallback, isLocalStorageAvailable } from '@/lib/storage/localStorage-fallback';

// Configuration for restore detection
const RESTORE_CONFIG = {
  maxWaitTime: 10000,       // Maximum wait time for restore completion (10 seconds)
  checkInterval: 500,       // How often to check if restore is complete (500ms)
  minStableTime: 1000,      // Minimum time messages must be stable before sync (1 second)
};

export function useConversationSync() {
  const lastMessageCountRef = useRef(0);
  const lastSessionIdRef = useRef<string | null>(null);
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const storageRef = useRef<any>(null);
  const autoSaveIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isRestoringRef = useRef(false); // Track if we're in restore mode
  const restoreCheckIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const restoreStartTimeRef = useRef<number>(0);
  const lastStableMessageCountRef = useRef<number>(0);
  const lastMessageChangeTimeRef = useRef<number>(0);
  const isSyncingRef = useRef(false); // Prevent concurrent sync calls

  // Initialize storage adapter
  useEffect(() => {
    if (isIndexedDBAvailable()) {
      storageRef.current = indexedDBStorage;
    } else if (isLocalStorageAvailable()) {
      storageRef.current = localStorageFallback;
    }
  }, []);

  useEffect(() => {
    // Reset mounted flag
    isMountedRef.current = true;

    // Auto-save interval (every 30 seconds)
    autoSaveIntervalRef.current = setInterval(async () => {
      if (isMountedRef.current) {
        await syncConversationState();
      }
    }, 30000);

    // Start monitoring for message changes
    const monitorMessages = () => {
      // Check if component is still mounted
      if (!isMountedRef.current) {
        return;
      }

      // Debounce to avoid excessive updates
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }

      syncTimeoutRef.current = setTimeout(async () => {
        // Check if component is still mounted before async operation
        if (!isMountedRef.current) {
          return;
        }
        await syncConversationState();
      }, 1000);
    };

    // Create MutationObserver to watch for DOM changes
    const observer = new MutationObserver(monitorMessages);

    // Find chat messages container with retry mechanism
    // ChatContainer might remount, so we need to find the element after it's rendered
    const attachObserver = (retryCount = 0) => {
      const messagesContainer = document.querySelector('.chat-messages');
      if (messagesContainer) {
        observer.observe(messagesContainer, {
          childList: true,
          subtree: true,
          characterData: true,
        });
        console.log('[ConversationSync] Observer attached to .chat-messages');

        // Initial sync
        monitorMessages();
      } else if (retryCount < 10 && isMountedRef.current) {
        // Retry after a short delay (ChatContainer might be mounting)
        console.log('[ConversationSync] .chat-messages not found, retrying...', retryCount + 1);
        setTimeout(() => attachObserver(retryCount + 1), 200);
      } else {
        console.warn('[ConversationSync] Could not find .chat-messages after retries');
      }
    };

    attachObserver();

    return () => {
      // Set mounted flag to false
      isMountedRef.current = false;

      // Disconnect observer
      observer.disconnect();

      // Clear timeouts
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
        syncTimeoutRef.current = null;
      }

      if (autoSaveIntervalRef.current) {
        clearInterval(autoSaveIntervalRef.current);
        autoSaveIntervalRef.current = null;
      }

      if (restoreCheckIntervalRef.current) {
        clearInterval(restoreCheckIntervalRef.current);
        restoreCheckIntervalRef.current = null;
      }
    };
  }, []);

  // Helper function to check if restore is complete using completion-based detection
  const checkRestoreComplete = (): boolean => {
    const now = Date.now();

    // Get current message count from DOM
    const userMessages = document.querySelectorAll('.message.user .message-content');
    const assistantMessages = document.querySelectorAll('.message.assistant .message-content');
    const currentMessageCount = Math.min(userMessages.length, assistantMessages.length);

    // Check if messages have changed
    if (currentMessageCount !== lastStableMessageCountRef.current) {
      lastStableMessageCountRef.current = currentMessageCount;
      lastMessageChangeTimeRef.current = now;
      return false; // Messages still changing
    }

    // Check if messages have been stable for the required time
    const stableTime = now - lastMessageChangeTimeRef.current;
    if (stableTime >= RESTORE_CONFIG.minStableTime && currentMessageCount > 0) {
      console.log('[ConversationSync] Restore complete - messages stable for', stableTime, 'ms');
      return true;
    }

    // Check if we've exceeded max wait time
    const elapsedTime = now - restoreStartTimeRef.current;
    if (elapsedTime >= RESTORE_CONFIG.maxWaitTime) {
      console.log('[ConversationSync] Restore timeout - proceeding after', elapsedTime, 'ms');
      return true;
    }

    return false;
  };

  // Start completion-based restore detection
  const startRestoreDetection = (expectedMessageCount: number) => {
    isRestoringRef.current = true;
    restoreStartTimeRef.current = Date.now();
    lastStableMessageCountRef.current = 0;
    lastMessageChangeTimeRef.current = Date.now();

    console.log('[ConversationSync] Starting completion-based restore detection, expecting ~', expectedMessageCount, 'messages');

    // Clear any existing interval
    if (restoreCheckIntervalRef.current) {
      clearInterval(restoreCheckIntervalRef.current);
    }

    // Set up interval to check for restore completion
    restoreCheckIntervalRef.current = setInterval(() => {
      if (!isMountedRef.current) {
        if (restoreCheckIntervalRef.current) {
          clearInterval(restoreCheckIntervalRef.current);
          restoreCheckIntervalRef.current = null;
        }
        return;
      }

      if (checkRestoreComplete()) {
        isRestoringRef.current = false;
        if (restoreCheckIntervalRef.current) {
          clearInterval(restoreCheckIntervalRef.current);
          restoreCheckIntervalRef.current = null;
        }
        console.log('[ConversationSync] Restore period ended, syncing enabled');

        // Trigger a sync now that restore is complete
        syncConversationState();
      }
    }, RESTORE_CONFIG.checkInterval);
  };

  async function syncConversationState() {
    // Check if component is still mounted
    if (!isMountedRef.current) {
      return;
    }

    // Prevent concurrent sync calls (race condition fix)
    if (isSyncingRef.current) {
      return;
    }
    isSyncingRef.current = true;

    try {
      if (!storageRef.current) {
        console.log('[ConversationSync] Storage not available');
        return;
      }

      // Use unified session manager instead of direct localStorage access
      const sessionId = sessionManager.getSessionId();
      if (!sessionId) {
        console.log('[ConversationSync] No active session');
        return;
      }

      // Check mounted state after getting session
      if (!isMountedRef.current) {
        return;
      }

      // Detect session change - reset message count tracking
      // IMPORTANT: Update lastSessionIdRef IMMEDIATELY to prevent race conditions
      const isSessionChange = lastSessionIdRef.current !== sessionId;
      if (isSessionChange) {
        // Update ref FIRST before any async operations
        const previousSession = lastSessionIdRef.current;
        lastSessionIdRef.current = sessionId;
        lastMessageCountRef.current = 0; // Reset for new session

        console.log('[ConversationSync] Session changed:', sessionId, 'previous:', previousSession);

        // Check if this is an EXISTING conversation being restored (has stored messages)
        // Only apply restore period for existing conversations, not brand new ones
        const existingRecord = await storageRef.current.get(sessionId);
        const isRestoringExisting = existingRecord && existingRecord.messageCount > 0;

        if (isRestoringExisting) {
          // Use completion-based detection instead of fixed timeout
          startRestoreDetection(existingRecord.messageCount);
          console.log('[ConversationSync] Restoring existing conversation with', existingRecord.messageCount, 'messages');
        } else {
          // New conversation - no restore period needed
          isRestoringRef.current = false;
          console.log('[ConversationSync] New conversation detected, syncing immediately');
        }
      }

      // Skip syncing during restore period (only for existing conversations being restored)
      if (isRestoringRef.current) {
        console.log('[ConversationSync] Skipping sync during restore period');
        return;
      }

      // Count messages in DOM (user + assistant pairs)
      const userMessages = document.querySelectorAll('.message.user .message-content');
      const assistantMessages = document.querySelectorAll('.message.assistant .message-content');
      const messageCount = Math.min(userMessages.length, assistantMessages.length);

      // Skip if no messages yet (but log it for debugging)
      if (messageCount === 0) {
        console.log('[ConversationSync] No complete message pairs to sync yet (user:', userMessages.length, ', assistant:', assistantMessages.length, ')');
        return;
      }

      // Skip if message count hasn't changed AND it's not a session change
      // For session changes, always sync the first message
      if (messageCount === lastMessageCountRef.current && !isSessionChange) {
        return;
      }

      lastMessageCountRef.current = messageCount;

      // Get first user message for title generation
      // Clone element and remove timestamp to get clean message text
      const firstMessageElement = userMessages[0];
      let firstMessageText = '';
      if (firstMessageElement) {
        const clone = firstMessageElement.cloneNode(true) as HTMLElement;
        const timestamp = clone.querySelector('.message-timestamp');
        if (timestamp) {
          timestamp.remove();
        }
        firstMessageText = clone.textContent?.trim() || '';
      }
      const title = firstMessageText.length > 50
        ? firstMessageText.substring(0, 50).trim() + '...'
        : firstMessageText.trim() || 'New Conversation';

      // Get last assistant message for preview
      // Clone element and remove timestamp to get clean message text
      const lastAssistantMessage = assistantMessages[assistantMessages.length - 1];
      let previewText = '';
      if (lastAssistantMessage) {
        const clone = lastAssistantMessage.cloneNode(true) as HTMLElement;
        const timestamp = clone.querySelector('.message-timestamp');
        if (timestamp) {
          timestamp.remove();
        }
        previewText = clone.textContent?.trim().substring(0, 100) || '';
      }

      // Try to get existing conversation
      const existing = await storageRef.current.get(sessionId);

      // Check mounted state after async DB operation
      if (!isMountedRef.current) {
        return;
      }

      if (existing) {
        // Update existing conversation metadata
        console.log('[ConversationSync] Updating conversation:', sessionId);

        const updatedRecord: ConversationRecord = {
          ...existing,
          messageCount,
          previewText,
          updatedAt: Date.now(),
        };

        await storageRef.current.save(updatedRecord);
      } else {
        // Create new conversation entry
        console.log('[ConversationSync] Creating new conversation:', sessionId);

        const newRecord: ConversationRecord = {
          sessionId,
          title,
          previewText,
          messageCount,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          hasCitations: false, // Will be updated when citations are detected
          messages: [], // Messages will be populated when fetched from API
        };

        await storageRef.current.save(newRecord);
      }

      // Check mounted state after all async operations
      if (!isMountedRef.current) {
        return;
      }

      console.log('[ConversationSync] Synced conversation:', { sessionId, messageCount });

      // Broadcast update to other tabs
      if (typeof window !== 'undefined' && window.BroadcastChannel) {
        try {
          const channel = new BroadcastChannel('conversation_sync');
          channel.postMessage({
            type: 'conversation_updated',
            sessionId,
            messageCount,
            timestamp: Date.now(),
          });
          channel.close();
        } catch (error) {
          console.error('[ConversationSync] Failed to broadcast update:', error);
        }
      }
    } catch (error) {
      // Only log error if component is still mounted
      if (isMountedRef.current) {
        console.error('[ConversationSync] Failed to sync conversation:', error);
      }
    } finally {
      // Release the sync lock
      isSyncingRef.current = false;
    }
  }
}
