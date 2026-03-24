"""
Session management for Vaquill WhatsApp bot.

Sessions store client-side chat history (list of {role, content} messages)
rather than a remote session ID. The Vaquill API is stateless — history
is sent with each request.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime

import structlog
from cachetools import TTLCache

logger = structlog.get_logger()


class SessionManager:
    """Manages per-user chat sessions with Redis or in-memory fallback."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        session_timeout_minutes: int = 30,
        max_context_messages: int = 10,
    ):
        self.redis_url = redis_url
        self.redis = None
        self.session_timeout = session_timeout_minutes * 60
        self.max_context_messages = max_context_messages

        # In-memory fallback
        self.memory_sessions: TTLCache = TTLCache(
            maxsize=1000, ttl=self.session_timeout
        )

        if redis_url:
            try:
                import redis.asyncio as redis  # noqa: F811

                self.redis_available = True
            except ImportError:
                logger.warning("redis_not_available", fallback="in-memory")
                self.redis_available = False
        else:
            self.redis_available = False

    # -- lifecycle --------------------------------------------------------

    async def initialize(self):
        """Open Redis connection if configured."""
        if self.redis_available and self.redis_url:
            try:
                import redis.asyncio as redis  # noqa: F811

                self.redis = await redis.from_url(
                    self.redis_url, decode_responses=True
                )
                await self.redis.ping()
                logger.info("session_redis_connected")
            except Exception as e:
                logger.error("session_redis_failed", error=str(e))
                self.redis_available = False

    async def close(self):
        if self.redis:
            await self.redis.close()

    # -- CRUD -------------------------------------------------------------

    async def create_session(
        self, user_id: str, language: str = "en"
    ) -> Dict:
        """Create a fresh session for a user (empty chat history)."""
        session_data = {
            "user_id": user_id,
            "language": language,
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat(),
            "message_count": 0,
            "chat_history": [],
        }

        key = f"session:{user_id}"

        try:
            if self.redis_available and self.redis:
                await self.redis.setex(
                    key, self.session_timeout, json.dumps(session_data)
                )
            else:
                self.memory_sessions[key] = session_data

            logger.info("session_created", user_id=user_id)
            return session_data
        except Exception as e:
            logger.error("session_creation_error", error=str(e))
            self.memory_sessions[key] = session_data
            return session_data

    async def get_session(self, user_id: str) -> Optional[Dict]:
        """Return session data or None if expired / not found."""
        key = f"session:{user_id}"

        try:
            if self.redis_available and self.redis:
                raw = await self.redis.get(key)
                if raw:
                    session_data = json.loads(raw)
                    session_data["last_active"] = datetime.utcnow().isoformat()
                    await self.redis.expire(key, self.session_timeout)
                    return session_data
            else:
                session_data = self.memory_sessions.get(key)
                if session_data:
                    session_data["last_active"] = datetime.utcnow().isoformat()
                    return session_data

            return None
        except Exception as e:
            logger.error("session_get_error", error=str(e))
            return self.memory_sessions.get(key)

    async def update_session(self, user_id: str, updates: Dict) -> bool:
        """Merge *updates* into the existing session dict."""
        session = await self.get_session(user_id)
        if not session:
            return False

        session.update(updates)
        session["last_active"] = datetime.utcnow().isoformat()
        key = f"session:{user_id}"

        try:
            if self.redis_available and self.redis:
                await self.redis.setex(
                    key, self.session_timeout, json.dumps(session)
                )
            else:
                self.memory_sessions[key] = session
            return True
        except Exception as e:
            logger.error("session_update_error", error=str(e))
            return False

    async def clear_session(self, user_id: str) -> bool:
        """Delete the session for *user_id*."""
        key = f"session:{user_id}"
        try:
            if self.redis_available and self.redis:
                result = await self.redis.delete(key)
                success = result > 0
            else:
                success = key in self.memory_sessions
                if success:
                    del self.memory_sessions[key]

            if success:
                logger.info("session_cleared", user_id=user_id)
            return success
        except Exception as e:
            logger.error("session_clear_error", error=str(e))
            return False

    # -- chat history helpers ---------------------------------------------

    async def add_message(
        self, user_id: str, role: str, content: str
    ) -> None:
        """Append a message to the session's chat_history, trimming to max."""
        session = await self.get_session(user_id)
        if not session:
            return

        history: List[Dict[str, str]] = session.get("chat_history", [])
        history.append({"role": role, "content": content})

        # Keep only the most recent messages
        if len(history) > self.max_context_messages:
            history = history[-self.max_context_messages :]

        await self.update_session(
            user_id,
            {
                "chat_history": history,
                "message_count": session.get("message_count", 0) + 1,
            },
        )

    async def get_chat_history(self, user_id: str) -> List[Dict[str, str]]:
        """Return the chat_history list for the Vaquill API."""
        session = await self.get_session(user_id)
        if session:
            return session.get("chat_history", [])
        return []

    # -- language ---------------------------------------------------------

    async def set_language(self, user_id: str, language: str) -> bool:
        return await self.update_session(user_id, {"language": language})

    async def get_user_language(self, user_id: str) -> str:
        session = await self.get_session(user_id)
        if session:
            return session.get("language", "en")
        return "en"

    # -- mode -------------------------------------------------------------

    async def set_mode(self, user_id: str, mode: str) -> bool:
        return await self.update_session(user_id, {"mode": mode})

    async def get_user_mode(self, user_id: str) -> Optional[str]:
        session = await self.get_session(user_id)
        if session:
            return session.get("mode")
        return None

    # -- stats ------------------------------------------------------------

    async def get_active_sessions_count(self) -> int:
        try:
            if self.redis_available and self.redis:
                keys = await self.redis.keys("session:*")
                return len(keys)
            return len(self.memory_sessions)
        except Exception as e:
            logger.error("active_sessions_count_error", error=str(e))
            return 0
