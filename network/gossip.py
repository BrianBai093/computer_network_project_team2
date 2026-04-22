"""
gossip.py — Seen-message cache (prevents duplicate forwarding of Gossip messages)

Uses a bounded LRU cache to store IDs of already-processed messages.
"""

import threading
from collections import OrderedDict

from config import SEEN_MSG_CACHE_SIZE


class SeenMessages:
    """Thread-safe seen-message ID cache (LRU, bounded)."""

    def __init__(self, maxsize: int = SEEN_MSG_CACHE_SIZE):
        self._maxsize = maxsize
        self._cache: OrderedDict[str, bool] = OrderedDict()
        self._lock   = threading.Lock()

    def seen(self, msg_id: str) -> bool:
        """Return True if msg_id has been seen before; otherwise record it and return False."""
        with self._lock:
            if msg_id in self._cache:
                self._cache.move_to_end(msg_id)
                return True
            self._cache[msg_id] = True
            self._cache.move_to_end(msg_id)
            if len(self._cache) > self._maxsize:
                self._cache.popitem(last=False)   # Evict the oldest entry
            return False

    def size(self) -> int:
        with self._lock:
            return len(self._cache)
