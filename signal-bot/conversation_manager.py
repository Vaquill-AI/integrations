"""
Conversation history manager with LRU eviction and TTL cleanup.

Prevents unbounded memory growth by capping the number of tracked users
and automatically evicting stale entries.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Dict, List


class ConversationManager:
    """LRU-evicting, TTL-aware conversation history store."""

    def __init__(
        self,
        max_history_pairs: int = 10,
        max_users: int = 5000,
        ttl_seconds: int = 3600,
    ):
        self._max_messages = max_history_pairs * 2
        self._max_users = max_users
        self._ttl = ttl_seconds
        # user_id -> {"messages": [...], "last_access": float}
        self._data: OrderedDict[str, Dict] = OrderedDict()

    def append(self, user_id: str, role: str, content: str) -> None:
        """Append a message and trim to max history."""
        if user_id not in self._data:
            self._data[user_id] = {"messages": [], "last_access": time.time()}

        entry = self._data[user_id]
        entry["messages"].append({"role": role, "content": content})
        entry["last_access"] = time.time()

        # Trim per-user history
        if len(entry["messages"]) > self._max_messages:
            entry["messages"] = entry["messages"][-self._max_messages:]

        # Move to end (most recently used)
        self._data.move_to_end(user_id)

        # Evict oldest users if over capacity
        while len(self._data) > self._max_users:
            self._data.popitem(last=False)

    def get(self, user_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a user."""
        if user_id not in self._data:
            return []

        entry = self._data[user_id]

        # Check TTL
        if time.time() - entry["last_access"] > self._ttl:
            self._data.pop(user_id, None)
            return []

        entry["last_access"] = time.time()
        self._data.move_to_end(user_id)
        return list(entry["messages"])

    def clear(self, user_id: str) -> None:
        """Clear conversation history for a user."""
        self._data.pop(user_id, None)

    def cleanup_stale(self) -> int:
        """Remove entries older than TTL. Returns count of evicted entries."""
        now = time.time()
        stale_keys = [
            k for k, v in self._data.items()
            if now - v["last_access"] > self._ttl
        ]
        for k in stale_keys:
            del self._data[k]
        return len(stale_keys)

    @property
    def active_users(self) -> int:
        """Number of users with active conversation history."""
        return len(self._data)
