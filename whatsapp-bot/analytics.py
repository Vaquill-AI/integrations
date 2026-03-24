"""
Analytics tracking for the Vaquill WhatsApp bot.

Records message counts, response times, success/failure rates, and
per-user activity patterns. Uses Redis when available, otherwise
falls back to in-memory storage.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

import structlog

logger = structlog.get_logger()


class Analytics:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.redis = None

        # In-memory fallback
        self.memory_stats: Dict = defaultdict(
            lambda: {
                "response_times": [],
                "responses_success": 0,
                "responses_failure": 0,
                "total_messages": 0,
            }
        )
        self.message_log: List[Dict] = []

        if redis_url:
            try:
                import redis.asyncio as redis  # noqa: F811

                self.redis_available = True
            except ImportError:
                logger.warning("redis_not_available_for_analytics")
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
                logger.info("analytics_redis_connected")
            except Exception as e:
                logger.error("analytics_redis_failed", error=str(e))
                self.redis_available = False

    async def close(self):
        if self.redis:
            await self.redis.close()

    # -- logging ----------------------------------------------------------

    async def log_message(
        self, user_id: str, message: str, message_type: str = "user"
    ):
        timestamp = datetime.utcnow()

        log_entry = {
            "user_id": user_id,
            "message": message[:100],
            "message_type": message_type,
            "timestamp": timestamp.isoformat(),
            "hour": timestamp.hour,
            "day_of_week": timestamp.weekday(),
            "word_count": len(message.split()),
        }

        try:
            if self.redis_available and self.redis:
                daily_key = f"analytics:messages:{timestamp.strftime('%Y%m%d')}"
                await self.redis.lpush(daily_key, json.dumps(log_entry))
                await self.redis.expire(daily_key, 86400 * 30)
                await self._update_redis_counters(user_id, timestamp)
            else:
                self.message_log.append(log_entry)
                if len(self.message_log) > 1000:
                    self.message_log = self.message_log[-1000:]
                self._update_memory_counters(user_id, timestamp)
        except Exception as e:
            logger.error("analytics_log_error", error=str(e))

    async def log_response(
        self, user_id: str, success: bool, response_time: Optional[float] = None
    ):
        timestamp = datetime.utcnow()

        try:
            if self.redis_available and self.redis:
                status = "success" if success else "failure"
                key = f"analytics:responses:{timestamp.strftime('%Y%m%d')}:{status}"
                await self.redis.incr(key)
                await self.redis.expire(key, 86400 * 30)

                if response_time is not None:
                    rt_key = f"analytics:response_times:{timestamp.strftime('%Y%m%d')}"
                    await self.redis.lpush(rt_key, str(response_time))
                    await self.redis.expire(rt_key, 86400 * 7)
            else:
                date_key = timestamp.strftime("%Y%m%d")
                status_key = "responses_success" if success else "responses_failure"
                self.memory_stats[date_key][status_key] += 1
                if response_time is not None:
                    self.memory_stats[date_key]["response_times"].append(response_time)
        except Exception as e:
            logger.error("analytics_response_error", error=str(e))

    async def log_error(self, user_id: str, error_message: str):
        timestamp = datetime.utcnow()
        entry = {
            "user_id": user_id,
            "error": error_message[:200],
            "timestamp": timestamp.isoformat(),
        }
        try:
            if self.redis_available and self.redis:
                key = f"analytics:errors:{timestamp.strftime('%Y%m%d')}"
                await self.redis.lpush(key, json.dumps(entry))
                await self.redis.expire(key, 86400 * 7)
            else:
                logger.error("user_error", **entry)
        except Exception as e:
            logger.error("analytics_error_log_error", error=str(e))

    # -- queries ----------------------------------------------------------

    async def get_user_stats(self, user_id: str) -> Dict:
        stats: Dict = {
            "user_id": user_id,
            "messages_today": 0,
            "messages_this_week": 0,
            "messages_this_month": 0,
            "most_active_hour": None,
            "first_seen": None,
            "last_seen": None,
        }

        try:
            now = datetime.utcnow()
            if self.redis_available and self.redis:
                for i in range(30):
                    d = now - timedelta(days=i)
                    c = await self.redis.get(
                        f"analytics:user:{user_id}:{d.strftime('%Y%m%d')}:messages"
                    )
                    if c:
                        count = int(c)
                        if i == 0:
                            stats["messages_today"] = count
                        if i < 7:
                            stats["messages_this_week"] += count
                        stats["messages_this_month"] += count

                hour_counts: Dict[int, int] = defaultdict(int)
                for i in range(7):
                    d = now - timedelta(days=i)
                    for hour in range(24):
                        hk = f"analytics:user:{user_id}:{d.strftime('%Y%m%d')}:hour:{hour}"
                        hc = await self.redis.get(hk)
                        if hc:
                            hour_counts[hour] += int(hc)
                if hour_counts:
                    stats["most_active_hour"] = max(hour_counts, key=hour_counts.get)

                stats["first_seen"] = await self.redis.get(
                    f"analytics:user:{user_id}:first_seen"
                )
                stats["last_seen"] = await self.redis.get(
                    f"analytics:user:{user_id}:last_seen"
                )
            else:
                for log in self.message_log:
                    if log["user_id"] == user_id:
                        log_date = datetime.fromisoformat(log["timestamp"])
                        days_ago = (now - log_date).days
                        if days_ago == 0:
                            stats["messages_today"] += 1
                        if days_ago < 7:
                            stats["messages_this_week"] += 1
                        if days_ago < 30:
                            stats["messages_this_month"] += 1
        except Exception as e:
            logger.error("user_stats_error", error=str(e))

        return stats

    async def get_global_stats(self) -> Dict:
        stats: Dict = {
            "total_users": 0,
            "active_users_today": 0,
            "active_users_week": 0,
            "messages_today": 0,
            "messages_week": 0,
            "success_rate_today": 0,
            "average_response_time": 0,
            "error_count_today": 0,
        }

        try:
            now = datetime.utcnow()
            if self.redis_available and self.redis:
                users_today = await self.redis.smembers(
                    f"analytics:active_users:{now.strftime('%Y%m%d')}"
                )
                stats["active_users_today"] = len(users_today)

                weekly_users: set = set()
                for i in range(7):
                    d = now - timedelta(days=i)
                    daily = await self.redis.smembers(
                        f"analytics:active_users:{d.strftime('%Y%m%d')}"
                    )
                    weekly_users.update(daily)
                stats["active_users_week"] = len(weekly_users)

                for i in range(7):
                    d = now - timedelta(days=i)
                    mk = f"analytics:messages:{d.strftime('%Y%m%d')}"
                    count = await self.redis.llen(mk)
                    if i == 0:
                        stats["messages_today"] = count
                    stats["messages_week"] += count

                sc = int(
                    await self.redis.get(
                        f"analytics:responses:{now.strftime('%Y%m%d')}:success"
                    )
                    or 0
                )
                fc = int(
                    await self.redis.get(
                        f"analytics:responses:{now.strftime('%Y%m%d')}:failure"
                    )
                    or 0
                )
                total = sc + fc
                if total > 0:
                    stats["success_rate_today"] = round(sc / total * 100, 2)

                rt_key = f"analytics:response_times:{now.strftime('%Y%m%d')}"
                rts = await self.redis.lrange(rt_key, 0, -1)
                if rts:
                    times = [float(t) for t in rts]
                    stats["average_response_time"] = round(sum(times) / len(times), 2)

                ek = f"analytics:errors:{now.strftime('%Y%m%d')}"
                stats["error_count_today"] = await self.redis.llen(ek)
            else:
                unique_users: set = set()
                for log in self.message_log:
                    unique_users.add(log["user_id"])
                    log_date = datetime.fromisoformat(log["timestamp"])
                    days_ago = (now - log_date).days
                    if days_ago == 0:
                        stats["messages_today"] += 1
                    if days_ago < 7:
                        stats["messages_week"] += 1
                stats["total_users"] = len(unique_users)
        except Exception as e:
            logger.error("global_stats_error", error=str(e))

        return stats

    # -- internal ---------------------------------------------------------

    async def _update_redis_counters(self, user_id: str, timestamp: datetime):
        ds = timestamp.strftime("%Y%m%d")
        await self.redis.sadd(f"analytics:active_users:{ds}", user_id)
        await self.redis.expire(f"analytics:active_users:{ds}", 86400 * 30)

        uck = f"analytics:user:{user_id}:{ds}:messages"
        await self.redis.incr(uck)
        await self.redis.expire(uck, 86400 * 30)

        hk = f"analytics:user:{user_id}:{ds}:hour:{timestamp.hour}"
        await self.redis.incr(hk)
        await self.redis.expire(hk, 86400 * 7)

        fk = f"analytics:user:{user_id}:first_seen"
        lk = f"analytics:user:{user_id}:last_seen"
        if not await self.redis.exists(fk):
            await self.redis.set(fk, timestamp.isoformat())
        await self.redis.set(lk, timestamp.isoformat())

    def _update_memory_counters(self, user_id: str, timestamp: datetime):
        ds = timestamp.strftime("%Y%m%d")
        self.memory_stats[ds]["total_messages"] += 1
        uk = f"user_{user_id}_messages"
        self.memory_stats[ds][uk] = self.memory_stats[ds].get(uk, 0) + 1
        hk = f"hour_{timestamp.hour}"
        self.memory_stats[ds][hk] = self.memory_stats[ds].get(hk, 0) + 1
