"""
transaction.py — Transaction data class + 4 transaction types

Transaction types (see config.TX_*):
  REGISTER  Device registration  payload: {device_id, public_key, metadata}
  CAPTURE   Photo capture record payload: {device_id, image_hash, phash, location}
  ENDORSE   Endorsement          payload: {target_tx_id, endorser_device_id}
  REVOKE    Revocation           payload: {target_device_id, reason}
"""

import hashlib
import json
import time
from dataclasses import dataclass, field

from config import TX_REGISTER, TX_CAPTURE, TX_ENDORSE, TX_REVOKE, TX_COINBASE


@dataclass
class Transaction:
    tx_type:   str          # TX_REGISTER / TX_CAPTURE / TX_ENDORSE / TX_REVOKE
    sender:    str          # Sender public key (hex)
    payload:   dict         # Business data
    timestamp: float = field(default_factory=time.time)
    signature: str   = ""   # ECDSA signature (hex), filled by application.crypto_utils
    tx_id:     str   = ""   # Filled after hash computation

    def __post_init__(self):
        if not self.tx_id:
            self.tx_id = self.compute_id()

    # ── Core methods ──────────────────────────────────────────────────────────

    def compute_id(self) -> str:
        """Compute SHA-256 over (tx_type, sender, payload, timestamp), return hex string."""
        data = {
            "tx_type":   self.tx_type,
            "sender":    self.sender,
            "payload":   self.payload,
            "timestamp": self.timestamp,
        }
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "tx_id":     self.tx_id,
            "tx_type":   self.tx_type,
            "sender":    self.sender,
            "payload":   self.payload,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        """Deserialize from a dictionary."""
        tx = cls(
            tx_type   = d["tx_type"],
            sender    = d["sender"],
            payload   = d["payload"],
            timestamp = d["timestamp"],
            signature = d.get("signature", ""),
        )
        tx.tx_id = d.get("tx_id", tx.compute_id())
        return tx

    def signable_bytes(self) -> bytes:
        """Return the canonical byte string used for signing/verifying (excludes the signature field)."""
        data = {
            "tx_type":   self.tx_type,
            "sender":    self.sender,
            "payload":   self.payload,
            "timestamp": self.timestamp,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    # ── Factory methods ───────────────────────────────────────────────────────

    @staticmethod
    def make_register(sender_pubkey: str, device_id: str,
                      metadata: dict | None = None) -> "Transaction":
        """Create a REGISTER transaction (unsigned)."""
        return Transaction(
            tx_type = TX_REGISTER,
            sender  = sender_pubkey,
            payload = {
                "device_id":  device_id,
                "public_key": sender_pubkey,
                "metadata":   metadata or {},
            },
        )

    @staticmethod
    def make_capture(sender_pubkey: str, device_id: str,
                     image_hash: str, phash: str,
                     location: str = "") -> "Transaction":
        """Create a CAPTURE transaction (unsigned)."""
        return Transaction(
            tx_type = TX_CAPTURE,
            sender  = sender_pubkey,
            payload = {
                "device_id":  device_id,
                "image_hash": image_hash,
                "phash":      phash,
                "location":   location,
            },
        )

    @staticmethod
    def make_endorse(sender_pubkey: str, target_tx_id: str,
                     endorser_device_id: str) -> "Transaction":
        """Create an ENDORSE transaction (unsigned)."""
        return Transaction(
            tx_type = TX_ENDORSE,
            sender  = sender_pubkey,
            payload = {
                "target_tx_id":       target_tx_id,
                "endorser_device_id": endorser_device_id,
            },
        )

    @staticmethod
    def make_revoke(sender_pubkey: str, target_device_id: str,
                    reason: str = "") -> "Transaction":
        """Create a REVOKE transaction (unsigned)."""
        return Transaction(
            tx_type = TX_REVOKE,
            sender  = sender_pubkey,
            payload = {
                "target_device_id": target_device_id,
                "reason":           reason,
            },
        )

    @staticmethod
    def make_coinbase(miner_pubkey: str, reward: int | float = 1) -> "Transaction":
        """Create a COINBASE (mining reward) transaction.

        Args:
            miner_pubkey: The public key of the miner receiving the reward.
            reward: The mining reward amount.

        Returns:
            An unsigned COINBASE Transaction.
        """
        return Transaction(
            tx_type=TX_COINBASE,
            sender=miner_pubkey,
            payload={"miner": miner_pubkey, "reward": reward},
        )
