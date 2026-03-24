"""
Rate limiter for Vaquill Discord Bot.

Supports Redis-backed distributed limiting with a local-cache fallback
when Redis is unavailable.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, Tuple, Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter backed by Redis sorted sets."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url
        self.redis: redis.Redis | None = None
        self.local_cache: Dict[str, list[float]] = defaultdict(list)

    async def connect(self):
        """Connect to Redis if URL is provided."""
        if self.redis_url:
            try:
                self.redis = await redis.from_url(self.redis_url)
                await self.redis.ping()
                logger.info("Connected to Redis for rate limiting")
            except Exception as e:
                logger.warning("Failed to connect to Redis: %s. Using local cache.", e)
                self.redis = None

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def check_rate_limit(
        self, key: str, limit: int, window: int
    ) -> Tuple[bool, int]:
        """
        Check if the rate limit has been exceeded.

        Returns (is_allowed, remaining_queries).
        """
        current_time = time.time()

        if self.redis:
            return await self._check_redis_rate_limit(key, limit, window, current_time)
        return self._check_local_rate_limit(key, limit, window, current_time)

    async def _check_redis_rate_limit(
        self, key: str, limit: int, window: int, current_time: float
    ) -> Tuple[bool, int]:
        """Check rate limit using Redis sorted sets."""
        try:
            redis_key = f"vaquill:rate_limit:{key}"

            await self.redis.zremrangebyscore(redis_key, 0, current_time - window)
            current_count = await self.redis.zcard(redis_key)

            if current_count < limit:
                await self.redis.zadd(redis_key, {str(current_time): current_time})
                await self.redis.expire(redis_key, window)
                return True, limit - current_count - 1
            return False, 0
        except Exception as e:
            logger.error("Redis rate limit error: %s", e)
            return self._check_local_rate_limit(key, limit, window, current_time)

    def _check_local_rate_limit(
        self, key: str, limit: int, window: int, current_time: float
    ) -> Tuple[bool, int]:
        """Check rate limit using in-memory fallback."""
        self.local_cache[key] = [
            ts for ts in self.local_cache[key] if current_time - ts < window
        ]

        if len(self.local_cache[key]) < limit:
            self.local_cache[key].append(current_time)
            return True, limit - len(self.local_cache[key])
        return False, 0

    async def get_reset_time(self, key: str, window: int) -> int:
        """Get seconds until the rate limit window resets."""
        current_time = time.time()

        if self.redis:
            try:
                redis_key = f"vaquill:rate_limit:{key}"
                oldest_entry = await self.redis.zrange(
                    redis_key, 0, 0, withscores=True
                )
                if oldest_entry:
                    oldest_time = oldest_entry[0][1]
                    return max(0, int(oldest_time + window - current_time))
                return 0
            except Exception:
                pass

        if key in self.local_cache and self.local_cache[key]:
            oldest_time = min(self.local_cache[key])
            return max(0, int(oldest_time + window - current_time))

        return 0


class DiscordRateLimiter:
    """Discord-specific rate limiter wrapping user and channel keys."""

    def __init__(self, rate_limiter: RateLimiter, config: Dict[str, Any]):
        self.rate_limiter = rate_limiter
        self.config = config

    async def check_user_limit(self, user_id: str) -> Tuple[bool, int, int]:
        """Check rate limit for a user. Returns (allowed, remaining, reset_seconds)."""
        key = f"user:{user_id}"
        is_allowed, remaining = await self.rate_limiter.check_rate_limit(
            key,
            self.config["RATE_LIMIT_PER_USER"],
            self.config["RATE_LIMIT_WINDOW"],
        )
        reset_time = await self.rate_limiter.get_reset_time(
            key, self.config["RATE_LIMIT_WINDOW"]
        )
        return is_allowed, remaining, reset_time

    async def check_channel_limit(self, channel_id: str) -> Tuple[bool, int, int]:
        """Check rate limit for a channel. Returns (allowed, remaining, reset_seconds)."""
        key = f"channel:{channel_id}"
        is_allowed, remaining = await self.rate_limiter.check_rate_limit(
            key,
            self.config["RATE_LIMIT_PER_CHANNEL"],
            self.config["RATE_LIMIT_WINDOW"],
        )
        reset_time = await self.rate_limiter.get_reset_time(
            key, self.config["RATE_LIMIT_WINDOW"]
        )
        return is_allowed, remaining, reset_time
