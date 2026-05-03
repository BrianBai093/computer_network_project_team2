"""Backward-compatible image utility names used by older tests."""

from __future__ import annotations

from application.image_hash import compute_image_hash, phash_distance


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest for raw image bytes."""
    return compute_image_hash(data)
