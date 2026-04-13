"""
Message deduplication for Signal bot.

Signal can redeliver messages on WebSocket reconnection. This module
tracks recently seen messages to prevent duplicate API calls.
"""

from __future__ import annotations

from collections import OrderedDict


class MessageDeduplicator:
    """Bounded deduplication using message sender + timestamp as key."""

    def __init__(self, max_entries: int = 2000):
        self._seen: OrderedDict[str, bool] = OrderedDict()
        self._max = max_entries

    def is_duplicate(self, sender: str, timestamp: int) -> bool:
        """Check if this message was already processed.

        Returns True if duplicate, False if new (and marks it as seen).
        """
        key = f"{sender}:{timestamp}"
        if key in self._seen:
            return True

        self._seen[key] = True

        # Evict oldest entries
        while len(self._seen) > self._max:
            self._seen.popitem(last=False)

        return False
