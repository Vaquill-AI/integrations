"""
Conversation Manager for Vaquill Slack Bot.

Stores chat history per thread as ``[{role, content}, ...]`` arrays
suitable for the Vaquill ``/ask`` endpoint's ``chatHistory`` parameter.
No server-side session is created -- history lives here.
"""

import time
import logging
from typing import Dict, Optional, List, Tuple, Any
from collections import defaultdict

from config import Config

logger = logging.getLogger(__name__)


class ConversationManager:
    """In-memory conversation history scoped to Slack threads."""

    def __init__(self) -> None:
        # conv_key -> conversation metadata + history
        self.conversations: Dict[str, Dict[str, Any]] = {}
        # thread_key -> thread participation info
        self.thread_participation: Dict[str, Dict[str, Any]] = {}

    # -- public API -----------------------------------------------------------

    def get_or_create_history(
        self,
        user_id: str,
        channel_id: str,
        thread_ts: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Return the chat-history array for a conversation, creating if needed."""
        key = self._key(user_id, channel_id, thread_ts)
        if key in self.conversations and self._is_valid(self.conversations[key]):
            self.conversations[key]["last_activity"] = time.time()
            return self.conversations[key]["history"]

        # New conversation
        self.conversations[key] = {
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "history": [],
            "created_at": time.time(),
            "last_activity": time.time(),
        }
        return self.conversations[key]["history"]

    def append_exchange(
        self,
        user_id: str,
        channel_id: str,
        thread_ts: Optional[str],
        question: str,
        answer: str,
    ) -> None:
        """Append a user/assistant pair and enforce the max-context window."""
        history = self.get_or_create_history(user_id, channel_id, thread_ts)
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

        # Trim to keep only the most recent N exchanges (N pairs = 2N items)
        max_items = Config.MAX_CONTEXT_MESSAGES * 2
        if len(history) > max_items:
            del history[: len(history) - max_items]

    def clear_channel_conversations(self, channel_id: str) -> None:
        to_remove = [
            k for k, v in self.conversations.items() if v["channel_id"] == channel_id
        ]
        for k in to_remove:
            del self.conversations[k]
        logger.info("Cleared %d conversations for channel %s", len(to_remove), channel_id)

    def clear_user_conversations(self, user_id: str) -> None:
        to_remove = [
            k for k, v in self.conversations.items() if v["user_id"] == user_id
        ]
        for k in to_remove:
            del self.conversations[k]
        logger.info("Cleared %d conversations for user %s", len(to_remove), user_id)

    def cleanup_expired_conversations(self) -> None:
        expired = [
            k for k, v in self.conversations.items() if not self._is_valid(v)
        ]
        for k in expired:
            del self.conversations[k]
        if expired:
            logger.info("Cleaned up %d expired conversations", len(expired))

    # -- thread participation -------------------------------------------------

    def mark_thread_participation(self, channel_id: str, thread_ts: str) -> None:
        if not Config.THREAD_FOLLOW_UP_ENABLED or not thread_ts:
            return
        key = f"{channel_id}:{thread_ts}"
        self.thread_participation[key] = {
            "first_participation": time.time(),
            "last_activity": time.time(),
            "message_count": 1,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
        }

    def update_thread_activity(self, channel_id: str, thread_ts: str) -> None:
        if not thread_ts:
            return
        key = f"{channel_id}:{thread_ts}"
        if key in self.thread_participation:
            self.thread_participation[key]["last_activity"] = time.time()
            self.thread_participation[key]["message_count"] += 1

    def should_respond_to_thread(
        self, channel_id: str, thread_ts: str
    ) -> Tuple[bool, str]:
        if not Config.THREAD_FOLLOW_UP_ENABLED:
            return False, "Thread follow-up is disabled"
        if not thread_ts:
            return False, "Not a thread message"

        key = f"{channel_id}:{thread_ts}"
        if key not in self.thread_participation:
            return False, "Bot has not participated in this thread"

        info = self.thread_participation[key]
        now = time.time()

        if now - info["last_activity"] > Config.THREAD_FOLLOW_UP_TIMEOUT:
            del self.thread_participation[key]
            return False, "Thread participation has expired"

        if info["message_count"] >= Config.THREAD_FOLLOW_UP_MAX_MESSAGES:
            return False, "Thread message limit reached"

        return True, "Bot should respond to thread follow-up"

    def cleanup_expired_thread_participation(self) -> None:
        now = time.time()
        expired = [
            k
            for k, v in self.thread_participation.items()
            if now - v["last_activity"] > Config.THREAD_FOLLOW_UP_TIMEOUT
        ]
        for k in expired:
            del self.thread_participation[k]
        if expired:
            logger.info("Cleaned up %d expired thread participations", len(expired))

    def get_active_conversation_count(self) -> Dict[str, Any]:
        by_channel: Dict[str, int] = defaultdict(int)
        by_user: Dict[str, int] = defaultdict(int)
        for v in self.conversations.values():
            by_channel[v["channel_id"]] += 1
            by_user[v["user_id"]] += 1
        return {
            "total": len(self.conversations),
            "by_channel": dict(by_channel),
            "by_user": dict(by_user),
        }

    # -- internals ------------------------------------------------------------

    def _key(
        self, user_id: str, channel_id: str, thread_ts: Optional[str]
    ) -> str:
        if Config.ENABLE_THREADING and thread_ts:
            return f"{user_id}:{channel_id}:{thread_ts}"
        return f"{user_id}:{channel_id}"

    def _is_valid(self, conv: Dict[str, Any]) -> bool:
        return (time.time() - conv.get("last_activity", 0)) < Config.CONVERSATION_TIMEOUT
