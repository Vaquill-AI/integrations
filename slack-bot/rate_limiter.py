"""
Rate Limiter for Vaquill Slack Bot.

Supports an optional Redis backend for distributed deployments;
falls back to in-memory sliding-window counters.
"""

import time
import logging
from typing import Dict, Optional
from collections import defaultdict

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from config import Config

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter with optional Redis backend."""

    def __init__(self) -> None:
        self.local_storage: Dict[str, list] = defaultdict(list)
        self.redis_client: Optional["redis.Redis"] = None
        self._redis_initialized = False

    # -- public API -----------------------------------------------------------

    async def check_rate_limit(self, user_id: str, channel_id: str) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        await self._ensure_redis()
        now = time.time()

        if not await self._check(
            f"user:{user_id}",
            now,
            Config.RATE_LIMIT_PER_USER,
            Config.RATE_LIMIT_WINDOW_USER,
        ):
            logger.warning("User %s exceeded rate limit", user_id)
            return False

        if not await self._check(
            f"channel:{channel_id}",
            now,
            Config.RATE_LIMIT_PER_CHANNEL,
            Config.RATE_LIMIT_WINDOW_CHANNEL,
        ):
            logger.warning("Channel %s exceeded rate limit", channel_id)
            return False

        return True

    async def get_remaining_quota(self, user_id: str) -> Dict[str, int]:
        now = time.time()
        key = f"user:{user_id}"

        if self.redis_client:
            try:
                count = await self.redis_client.zcount(
                    key, now - Config.RATE_LIMIT_WINDOW_USER, now
                )
                remaining = max(0, Config.RATE_LIMIT_PER_USER - count)
            except Exception:
                remaining = self._remaining_local(
                    key, now, Config.RATE_LIMIT_PER_USER, Config.RATE_LIMIT_WINDOW_USER
                )
        else:
            remaining = self._remaining_local(
                key, now, Config.RATE_LIMIT_PER_USER, Config.RATE_LIMIT_WINDOW_USER
            )

        return {
            "remaining": remaining,
            "limit": Config.RATE_LIMIT_PER_USER,
            "window": Config.RATE_LIMIT_WINDOW_USER,
        }

    async def reset_limits(
        self,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> None:
        if user_id:
            await self._reset_key(f"user:{user_id}")
        if channel_id:
            await self._reset_key(f"channel:{channel_id}")

    async def close(self) -> None:
        if self.redis_client:
            await self.redis_client.close()

    # -- internals ------------------------------------------------------------

    async def _ensure_redis(self) -> None:
        if not self._redis_initialized and REDIS_AVAILABLE and Config.REDIS_URL:
            try:
                self.redis_client = redis.from_url(
                    Config.REDIS_URL, encoding="utf-8", decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("Redis connected for rate limiting")
            except Exception as exc:
                logger.warning("Redis unavailable (%s), using local storage", exc)
                self.redis_client = None
            self._redis_initialized = True

    async def _check(
        self, key: str, now: float, limit: int, window: int
    ) -> bool:
        if self.redis_client:
            return await self._check_redis(key, now, limit, window)
        return self._check_local(key, now, limit, window)

    async def _check_redis(
        self, key: str, now: float, limit: int, window: int
    ) -> bool:
        try:
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window)
            results = await pipe.execute()
            return results[1] < limit
        except Exception as exc:
            logger.error("Redis rate-limit error: %s", exc)
            return self._check_local(key, now, limit, window)

    def _check_local(
        self, key: str, now: float, limit: int, window: int
    ) -> bool:
        cutoff = now - window
        self.local_storage[key] = [t for t in self.local_storage[key] if t > cutoff]
        if len(self.local_storage[key]) >= limit:
            return False
        self.local_storage[key].append(now)
        return True

    def _remaining_local(
        self, key: str, now: float, limit: int, window: int
    ) -> int:
        cutoff = now - window
        valid = [t for t in self.local_storage[key] if t > cutoff]
        return max(0, limit - len(valid))

    async def _reset_key(self, key: str) -> None:
        if self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception as exc:
                logger.error("Failed to reset Redis key %s: %s", key, exc)
        self.local_storage.pop(key, None)
