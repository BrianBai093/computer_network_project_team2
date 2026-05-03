"""Device wallet and identity management.

Creates and stores ECDSA keypairs, exposes public/private key hex strings, and
derives device_id as SHA-256(public_key)[:32] for REGISTER payloads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ecdsa import NIST256p, SigningKey, VerifyingKey

from application.crypto_utils import derive_device_id, generate_keypair


@dataclass(frozen=True)
class Wallet:
    """TrueShot wallet containing one device identity.

    Args:
        private_key: Hex-encoded ECDSA private key.
        public_key: Hex-encoded ECDSA public key.
    """

    private_key: str
    public_key: str

    @property
    def device_id(self) -> str:
        """Return the derived device id for this wallet."""
        return derive_device_id(self.public_key)

    @classmethod
    def generate(cls) -> "Wallet":
        """Create a wallet with a fresh ECDSA keypair.

        Returns:
            A new ``Wallet``.
        """
        private_key, public_key = generate_keypair()
        return cls(private_key=private_key, public_key=public_key)

    @classmethod
    def from_file(cls, path: str) -> "Wallet":
        """Load a wallet from a JSON file.

        Args:
            path: Filesystem path to a wallet JSON file.

        Returns:
            The loaded ``Wallet``.

        Raises:
            ValueError: If the file does not contain a usable keypair.
        """
        wallet_path = Path(path)
        if not wallet_path.exists():
            wallet = cls.generate()
            wallet.save(path)
            return wallet

        data = json.loads(wallet_path.read_text(encoding="utf-8"))
        private_key = _required_string(data, "private_key")
        public_key = _required_string(data, "public_key")
        _validate_keypair(private_key, public_key)
        return cls(private_key=private_key, public_key=public_key)

    def save(self, path: str) -> None:
        """Save this wallet as JSON.

        Args:
            path: Destination file path.
        """
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                {
                    "private_key": self.private_key,
                    "public_key": self.public_key,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"wallet field {key!r} must be a non-empty string")
    return value


def _validate_keypair(private_key: str, public_key: str) -> None:
    try:
        signing_key = SigningKey.from_string(bytes.fromhex(private_key), curve=NIST256p)
        verifying_key = VerifyingKey.from_string(bytes.fromhex(public_key), curve=NIST256p)
    except ValueError as exc:
        raise ValueError("wallet contains invalid key material") from exc
    if signing_key.get_verifying_key().to_string() != verifying_key.to_string():
        raise ValueError("wallet private key does not match public key")
