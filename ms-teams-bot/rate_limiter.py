"""
Rate Limiter for Vaquill Microsoft Teams Bot
"""

import time
import asyncio
import logging
from typing import Dict, Optional, Tuple, Any
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from config import Config

logger = logging.getLogger(__name__)


class RateLimitScope(Enum):
    """Rate limit scopes"""

    USER = "user"
    CHANNEL = "channel"
    TENANT = "tenant"


class RateLimiter:
    """Rate limiting implementation with Redis support"""

    def __init__(self):
        self.local_storage: Dict[str, list] = defaultdict(list)
        self._local_lock: Optional[asyncio.Lock] = None
        self.redis_client: Optional[Any] = None

    def _get_or_create_lock(self) -> asyncio.Lock:
        """Get or create lock for current event loop"""
        try:
            if self._local_lock is not None:
                return self._local_lock
        except RuntimeError:
            pass
        self._local_lock = asyncio.Lock()
        return self._local_lock

    async def initialize(self):
        """Initialize rate limiter components"""
        if REDIS_AVAILABLE and Config.REDIS_URL:
            await self._init_redis()
        else:
            logger.info(
                "Redis not available, using local storage for rate limiting"
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
            logger.info("Redis connected for rate limiting")
        except Exception as e:
            logger.warning(
                f"Failed to connect to Redis: {e}. Using local storage."
            )
            self.redis_client = None

    async def check_rate_limit(
        self,
        user_id: str,
        channel_id: str,
        tenant_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a request has exceeded rate limits.

        Returns:
            Tuple of (is_allowed, error_message).
        """
        current_time = time.time()

        # Check user rate limit
        user_key = f"{RateLimitScope.USER.value}:{tenant_id}:{user_id}"
        if not await self._check_limit(
            user_key,
            current_time,
            Config.RATE_LIMIT_PER_USER,
            Config.RATE_LIMIT_WINDOW_USER,
        ):
            remaining = await self._get_reset_time(
                user_key, Config.RATE_LIMIT_WINDOW_USER
            )
            logger.warning(f"User {user_id} exceeded rate limit")
            return (
                False,
                f"You've exceeded the rate limit. Please try again in {remaining} seconds.",
            )

        # Check channel rate limit
        channel_key = f"{RateLimitScope.CHANNEL.value}:{tenant_id}:{channel_id}"
        if not await self._check_limit(
            channel_key,
            current_time,
            Config.RATE_LIMIT_PER_CHANNEL,
            Config.RATE_LIMIT_WINDOW_CHANNEL,
        ):
            remaining = await self._get_reset_time(
                channel_key, Config.RATE_LIMIT_WINDOW_CHANNEL
            )
            logger.warning(f"Channel {channel_id} exceeded rate limit")
            return (
                False,
                f"This channel has exceeded the rate limit. Please try again in {remaining} seconds.",
            )

        # Check tenant rate limit
        tenant_key = f"{RateLimitScope.TENANT.value}:{tenant_id}"
        if not await self._check_limit(
            tenant_key,
            current_time,
            Config.RATE_LIMIT_PER_TENANT,
            Config.RATE_LIMIT_WINDOW_TENANT,
        ):
            remaining = await self._get_reset_time(
                tenant_key, Config.RATE_LIMIT_WINDOW_TENANT
            )
            logger.warning(f"Tenant {tenant_id} exceeded rate limit")
            return (
                False,
                f"Your organization has exceeded the rate limit. Please try again in {remaining} seconds.",
            )

        return True, None

    async def _check_limit(
        self, key: str, current_time: float, limit: int, window: int
    ) -> bool:
        """Check and update rate limit for a specific key"""
        if self.redis_client:
            return await self._check_limit_redis(key, current_time, limit, window)
        return await self._check_limit_local(key, current_time, limit, window)

    async def _check_limit_redis(
        self, key: str, current_time: float, limit: int, window: int
    ) -> bool:
        """Check rate limit using Redis with sliding window"""
        try:
            pipeline = self.redis_client.pipeline()
            min_time = current_time - window
            pipeline.zremrangebyscore(key, 0, min_time)
            pipeline.zcard(key)
            pipeline.zadd(key, {str(current_time): current_time})
            pipeline.expire(key, window + 60)
            results = await pipeline.execute()
            count = results[1]
            return count < limit
        except Exception as e:
            logger.error(f"Redis error in rate limiting: {e}")
            return await self._check_limit_local(key, current_time, limit, window)

    async def _check_limit_local(
        self, key: str, current_time: float, limit: int, window: int
    ) -> bool:
        """Check rate limit using local storage (thread-safe)"""
        lock = self._get_or_create_lock()
        async with lock:
            min_time = current_time - window
            self.local_storage[key] = [
                timestamp
                for timestamp in self.local_storage[key]
                if timestamp > min_time
            ]

            if len(self.local_storage[key]) >= limit:
                return False

            self.local_storage[key].append(current_time)
            return True

    async def _get_reset_time(self, key: str, window: int) -> int:
        """Get seconds until rate limit resets"""
        current_time = time.time()

        if self.redis_client:
            try:
                oldest = await self.redis_client.zrange(
                    key, 0, 0, withscores=True
                )
                if oldest:
                    oldest_time = oldest[0][1]
                    reset_time = oldest_time + window
                    return max(1, int(reset_time - current_time))
            except Exception:
                pass

        if key in self.local_storage and self.local_storage[key]:
            oldest_time = min(self.local_storage[key])
            reset_time = oldest_time + window
            return max(1, int(reset_time - current_time))

        return 60

    async def get_remaining_quota(
        self,
        user_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        """Get remaining quota for a user"""
        current_time = time.time()
        user_key = f"{RateLimitScope.USER.value}:{tenant_id}:{user_id}"

        if self.redis_client:
            try:
                min_time = current_time - Config.RATE_LIMIT_WINDOW_USER
                count = await self.redis_client.zcount(
                    user_key, min_time, current_time
                )
                remaining = max(0, Config.RATE_LIMIT_PER_USER - count)
            except Exception:
                remaining = self._get_remaining_local(
                    user_key,
                    current_time,
                    Config.RATE_LIMIT_PER_USER,
                    Config.RATE_LIMIT_WINDOW_USER,
                )
        else:
            remaining = self._get_remaining_local(
                user_key,
                current_time,
                Config.RATE_LIMIT_PER_USER,
                Config.RATE_LIMIT_WINDOW_USER,
            )

        return {
            "user_remaining": remaining,
            "user_limit": Config.RATE_LIMIT_PER_USER,
            "user_window": Config.RATE_LIMIT_WINDOW_USER,
        }

    def _get_remaining_local(
        self, key: str, current_time: float, limit: int, window: int
    ) -> int:
        """Get remaining quota from local storage"""
        min_time = current_time - window
        valid_requests = [t for t in self.local_storage[key] if t > min_time]
        return max(0, limit - len(valid_requests))

    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
