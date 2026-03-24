"""
Analytics for Vaquill Slack Bot.

Tracks usage, performance, and user interactions.  Events are buffered
in memory and periodically flushed to an optional HTTP endpoint.
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

import aiohttp

from config import Config

logger = logging.getLogger(__name__)


class Analytics:
    """In-memory analytics with optional external sink."""

    def __init__(self) -> None:
        self.enabled = Config.ENABLE_ANALYTICS
        self.endpoint = Config.ANALYTICS_ENDPOINT
        self.buffer: List[Dict[str, Any]] = []
        self.buffer_size = 100
        self.flush_interval = 60  # seconds

        self.metrics: Dict[str, Any] = {
            "queries": defaultdict(int),
            "responses": defaultdict(int),
            "errors": defaultdict(int),
            "feedback": defaultdict(lambda: {"positive": 0, "negative": 0}),
            "response_times": defaultdict(list),
            "active_users": set(),
            "active_channels": set(),
        }

        self._flush_task_started = False

    # -- tracking methods -----------------------------------------------------

    async def track_query(
        self,
        user_id: str,
        channel_id: str,
        query: str,
        mode: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            return

        event = {
            "event": "query_submitted",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "channel_id": channel_id,
            "mode": mode or Config.VAQUILL_MODE,
            "query_length": len(query),
            "properties": {
                "has_thread": "::" in channel_id,
                "is_dm": channel_id.startswith("D"),
            },
        }

        self.metrics["queries"][mode or "default"] += 1
        self.metrics["active_users"].add(user_id)
        self.metrics["active_channels"].add(channel_id)

        await self._add_event(event)

    async def track_response(
        self,
        user_id: str,
        channel_id: str,
        success: bool,
        response_time: Optional[float] = None,
        credits_consumed: Optional[int] = None,
    ) -> None:
        if not self.enabled:
            return

        event = {
            "event": "response_generated",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "channel_id": channel_id,
            "success": success,
            "response_time": response_time,
            "credits_consumed": credits_consumed,
        }

        key = "success" if success else "error"
        self.metrics["responses" if success else "errors"][channel_id] += 1
        if response_time:
            self.metrics["response_times"][channel_id].append(response_time)

        await self._add_event(event)

    async def track_feedback(
        self, user_id: str, message_id: str, feedback_type: str
    ) -> None:
        if not self.enabled:
            return

        event = {
            "event": "feedback_received",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "message_id": message_id,
            "feedback_type": feedback_type,
        }

        self.metrics["feedback"]["total"][feedback_type] += 1
        await self._add_event(event)

    async def track_error(
        self,
        error_type: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return

        event = {
            "event": "error_occurred",
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": error_type,
            "user_id": user_id,
            "details": details or {},
        }

        self.metrics["errors"][error_type] += 1
        await self._add_event(event)

    async def track_command(
        self,
        command: str,
        user_id: str,
        channel_id: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled:
            return

        event = {
            "event": "command_executed",
            "timestamp": datetime.utcnow().isoformat(),
            "command": command,
            "user_id": user_id,
            "channel_id": channel_id,
            "parameters": parameters or {},
        }

        await self._add_event(event)

    # -- reporting ------------------------------------------------------------

    def get_metrics_summary(self) -> Dict[str, Any]:
        avg_times = {}
        for key, times in self.metrics["response_times"].items():
            if times:
                avg_times[key] = sum(times) / len(times)

        feedback_ratio = {}
        for key, fb in self.metrics["feedback"].items():
            total = fb["positive"] + fb["negative"]
            if total > 0:
                feedback_ratio[key] = fb["positive"] / total

        return {
            "period": "session",
            "total_queries": sum(self.metrics["queries"].values()),
            "total_responses": sum(self.metrics["responses"].values()),
            "total_errors": sum(self.metrics["errors"].values()),
            "unique_users": len(self.metrics["active_users"]),
            "unique_channels": len(self.metrics["active_channels"]),
            "queries_by_mode": dict(self.metrics["queries"]),
            "average_response_times": avg_times,
            "feedback_ratio": feedback_ratio,
            "errors_by_type": dict(self.metrics["errors"]),
        }

    # -- internals ------------------------------------------------------------

    async def _add_event(self, event: Dict[str, Any]) -> None:
        if not self._flush_task_started and self.enabled:
            self._flush_task_started = True
            asyncio.create_task(self._periodic_flush())

        self.buffer.append(event)
        if len(self.buffer) >= self.buffer_size:
            await self._flush_events()

    async def _flush_events(self) -> None:
        if not self.buffer or not self.endpoint:
            return

        batch = self.buffer.copy()
        self.buffer.clear()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    json={"events": batch},
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.error("Failed to flush analytics: %d", resp.status)
                        self.buffer.extend(batch)
        except Exception as exc:
            logger.error("Error flushing analytics: %s", exc)
            self.buffer.extend(batch)

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(self.flush_interval)
            if self.buffer:
                await self._flush_events()

    async def close(self) -> None:
        if self.buffer:
            await self._flush_events()
