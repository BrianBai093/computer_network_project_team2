"""
wallet.py — Wallet (key persistence)

Saves the key pair to a local JSON file (WALLET_FILE).

Class:
  Wallet
    .private_key  -> str (hex)
    .public_key   -> str (hex)
    .device_id    -> str
    .save()
    .load()
    Wallet.generate() -> Wallet
    Wallet.from_file(path) -> Wallet
"""

import json
import os

from config import WALLET_FILE
from application.crypto_utils import generate_keypair, pubkey_to_device_id


class Wallet:
    def __init__(self, private_key: str, public_key: str):
        self.private_key = private_key
        self.public_key  = public_key
        self.device_id   = pubkey_to_device_id(public_key)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def generate(cls) -> "Wallet":
        """Generate a new key pair and return a Wallet instance."""
        priv, pub = generate_keypair()
        return cls(priv, pub)

    @classmethod
    def from_file(cls, path: str = WALLET_FILE) -> "Wallet":
        """Load wallet from file; create and save a new wallet if the file does not exist."""
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            return cls(data["private_key"], data["public_key"])
        wallet = cls.generate()
        wallet.save(path)
        return wallet

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path: str = WALLET_FILE) -> None:
        """Write the key pair to a JSON file."""
        with open(path, "w") as f:
            json.dump({
                "private_key": self.private_key,
                "public_key":  self.public_key,
                "device_id":   self.device_id,
            }, f, indent=2)

    def to_dict(self) -> dict:
        return {
            "public_key": self.public_key,
            "device_id":  self.device_id,
        }
