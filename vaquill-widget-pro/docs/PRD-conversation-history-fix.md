# PRD: Conversation History Consistency Fix

## Executive Summary

The Vaquill Widget has critical issues with conversation history management causing inconsistent behavior where history is sometimes preserved and sometimes lost. This PRD outlines a comprehensive solution to unify session management across Voice and Chat modes.

---

## Problem Statement

### Current State
- **Voice Mode**: Creates sessions per utterance, never persists session_id to storage
- **Chat Mode**: Uses localStorage + Vaquill session_id, fragile restoration logic
- **Mode Switching**: No coordination between Voice and Chat session contexts
- **Error Handling**: Network errors treated same as invalid sessions, causing premature session clearing

### Impact
- Users lose conversation context when switching between Voice and Chat modes
- Network hiccups cause complete conversation history loss
- Multiple orphaned sessions created for single logical conversation
- Poor user experience with unpredictable history behavior

---

## Solution Architecture

### Design Principle: Single Source of Truth

Create a **Unified Session Manager** that:
1. Centralizes all session_id storage and retrieval
2. Coordinates between Voice and Chat modes
3. Implements robust error handling with retry logic
4. Provides event-based notifications for session changes

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      UNIFIED SESSION MANAGER                         │
│                    (src/lib/session-manager.ts)                      │
├─────────────────────────────────────────────────────────────────────┤
│  • Single localStorage key for session_id                           │
│  • Event emitter for session changes                                 │
│  • Retry logic with exponential backoff                              │
│  • Mode-agnostic session creation/restoration                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ ChatContainer│  │  VoiceMode   │  │ API Routes   │
    │              │  │              │  │              │
    │ useSession() │  │ useSession() │  │ getSession() │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Implementation Plan

### Phase 1: Create Unified Session Manager

**File**: `src/lib/session-manager.ts`

**Responsibilities**:
- Store/retrieve session_id from localStorage
- Create new sessions via Vaquill API
- Restore existing sessions with retry logic
- Emit events on session changes
- Track session state (initializing, active, error)

**Key Methods**:
```typescript
interface SessionManager {
  getSessionId(): string | null;
  createSession(): Promise<string>;
  restoreSession(sessionId: string): Promise<boolean>;
  clearSession(): void;
  onSessionChange(callback: (sessionId: string | null) => void): () => void;
}
```

### Phase 2: Create React Hook for Session Access

**File**: `src/hooks/useSession.ts`

**Responsibilities**:
- Provide React components access to SessionManager
- Handle component lifecycle (mount/unmount)
- Provide loading/error states
- Auto-initialize session on mount

### Phase 3: Update Voice Mode

**Changes to**: `src/app/api/inference-stream/route.ts`

**Before**:
```typescript
// Session created but never persisted
sessionPromise = vaquillClient.createConversation().then(conv => {
  return conv;
});
```

**After**:
```typescript
// Accept session_id from client, only create if missing
const clientSessionId = request.headers.get('x-session-id');
if (clientSessionId) {
  sessionId = clientSessionId;
} else {
  const conv = await vaquillClient.createConversation();
  sessionId = conv.session_id;
  // Return session_id to client for storage
}
```

**Changes to**: `src/components/VoiceMode.tsx`

- Use `useSession()` hook to get/set session_id
- Pass session_id to inference-stream API
- Receive and store session_id from response

### Phase 4: Update Chat Mode

**Changes to**: `src/components/ChatContainer.tsx`

- Replace manual localStorage handling with `useSession()` hook
- Remove duplicate session creation logic
- Use SessionManager's retry logic instead of immediate clear

### Phase 5: Fix Mode Transition

**Changes to**: `src/app/page.tsx`

- Remove key-based remounting that causes session loss
- Use shared session context from SessionManager
- Preserve session across mode switches

### Phase 6: Improve Error Handling

**Retry Strategy**:
```typescript
const RETRY_CONFIG = {
  maxAttempts: 3,
  baseDelay: 1000,  // 1 second
  maxDelay: 5000,   // 5 seconds
  backoffMultiplier: 2
};
```

**Error Classification**:
| Error Type | Action |
|------------|--------|
| Network timeout | Retry with backoff |
| 404 Not Found | Clear session, create new |
| 401 Unauthorized | Clear session, surface error |
| 500 Server Error | Retry with backoff |

### Phase 7: Extend Sync Window

**Changes to**: `src/hooks/useConversationSync.ts`

- Replace fixed 2-second timeout with completion-based detection
- Wait for actual message load before enabling sync
- Add maximum timeout of 10 seconds as safety

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `src/lib/session-manager.ts` | CREATE | Unified session management |
| `src/hooks/useSession.ts` | CREATE | React hook for session access |
| `src/components/VoiceMode.tsx` | MODIFY | Use useSession hook |
| `src/components/ChatContainer.tsx` | MODIFY | Use useSession hook |
| `src/app/page.tsx` | MODIFY | Remove destructive remounting |
| `src/app/api/inference-stream/route.ts` | MODIFY | Accept/return session_id |
| `src/hooks/useConversationSync.ts` | MODIFY | Completion-based sync |
| `src/lib/speech-manager.ts` | MODIFY | Use session manager |

---

## Success Metrics

1. **Session Persistence**: 100% of sessions persist across mode switches
2. **History Continuity**: Conversation history maintained across Voice ↔ Chat transitions
3. **Error Recovery**: Transient network errors don't cause history loss
4. **Session Uniqueness**: One session_id per logical conversation

---

## Testing Plan

### Unit Tests
- SessionManager creates sessions correctly
- SessionManager restores sessions with retry
- SessionManager clears sessions appropriately

### Integration Tests
- Voice → Chat preserves history
- Chat → Voice preserves history
- Network error during restore triggers retry
- Session persists across page refresh

### Manual Testing
1. Start voice conversation, switch to chat, verify history
2. Start chat conversation, switch to voice, verify context
3. Simulate network timeout during restore, verify retry
4. Refresh page, verify session restored

---

## Implementation Order

1. ✅ Create SessionManager (foundation) - `src/lib/session-manager.ts`
2. ✅ Create useSession hook (React integration) - `src/hooks/useSession.ts`
3. ✅ Update inference-stream API (accept session_id) - `src/app/api/inference-stream/route.ts`
4. ✅ Update speech-manager (use session manager) - `src/lib/speech-manager.ts`
5. ✅ Update VoiceMode (use hook, pass session_id) - `src/components/VoiceMode.tsx`
6. ✅ Update ChatContainer (use hook) - `src/components/ChatContainer.tsx`
7. ✅ Update page.tsx (remove destructive remounting) - `src/app/page.tsx`
8. ✅ Update useConversationSync (completion-based) - `src/hooks/useConversationSync.ts`

## Implementation Complete

All phases have been implemented. The conversation history issues should now be resolved:

### Key Changes Made

1. **Unified Session Manager** (`src/lib/session-manager.ts`)
   - Single source of truth for session_id storage
   - Event-based notifications for session changes
   - Retry logic with exponential backoff for network errors
   - Proper error classification (404 vs timeout vs network error)

2. **useSession React Hook** (`src/hooks/useSession.ts`)
   - Reactive session state for React components
   - Auto-initialization on mount
   - Shared session context between Voice and Chat modes

3. **Voice Mode Session Persistence** (`src/app/api/inference-stream/route.ts`, `src/lib/speech-manager.ts`)
   - API accepts `x-session-id` header from client
   - API returns `session_id` in response for client storage
   - Speech manager saves new sessions to SessionManager

4. **Chat Mode Session Integration** (`src/components/ChatContainer.tsx`)
   - Uses `useSession` hook instead of manual localStorage
   - Session changes trigger message restoration
   - Refresh button uses `createNewSession()` method

5. **Mode Transition Fix** (`src/app/page.tsx`)
   - Removed destructive key-based remounting
   - Session shared via SessionManager across modes
   - Uses `currentSessionId` from `useSessionId()` hook

6. **Completion-Based Sync** (`src/hooks/useConversationSync.ts`)
   - 10-second max wait time (was 2 seconds)
   - Checks for message stability (1 second stable period)
   - Uses SessionManager instead of direct localStorage

---

## Rollback Plan

If issues arise:
1. Revert to previous localStorage-based approach
2. Session manager can be disabled via feature flag
3. Individual components can fall back to local state

---

## Timeline

- **Phase 1-2**: Session Manager + Hook (Core foundation)
- **Phase 3-4**: Voice + Chat updates (Mode integration)
- **Phase 5-7**: Transitions + Error handling (Polish)
- **Testing**: Comprehensive validation
