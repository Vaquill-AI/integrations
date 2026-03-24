"""
Rate limiting for the Vaquill WhatsApp bot.

Supports Redis-backed counters with an in-memory TTLCache fallback.
"""

import time
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

import structlog
from cachetools import TTLCache

logger = structlog.get_logger()


class RateLimiter:
    """Per-user rate limiter (minute / hour / daily windows)."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        daily_limit: int = 100,
        minute_limit: int = 5,
        hour_limit: int = 30,
    ):
        self.redis_url = redis_url
        self.redis = None
        self.daily_limit = daily_limit
        self.minute_limit = minute_limit
        self.hour_limit = hour_limit

        # In-memory fallback
        self.memory_cache: TTLCache = TTLCache(maxsize=10000, ttl=86400)

        if redis_url:
            try:
                import redis.asyncio as redis  # noqa: F811

                self.redis_available = True
            except ImportError:
                logger.warning("redis_not_available_for_rate_limiting")
                self.redis_available = False
        else:
            self.redis_available = False

    # -- lifecycle --------------------------------------------------------

    async def initialize(self):
        if self.redis_available and self.redis_url:
            try:
                import redis.asyncio as redis  # noqa: F811

                self.redis = await redis.from_url(
                    self.redis_url, decode_responses=True
                )
                await self.redis.ping()
                logger.info("rate_limiter_redis_connected")
            except Exception as e:
                logger.error("rate_limiter_redis_failed", error=str(e))
                self.redis_available = False

    async def close(self):
        if self.redis:
            await self.redis.close()

    async def check_connection(self) -> str:
        if self.redis:
            try:
                await self.redis.ping()
                return "connected"
            except Exception:
                return "disconnected"
        return "not_configured"

    # -- core -------------------------------------------------------------

    async def check_rate_limit(
        self, user_id: str
    ) -> Tuple[bool, Optional[str], Dict]:
        """
        Returns (is_allowed, error_message_or_none, stats_dict).
        """
        now = datetime.now()

        daily_key = f"rate:daily:{user_id}:{now.strftime('%Y%m%d')}"
        minute_key = f"rate:minute:{user_id}:{now.strftime('%Y%m%d%H%M')}"
        hour_key = f"rate:hour:{user_id}:{now.strftime('%Y%m%d%H')}"

        try:
            if self.redis_available and self.redis:
                return await self._check_redis(
                    user_id, daily_key, minute_key, hour_key, now
                )
            return await self._check_memory(
                user_id, daily_key, minute_key, hour_key, now
            )
        except Exception as e:
            logger.error("rate_limit_error", user_id=user_id, error=str(e))
            return True, None, {}

    # -- Redis backend ----------------------------------------------------

    async def _check_redis(
        self,
        user_id: str,
        daily_key: str,
        minute_key: str,
        hour_key: str,
        now: datetime,
    ) -> Tuple[bool, Optional[str], Dict]:
        daily_count = int(await self.redis.get(daily_key) or 0)
        minute_count = int(await self.redis.get(minute_key) or 0)
        hour_count = int(await self.redis.get(hour_key) or 0)

        if minute_count >= self.minute_limit:
            remaining = 60 - now.second
            return (
                False,
                f"Rate limit exceeded. Please wait {remaining} seconds.",
                {
                    "daily_used": daily_count,
                    "daily_limit": self.daily_limit,
                    "minute_used": minute_count,
                    "minute_limit": self.minute_limit,
                },
            )

        if hour_count >= self.hour_limit:
            remaining = 60 - now.minute
            return (
                False,
                f"Hourly limit reached. Please wait {remaining} minutes.",
                {
                    "daily_used": daily_count,
                    "daily_limit": self.daily_limit,
                    "hourly_used": hour_count,
                    "hourly_limit": self.hour_limit,
                },
            )

        if daily_count >= self.daily_limit:
            reset_time = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            )
            hours_left = (reset_time - now).seconds // 3600
            return (
                False,
                f"Daily limit reached. Resets in {hours_left} hours.",
                {
                    "daily_used": daily_count,
                    "daily_limit": self.daily_limit,
                    "reset_in_hours": hours_left,
                },
            )

        pipe = self.redis.pipeline()
        pipe.incr(daily_key)
        pipe.expire(daily_key, 86400)
        pipe.incr(minute_key)
        pipe.expire(minute_key, 60)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3600)
        await pipe.execute()

        return (
            True,
            None,
            {
                "daily_used": daily_count + 1,
                "daily_limit": self.daily_limit,
                "daily_remaining": self.daily_limit - (daily_count + 1),
                "minute_used": minute_count + 1,
                "minute_limit": self.minute_limit,
                "hourly_used": hour_count + 1,
                "hourly_limit": self.hour_limit,
            },
        )

    # -- in-memory backend ------------------------------------------------

    async def _check_memory(
        self,
        user_id: str,
        daily_key: str,
        minute_key: str,
        hour_key: str,
        now: datetime,
    ) -> Tuple[bool, Optional[str], Dict]:
        daily_count = self.memory_cache.get(daily_key, 0)
        minute_count = self.memory_cache.get(minute_key, 0)
        hour_count = self.memory_cache.get(hour_key, 0)

        if minute_count >= self.minute_limit:
            remaining = 60 - now.second
            return (
                False,
                f"Rate limit exceeded. Please wait {remaining} seconds.",
                {
                    "daily_used": daily_count,
                    "daily_limit": self.daily_limit,
                    "minute_used": minute_count,
                    "minute_limit": self.minute_limit,
                },
            )

        if hour_count >= self.hour_limit:
            remaining = 60 - now.minute
            return (
                False,
                f"Hourly limit reached. Please wait {remaining} minutes.",
                {
                    "daily_used": daily_count,
                    "daily_limit": self.daily_limit,
                    "hourly_used": hour_count,
                    "hourly_limit": self.hour_limit,
                },
            )

        if daily_count >= self.daily_limit:
            reset_time = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            )
            hours_left = (reset_time - now).seconds // 3600
            return (
                False,
                f"Daily limit reached. Resets in {hours_left} hours.",
                {
                    "daily_used": daily_count,
                    "daily_limit": self.daily_limit,
                    "reset_in_hours": hours_left,
                },
            )

        self.memory_cache[daily_key] = daily_count + 1
        self.memory_cache[minute_key] = minute_count + 1
        self.memory_cache[hour_key] = hour_count + 1

        return (
            True,
            None,
            {
                "daily_used": daily_count + 1,
                "daily_limit": self.daily_limit,
                "daily_remaining": self.daily_limit - (daily_count + 1),
                "minute_used": minute_count + 1,
                "minute_limit": self.minute_limit,
                "hourly_used": hour_count + 1,
                "hourly_limit": self.hour_limit,
            },
        )

    # -- stats ------------------------------------------------------------

    async def get_user_stats(self, user_id: str) -> Dict:
        now = datetime.now()
        stats: Dict = {
            "user_id": user_id,
            "timestamp": now.isoformat(),
            "daily": {"used": 0, "limit": self.daily_limit, "remaining": self.daily_limit},
            "hourly": {"used": 0, "limit": self.hour_limit, "remaining": self.hour_limit},
            "weekly": {},
            "monthly": {},
        }

        try:
            daily_key = f"rate:daily:{user_id}:{now.strftime('%Y%m%d')}"
            hour_key = f"rate:hour:{user_id}:{now.strftime('%Y%m%d%H')}"

            if self.redis_available and self.redis:
                dc = int(await self.redis.get(daily_key) or 0)
                hc = int(await self.redis.get(hour_key) or 0)
                stats["daily"] = {"used": dc, "limit": self.daily_limit, "remaining": self.daily_limit - dc}
                stats["hourly"] = {"used": hc, "limit": self.hour_limit, "remaining": self.hour_limit - hc}

                weekly_total = 0
                for i in range(7):
                    d = now - timedelta(days=i)
                    c = await self.redis.get(f"rate:daily:{user_id}:{d.strftime('%Y%m%d')}")
                    weekly_total += int(c) if c else 0
                stats["weekly"] = {"used": weekly_total, "average_per_day": round(weekly_total / 7, 2)}

                monthly_total = 0
                for i in range(30):
                    d = now - timedelta(days=i)
                    c = await self.redis.get(f"rate:daily:{user_id}:{d.strftime('%Y%m%d')}")
                    monthly_total += int(c) if c else 0
                stats["monthly"] = {"used": monthly_total, "average_per_day": round(monthly_total / 30, 2)}
            else:
                dc = self.memory_cache.get(daily_key, 0)
                hc = self.memory_cache.get(hour_key, 0)
                stats["daily"] = {"used": dc, "limit": self.daily_limit, "remaining": self.daily_limit - dc}
                stats["hourly"] = {"used": hc, "limit": self.hour_limit, "remaining": self.hour_limit - hc}
        except Exception as e:
            logger.error("stats_error", user_id=user_id, error=str(e))

        return stats

    async def reset_user_limits(self, user_id: str, limit_type: str = "all"):
        now = datetime.now()
        if self.redis_available and self.redis:
            if limit_type in ("daily", "all"):
                await self.redis.delete(f"rate:daily:{user_id}:{now.strftime('%Y%m%d')}")
            if limit_type in ("hour", "all"):
                await self.redis.delete(f"rate:hour:{user_id}:{now.strftime('%Y%m%d%H')}")
            if limit_type in ("minute", "all"):
                await self.redis.delete(f"rate:minute:{user_id}:{now.strftime('%Y%m%d%H%M')}")
        else:
            keys_to_remove = [
                k
                for k in self.memory_cache
                if k.startswith("rate:") and user_id in k
                and (limit_type == "all" or limit_type in k)
            ]
            for k in keys_to_remove:
                self.memory_cache.pop(k, None)

        logger.info("limits_reset", user_id=user_id, limit_type=limit_type)
