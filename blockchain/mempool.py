"""
mempool.py — Transaction pool (memory pool)

Responsibilities:
  - Caches pending Transaction objects waiting to be packaged
  - Prevents duplicate additions (deduplicated by tx_id)
  - Returns up to N transactions in FIFO order
  - Enforces a maximum pool size (rejects new transactions when full)
  - Background daemon thread evicts expired transactions periodically
  - Thread-safe (threading.Lock)
"""

import threading
import time

from blockchain.transaction import Transaction
from config import (
    MAX_BLOCK_TXS,
    MAX_MEMPOOL_SIZE,
    MEMPOOL_TX_TTL,
    MEMPOOL_EVICT_INTERVAL,
)


class Mempool:
    def __init__(self, start_evictor: bool = True):
        """Initialize the mempool.

        Args:
            start_evictor: If True, start the background eviction thread immediately.
                Set to False in unit tests that want to control eviction manually.
        """
        self._lock: threading.Lock = threading.Lock()
        self._pool: dict[str, Transaction] = {}   # tx_id -> Transaction
        self._entered_at: dict[str, float] = {}   # tx_id -> time entered the pool

        # Background evictor
        self._stop_event: threading.Event = threading.Event()
        self._evictor_thread: threading.Thread | None = None
        if start_evictor:
            self._start_evictor()

    # ── Add ───────────────────────────────────────────────────────────────────

    def add(self, tx: Transaction) -> bool:
        """
        Add a transaction to the memory pool.

        Returns False if:
          - tx_id already exists, or
          - the pool has reached MAX_MEMPOOL_SIZE.
        Otherwise inserts and returns True.
        """
        with self._lock:
            if tx.tx_id in self._pool:
                return False
            if len(self._pool) >= MAX_MEMPOOL_SIZE:
                return False
            self._pool[tx.tx_id] = tx
            self._entered_at[tx.tx_id] = time.time()
            return True

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def get_pending(self, limit: int = MAX_BLOCK_TXS) -> list[Transaction]:
        """Return up to limit pending transactions (without removing them from the pool)."""
        with self._lock:
            return list(self._pool.values())[:limit]

    def remove(self, tx_ids: list[str]) -> None:
        """Remove transactions that have been committed to the chain."""
        with self._lock:
            for tid in tx_ids:
                self._pool.pop(tid, None)
                self._entered_at.pop(tid, None)

    # ── Status queries ────────────────────────────────────────────────────────

    def size(self) -> int:
        with self._lock:
            return len(self._pool)

    def contains(self, tx_id: str) -> bool:
        with self._lock:
            return tx_id in self._pool

    def all_transactions(self) -> list[Transaction]:
        with self._lock:
            return list(self._pool.values())

    def clear(self) -> None:
        with self._lock:
            self._pool.clear()
            self._entered_at.clear()

    # ── Background eviction ───────────────────────────────────────────────────

    def _start_evictor(self) -> None:
        """Start the background daemon thread that evicts expired transactions."""
        self._evictor_thread = threading.Thread(
            target=self._evictor_loop,
            name="MempoolEvictor",
            daemon=True,
        )
        self._evictor_thread.start()

    def _evictor_loop(self) -> None:
        """Loop until stop_event is set, evicting expired transactions periodically."""
        while not self._stop_event.is_set():
            # Wait returns True if stop_event was set during the wait,
            # which lets us exit promptly on shutdown.
            if self._stop_event.wait(MEMPOOL_EVICT_INTERVAL):
                break
            try:
                evicted = self._evict_expired()
                # Optional: log here if you have a logger
                # if evicted:
                #     logger.info(f"Mempool evicted {evicted} expired transactions")
            except Exception:
                # Never let the daemon die on a transient error;
                # swallow and continue. Log if a logger is available.
                pass

    def _evict_expired(self) -> int:
        """Remove transactions older than MEMPOOL_TX_TTL. Returns the number evicted."""
        cutoff = time.time() - MEMPOOL_TX_TTL
        with self._lock:
            expired = [tid for tid, t in self._entered_at.items() if t < cutoff]
            for tid in expired:
                self._pool.pop(tid, None)
                self._entered_at.pop(tid, None)
            return len(expired)

    def shutdown(self, timeout: float = 2.0) -> None:
        """Stop the background evictor thread. Safe to call multiple times."""
        self._stop_event.set()
        if self._evictor_thread is not None and self._evictor_thread.is_alive():
            self._evictor_thread.join(timeout=timeout)