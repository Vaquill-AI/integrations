"""
In-memory rate limiter for the Vaquill Telegram Bot.

No external dependency (Redis) required.  Each bot process keeps its own
counters, which is fine for a single-instance deployment.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple


class RateLimiter:
    """Token-bucket-style rate limiter with per-minute and per-day windows."""

    def __init__(self, daily_limit: int = 100, minute_limit: int = 5):
        self.daily_limit = daily_limit
        self.minute_limit = minute_limit
        self._lock = asyncio.Lock()

        # user_id -> {daily_count, minute_count, daily_date, minute_ts}
        self._buckets: Dict[int, Dict[str, Any]] = defaultdict(
            lambda: {
                "daily_count": 0,
                "minute_count": 0,
                "daily_date": datetime.now().date(),
                "minute_ts": datetime.now(),
            }
        )

    async def check(self, user_id: int) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Check and consume one token for *user_id*.

        Returns ``(allowed, error_message_or_none, stats_dict)``.
        """
        async with self._lock:
            now = datetime.now()
            bucket = self._buckets[user_id]

            # Reset daily counter on date change
            if bucket["daily_date"] < now.date():
                bucket["daily_count"] = 0
                bucket["daily_date"] = now.date()

            # Reset minute counter after 60 s
            if (now - bucket["minute_ts"]).total_seconds() >= 60:
                bucket["minute_count"] = 0
                bucket["minute_ts"] = now

            # --- enforce limits ---
            if bucket["minute_count"] >= self.minute_limit:
                remaining_s = 60 - int((now - bucket["minute_ts"]).total_seconds())
                return (
                    False,
                    f"Rate limit exceeded. Please wait {remaining_s} seconds.",
                    self._stats(bucket),
                )

            if bucket["daily_count"] >= self.daily_limit:
                reset_at = datetime.combine(
                    now.date() + timedelta(days=1), datetime.min.time()
                )
                hours = int((reset_at - now).total_seconds() // 3600)
                return (
                    False,
                    f"Daily limit reached. Resets in ~{hours} hours.",
                    self._stats(bucket),
                )

            # Consume
            bucket["daily_count"] += 1
            bucket["minute_count"] += 1

            return True, None, self._stats(bucket)

    async def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Return current usage stats without consuming a token."""
        async with self._lock:
            now = datetime.now()
            bucket = self._buckets[user_id]

            if bucket["daily_date"] < now.date():
                bucket["daily_count"] = 0
                bucket["daily_date"] = now.date()

            return self._stats(bucket)

    # ------------------------------------------------------------------

    def _stats(self, bucket: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "daily_used": bucket["daily_count"],
            "daily_limit": self.daily_limit,
            "daily_remaining": self.daily_limit - bucket["daily_count"],
            "minute_used": bucket["minute_count"],
            "minute_limit": self.minute_limit,
        }
