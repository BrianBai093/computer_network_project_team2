"""Thread-safe SSE event bus for real-time visualization."""

from __future__ import annotations

import json
import queue
import threading
import time

_lock = threading.Lock()
_subscribers: list[queue.Queue] = []


def emit(event_type: str, **data) -> None:
    payload = json.dumps({"type": event_type, "ts": time.time(), **data})
    with _lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


def subscribe() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=200)
    with _lock:
        _subscribers.append(q)
    return q


def unsubscribe(q: queue.Queue) -> None:
    with _lock:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass
