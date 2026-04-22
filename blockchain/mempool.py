"""
mempool.py — Transaction pool (memory pool)

Responsibilities:
  - Caches pending Transaction objects waiting to be packaged
  - Prevents duplicate additions (deduplicated by tx_id)
  - Returns up to N transactions in FIFO order
  - Thread-safe (threading.Lock)
"""

import threading

from blockchain.transaction import Transaction
from config import MAX_BLOCK_TXS


class Mempool:
    def __init__(self):
        self._lock: threading.Lock = threading.Lock()
        self._pool: dict[str, Transaction] = {}   # tx_id -> Transaction

    # ── Add ───────────────────────────────────────────────────────────────────

    def add(self, tx: Transaction) -> bool:
        """
        Add a transaction to the memory pool.
        If tx_id already exists, ignore and return False; otherwise return True.
        """
        with self._lock:
            if tx.tx_id in self._pool:
                return False
            self._pool[tx.tx_id] = tx
            return True

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def get_pending(self, limit: int = MAX_BLOCK_TXS) -> list[Transaction]:
        """Return up to limit pending transactions (without removing them from the pool)."""
        with self._lock:
            return list(self._pool.values())[:limit]

    def remove(self, tx_ids: list[str]):
        """Remove transactions that have been committed to the chain."""
        with self._lock:
            for tid in tx_ids:
                self._pool.pop(tid, None)

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

    def clear(self):
        with self._lock:
            self._pool.clear()
