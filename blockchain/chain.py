"""
chain.py — Chain class

Responsibilities:
  - Holds an ordered list of Blocks
  - Automatically creates the genesis block on initialization
  - Validates individual block legitimacy
  - Appends blocks / replaces with a longer chain
  - Thread-safe (threading.Lock)
"""

import threading
import time

from config import DIFFICULTY_BITS, GENESIS_HASH
from blockchain.block import Block
from blockchain.transaction import Transaction


def _meets_difficulty(block_hash: str, bits: int) -> bool:
    """Check whether the block hash has a sufficient number of leading zero bits."""
    prefix_zeros = bits // 4          # Each hex character = 4 bits
    return block_hash.startswith("0" * prefix_zeros)


class Chain:
    def __init__(self):
        self._lock  = threading.Lock()
        self._chain: list[Block] = []
        self._create_genesis()

    # ── Read-only properties ──────────────────────────────────────────────────

    @property
    def height(self) -> int:
        return len(self._chain)

    @property
    def last_block(self) -> Block:
        return self._chain[-1]

    def get_block(self, index: int) -> Block | None:
        if 0 <= index < len(self._chain):
            return self._chain[index]
        return None

    def get_all_blocks(self) -> list[Block]:
        with self._lock:
            return list(self._chain)

    def get_all_transactions(self) -> list[Transaction]:
        """Return a flat list of all transactions on the chain."""
        txs = []
        with self._lock:
            for blk in self._chain:
                txs.extend(blk.transactions)
        return txs

    # ── Genesis block ─────────────────────────────────────────────────────────

    def _create_genesis(self):
        genesis = Block(
            index         = 0,
            previous_hash = GENESIS_HASH,
            transactions  = [],
            timestamp     = 0.0,
            nonce         = 0,
            miner         = "genesis",
        )
        self._chain.append(genesis)

    # ── Validation ────────────────────────────────────────────────────────────

    def is_valid_new_block(self, block: Block, difficulty: int = DIFFICULTY_BITS) -> bool:
        """
        Validate a single new block:
          1. index is consecutive
          2. previous_hash matches
          3. hash is correct
          4. hash meets the difficulty target
          5. merkle_root is correct
        """
        last = self.last_block

        if block.index != last.index + 1:
            return False
        if block.previous_hash != last.hash:
            return False
        if block.hash != block.compute_hash():
            return False
        if not _meets_difficulty(block.hash, difficulty):
            return False

        from blockchain.merkle import merkle_root
        expected_mr = merkle_root([tx.tx_id for tx in block.transactions])
        if block.merkle_root != expected_mr:
            return False

        return True

    def is_valid_chain(self, chain: list[Block], difficulty: int = DIFFICULTY_BITS) -> bool:
        """Validate a complete chain (starting from the genesis block)."""
        if not chain:
            return False

        # Validate genesis block
        genesis = chain[0]
        if genesis.index != 0 or genesis.previous_hash != GENESIS_HASH:
            return False

        for i in range(1, len(chain)):
            prev, curr = chain[i - 1], chain[i]
            if curr.index != prev.index + 1:
                return False
            if curr.previous_hash != prev.hash:
                return False
            if curr.hash != curr.compute_hash():
                return False
            if not _meets_difficulty(curr.hash, difficulty):
                return False

        return True

    # ── Append / replace ──────────────────────────────────────────────────────

    def append_block(self, block: Block, difficulty: int = DIFFICULTY_BITS) -> bool:
        """Append a validated block; returns True on success."""
        with self._lock:
            if self.is_valid_new_block(block, difficulty):
                self._chain.append(block)
                return True
            return False

    def replace_chain(self, new_chain: list[Block], difficulty: int = DIFFICULTY_BITS) -> bool:
        """
        Longest-chain rule: replace with new_chain if it is longer and valid.
        Returns True on success.
        """
        with self._lock:
            if len(new_chain) > len(self._chain) and self.is_valid_chain(new_chain, difficulty):
                self._chain = list(new_chain)
                return True
            return False

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_list(self) -> list[dict]:
        with self._lock:
            return [blk.to_dict() for blk in self._chain]

    @classmethod
    def from_list(cls, data: list[dict]) -> "Chain":
        chain_obj = cls.__new__(cls)
        chain_obj._lock  = threading.Lock()
        chain_obj._chain = [Block.from_dict(d) for d in data]
        return chain_obj
