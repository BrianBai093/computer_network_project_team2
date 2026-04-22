"""
block.py — Block data class

Fields:
  index          Block height
  previous_hash  Hash of the previous block
  timestamp      Block creation timestamp
  transactions   List of Transaction objects
  merkle_root    Merkle root
  nonce          PoW nonce
  hash           Current block hash (filled by compute_hash())
  miner          Miner public key (optional)
"""

import hashlib
import json
import time
from dataclasses import dataclass, field

from blockchain.transaction import Transaction
from blockchain.merkle import merkle_root


@dataclass
class Block:
    index:         int
    previous_hash: str
    transactions:  list[Transaction] = field(default_factory=list)
    timestamp:     float = field(default_factory=time.time)
    nonce:         int   = 0
    miner:         str   = ""
    merkle_root:   str   = ""
    hash:          str   = ""

    def __post_init__(self):
        self.merkle_root = merkle_root([tx.tx_id for tx in self.transactions])
        if not self.hash:
            self.hash = self.compute_hash()

    # ── Core methods ──────────────────────────────────────────────────────────

    def compute_hash(self) -> str:
        """Compute SHA-256 over the block header (excluding the hash field)."""
        header = {
            "index":         self.index,
            "previous_hash": self.previous_hash,
            "timestamp":     self.timestamp,
            "merkle_root":   self.merkle_root,
            "nonce":         self.nonce,
            "miner":         self.miner,
        }
        raw = json.dumps(header, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index":         self.index,
            "previous_hash": self.previous_hash,
            "timestamp":     self.timestamp,
            "transactions":  [tx.to_dict() for tx in self.transactions],
            "merkle_root":   self.merkle_root,
            "nonce":         self.nonce,
            "miner":         self.miner,
            "hash":          self.hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        txs = [Transaction.from_dict(t) for t in d.get("transactions", [])]
        blk = cls(
            index         = d["index"],
            previous_hash = d["previous_hash"],
            transactions  = txs,
            timestamp     = d["timestamp"],
            nonce         = d.get("nonce", 0),
            miner         = d.get("miner", ""),
        )
        blk.merkle_root = d.get("merkle_root", blk.merkle_root)
        blk.hash        = d.get("hash", blk.compute_hash())
        return blk
