"""
Conversation Manager for Vaquill Microsoft Teams Bot.

Stores chat history as a client-side array of {role, content} messages
(no server-side session IDs -- Vaquill API is stateless).
"""

import asyncio
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
import json

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Represents a conversation context with client-side chat history."""

    channel_id: str
    tenant_id: str
    user_id: str
    thread_id: Optional[str] = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_activity: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    message_count: int = 0
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "channel_id": self.channel_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "thread_id": self.thread_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": self.message_count,
            "chat_history": self.chat_history,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Create from dictionary"""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_activity"] = datetime.fromisoformat(data["last_activity"])
        return cls(**data)


class ConversationManager:
    """Manages conversation contexts and chat history (client-side)."""

    def __init__(self):
        self.local_storage: Dict[str, ConversationContext] = {}
        self.redis_client: Optional[Any] = None
        self.cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize conversation manager components"""
        if REDIS_AVAILABLE and Config.REDIS_URL:
            await self._init_redis()
        else:
            logger.info(
                "Redis not available, using local storage for conversation management"
            )

        if self.cleanup_task is None or self.cleanup_task.done():
            try:
                self.cleanup_task = asyncio.create_task(
                    self._cleanup_expired_conversations()
                )
            except RuntimeError as e:
                logger.warning(
                    f"Could not start cleanup task: {e}. Will retry on next call."
                )

    async def _init_redis(self):
        """Initialize Redis connection"""
        try:
            if Config.REDIS_SSL:
                self.redis_client = redis.from_url(
                    Config.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    ssl_cert_reqs="none",
                )
            else:
                self.redis_client = redis.from_url(
                    Config.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
            await self.redis_client.ping()
            logger.info("Redis connected for conversation management")
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis: {e}. Using local storage."
            )
            self.redis_client = None

    def _get_conversation_key(
        self,
        channel_id: str,
        user_id: str,
        thread_id: Optional[str] = None,
    ) -> str:
        """Generate a unique key for a conversation"""
        if thread_id:
            return f"conv:{channel_id}:{thread_id}:{user_id}"
        return f"conv:{channel_id}:{user_id}"

    async def get_or_create_conversation(
        self,
        channel_id: str,
        tenant_id: str,
        user_id: str,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationContext:
        """Get existing conversation or create a new one"""
        key = self._get_conversation_key(channel_id, user_id, thread_id)

        context = await self._get_conversation(key)

        if context:
            if self._is_expired(context):
                logger.info(f"Conversation {key} has expired, creating new one")
                await self._delete_conversation(key)
                context = None
            else:
                context.last_activity = datetime.now(timezone.utc)
                await self._save_conversation(key, context)
                return context

        if not context:
            context = ConversationContext(
                channel_id=channel_id,
                tenant_id=tenant_id,
                user_id=user_id,
                thread_id=thread_id,
                metadata=metadata or {},
            )
            await self._save_conversation(key, context)
            logger.info(f"Created new conversation: {key}")

        return context

    async def add_message(
        self,
        channel_id: str,
        user_id: str,
        role: str,
        content: str,
        thread_id: Optional[str] = None,
    ):
        """Add a message to the conversation's chat history."""
        key = self._get_conversation_key(channel_id, user_id, thread_id)
        context = await self._get_conversation(key)

        if context:
            context.chat_history.append({"role": role, "content": content})

            # Trim history if it exceeds max messages (keep pairs)
            max_entries = Config.MAX_CONTEXT_MESSAGES * 2
            if len(context.chat_history) > max_entries:
                context.chat_history = context.chat_history[-max_entries:]

            context.message_count += 1
            context.last_activity = datetime.now(timezone.utc)

            await self._save_conversation(key, context)

    async def get_chat_history(
        self,
        channel_id: str,
        user_id: str,
        thread_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Get the chat history array for a conversation.

        Returns a list of {role, content} dicts suitable for passing
        directly to VaquillClient.ask(chat_history=...).
        """
        key = self._get_conversation_key(channel_id, user_id, thread_id)
        context = await self._get_conversation(key)

        if not context:
            return []

        messages = context.chat_history
        if limit:
            messages = messages[-(limit * 2) :]

        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def clear_conversation(
        self,
        channel_id: str,
        user_id: str,
        thread_id: Optional[str] = None,
    ):
        """Clear a conversation"""
        key = self._get_conversation_key(channel_id, user_id, thread_id)
        await self._delete_conversation(key)
        logger.info(f"Cleared conversation: {key}")

    async def get_active_conversations_count(
        self, tenant_id: Optional[str] = None
    ) -> int:
        """Get count of active conversations"""
        count = 0

        if self.redis_client:
            try:
                cursor = b"0"
                pattern = "conv:*"
                while cursor:
                    cursor, keys = await self.redis_client.scan(
                        cursor, match=pattern, count=100
                    )
                    if tenant_id:
                        for key in keys:
                            data = await self.redis_client.get(key)
                            if data:
                                ctx = ConversationContext.from_dict(json.loads(data))
                                if ctx.tenant_id == tenant_id and not self._is_expired(
                                    ctx
                                ):
                                    count += 1
                    else:
                        count += len(keys)
                return count
            except Exception as e:
                logger.error(f"Redis error counting conversations: {e}")

        # Fallback to local storage
        if tenant_id:
            count = sum(
                1
                for ctx in self.local_storage.values()
                if ctx.tenant_id == tenant_id and not self._is_expired(ctx)
            )
        else:
            count = sum(
                1
                for ctx in self.local_storage.values()
                if not self._is_expired(ctx)
            )

        return count

    # -- internal storage helpers -----------------------------------------

    async def _get_conversation(
        self, key: str
    ) -> Optional[ConversationContext]:
        """Get conversation from storage"""
        if self.redis_client:
            try:
                data = await self.redis_client.get(key)
                if data:
                    return ConversationContext.from_dict(json.loads(data))
            except Exception as e:
                logger.error(f"Redis error getting conversation: {e}")

        return self.local_storage.get(key)

    async def _save_conversation(
        self, key: str, context: ConversationContext
    ):
        """Save conversation to storage"""
        if self.redis_client:
            try:
                data = json.dumps(context.to_dict())
                await self.redis_client.setex(
                    key, Config.CONVERSATION_TIMEOUT, data
                )
                return
            except Exception as e:
                logger.error(f"Redis error saving conversation: {e}")

        self.local_storage[key] = context

    async def _delete_conversation(self, key: str):
        """Delete conversation from storage"""
        if self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Redis error deleting conversation: {e}")

        if key in self.local_storage:
            del self.local_storage[key]

    def _is_expired(self, context: ConversationContext) -> bool:
        """Check if conversation has expired"""
        expiry_time = context.last_activity + timedelta(
            seconds=Config.CONVERSATION_TIMEOUT
        )
        return datetime.now(timezone.utc) > expiry_time

    async def _cleanup_expired_conversations(self):
        """Periodically clean up expired conversations"""
        while True:
            try:
                await asyncio.sleep(3600)

                expired_keys = [
                    key
                    for key, context in self.local_storage.items()
                    if self._is_expired(context)
                ]

                for key in expired_keys:
                    del self.local_storage[key]

                if expired_keys:
                    logger.info(
                        f"Cleaned up {len(expired_keys)} expired conversations"
                    )
            except Exception as e:
                logger.error(f"Error in conversation cleanup: {e}")

    async def close(self):
        """Cleanup resources"""
        if self.cleanup_task:
            self.cleanup_task.cancel()

        if self.redis_client:
            await self.redis_client.close()
