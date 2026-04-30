"""Application result models.

Defines VerifyResult and VerifyDetail, the stable verification response object
returned by verify_image() and consumed by the web layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VerifyResult(str, Enum):
    """Verification outcome for an uploaded image."""

    AUTHENTIC = "AUTHENTIC"
    SUSPICIOUS = "SUSPICIOUS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VerifyDetail:
    """Structured verification response.

    Args:
        result: High-level verification outcome.
        message: Human-readable explanation.
        image_hash: SHA-256 hash of uploaded image bytes.
        phash: Perceptual hash of uploaded image.
        matched_tx_id: Matching or nearest capture transaction id, if any.
        device_id: Device id from the matched capture, if any.
        timestamp: Transaction timestamp from the matched capture, if any.
        location: Location from the matched capture, if any.
        capture: Matched capture transaction dictionary, if any.
        endorsements: Endorsement transaction dictionaries.
        phash_distance: Hamming distance for a perceptual match, if any.
        signature_valid: Whether the matched capture signature verified.
    """

    result: VerifyResult
    message: str
    image_hash: str
    phash: str
    matched_tx_id: str | None = None
    device_id: str | None = None
    timestamp: float | None = None
    location: str | None = None
    capture: dict[str, Any] | None = None
    endorsements: list[dict[str, Any]] = field(default_factory=list)
    phash_distance: int | None = None
    signature_valid: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert this detail object into the stable web/API dictionary shape.

        Returns:
            Dictionary with all public verification fields.
        """
        return {
            "result": self.result.value,
            "message": self.message,
            "image_hash": self.image_hash,
            "phash": self.phash,
            "matched_tx_id": self.matched_tx_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "location": self.location,
            "capture": self.capture,
            "endorsements": self.endorsements,
            "phash_distance": self.phash_distance,
            "signature_valid": self.signature_valid,
        }
