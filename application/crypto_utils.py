"""Cryptographic primitives for TrueShot application records.

Uses ECDSA NIST256p keys encoded as hex strings and exposes shared sign/verify
helpers so application workflows and chain validation use the same signature rules.
"""

from __future__ import annotations

import hashlib

from ecdsa import BadSignatureError, NIST256p, SigningKey, VerifyingKey
from ecdsa.errors import MalformedPointError


def generate_keypair() -> tuple[str, str]:
    """Generate an ECDSA private/public keypair.

    Returns:
        A tuple of ``(private_key_hex, public_key_hex)``.
    """
    private_key = SigningKey.generate(curve=NIST256p)
    public_key = private_key.get_verifying_key()
    return private_key.to_string().hex(), public_key.to_string().hex()


def derive_device_id(public_key: str) -> str:
    """Derive a stable TrueShot device id from a public key.

    Args:
        public_key: Hex-encoded ECDSA public key.

    Returns:
        The first 32 hex characters of SHA-256(public_key).
    """
    return hashlib.sha256(public_key.encode("utf-8")).hexdigest()[:32]


def sign(private_key: str, message: bytes) -> str:
    """Sign bytes with an ECDSA private key.

    Args:
        private_key: Hex-encoded ECDSA private key.
        message: Canonical bytes returned by ``Transaction.signable_bytes()``.

    Returns:
        Hex-encoded deterministic ECDSA signature.

    Raises:
        ValueError: If the private key is invalid.
    """
    try:
        signing_key = SigningKey.from_string(bytes.fromhex(private_key), curve=NIST256p)
    except ValueError as exc:
        raise ValueError("invalid private key") from exc
    return signing_key.sign_deterministic(message, hashfunc=hashlib.sha256).hex()


def verify(public_key: str, message: bytes, signature: str) -> bool:
    """Verify an ECDSA signature.

    Args:
        public_key: Hex-encoded ECDSA public key.
        message: Canonical bytes returned by ``Transaction.signable_bytes()``.
        signature: Hex-encoded ECDSA signature.

    Returns:
        ``True`` when the signature is valid; otherwise ``False``.
    """
    try:
        verifying_key = VerifyingKey.from_string(bytes.fromhex(public_key), curve=NIST256p)
        return verifying_key.verify(
            bytes.fromhex(signature),
            message,
            hashfunc=hashlib.sha256,
        )
    except (BadSignatureError, ValueError, MalformedPointError):
        return False
