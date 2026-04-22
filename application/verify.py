"""
verify.py — Three-state image verification

Verification results (VerifyResult):
  AUTHENTIC  — An exact CAPTURE match exists on the chain; device is registered and not revoked.
  SUSPICIOUS — A perceptually similar image (pHash) exists on the chain but with a different hash
               (possibly tampered / post-processed).
  UNKNOWN    — No matching or similar record found on the chain.

Functions:
  verify_image(image_data, chain) -> VerifyDetail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from application.image_utils import sha256_bytes, phash_bytes, phash_distance, is_similar
from application.device import is_device_registered, is_device_revoked
from blockchain.chain import Chain
from config import TX_CAPTURE


class VerifyResult(str, Enum):
    AUTHENTIC  = "AUTHENTIC"
    SUSPICIOUS = "SUSPICIOUS"
    UNKNOWN    = "UNKNOWN"


@dataclass
class VerifyDetail:
    result:            VerifyResult
    image_hash:        str
    phash:             str
    matched_tx_id:     str  = ""
    matched_device:    str  = ""
    endorsement_count: int  = 0
    similar_tx_ids:    list = field(default_factory=list)
    reason:            str  = ""

    def to_dict(self) -> dict:
        return {
            "result":            self.result.value,
            "image_hash":        self.image_hash,
            "phash":             self.phash,
            "matched_tx_id":     self.matched_tx_id,
            "matched_device":    self.matched_device,
            "endorsement_count": self.endorsement_count,
            "similar_tx_ids":    self.similar_tx_ids,
            "reason":            self.reason,
        }


def verify_image(
    image_data: bytes,
    chain:      Chain,
) -> VerifyDetail:
    """
    Perform three-state verification on the given image bytes.

    Steps:
      1. Compute SHA-256 and pHash.
      2. Scan CAPTURE transactions on the chain:
         a. Exact SHA-256 match  -> AUTHENTIC (further check device status)
         b. Similar pHash but different SHA-256 -> SUSPICIOUS
      3. No match at all -> UNKNOWN
    """
    img_hash = sha256_bytes(image_data)
    p_hash   = phash_bytes(image_data)

    exact_match = None
    similar_txs: list[str] = []

    for tx in chain.get_all_transactions():
        if tx.tx_type != TX_CAPTURE:
            continue
        tx_hash  = tx.payload.get("image_hash", "")
        tx_phash = tx.payload.get("phash", "")

        if tx_hash == img_hash:
            exact_match = tx
            break

        if tx_phash and is_similar(p_hash, tx_phash):
            similar_txs.append(tx.tx_id)

    if exact_match:
        device_id  = exact_match.payload.get("device_id", "")
        registered = is_device_registered(device_id, chain)
        revoked    = is_device_revoked(device_id, chain)

        from application.endorse import get_endorsements
        endorsements = get_endorsements(exact_match.tx_id, chain)

        if not registered:
            result = VerifyResult.SUSPICIOUS
            reason = "Device is not registered on the chain."
        elif revoked:
            result = VerifyResult.SUSPICIOUS
            reason = "Device has been revoked."
        else:
            result = VerifyResult.AUTHENTIC
            reason = "Exact match found on chain; device is registered and active."

        return VerifyDetail(
            result            = result,
            image_hash        = img_hash,
            phash             = p_hash,
            matched_tx_id     = exact_match.tx_id,
            matched_device    = device_id,
            endorsement_count = len(endorsements),
            reason            = reason,
        )

    if similar_txs:
        return VerifyDetail(
            result         = VerifyResult.SUSPICIOUS,
            image_hash     = img_hash,
            phash          = p_hash,
            similar_tx_ids = similar_txs,
            reason         = "Perceptually similar image found on chain but hash differs — possible post-processing.",
        )

    return VerifyDetail(
        result     = VerifyResult.UNKNOWN,
        image_hash = img_hash,
        phash      = p_hash,
        reason     = "No matching or similar record found on the chain.",
    )
