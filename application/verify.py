"""Photo verification workflow.

Compares uploaded image hashes against chain CAPTURE records, verifies signatures,
classifies results as AUTHENTIC, SUSPICIOUS, or UNKNOWN, and attaches provenance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from application.crypto_utils import verify
from application.endorse import get_endorsements
from application.image_hash import (
    PHASH_DISTANCE_THRESHOLD,
    compute_image_hash,
    compute_phash,
    phash_distance,
)
from application.models import VerifyDetail, VerifyResult

if TYPE_CHECKING:
    from blockchain.chain import Chain
    from blockchain.transaction import Transaction

REGISTER_TYPES = {"REGISTER", "REGISTER_DEVICE"}


def verify_image(image_data: bytes, chain: "Chain") -> VerifyDetail:
    """Verify an uploaded image against on-chain capture records.

    Args:
        image_data: Uploaded image bytes.
        chain: Layer 1 chain to query.

    Returns:
        Detailed verification result.

    Raises:
        ValueError: If the uploaded image cannot be decoded for pHash.
    """
    image_hash = compute_image_hash(image_data)
    uploaded_phash = compute_phash(image_data)
    captures = [_tx for _tx in chain.get_all_transactions() if _tx_type(_tx) == "CAPTURE"]

    suspicious_exact: VerifyDetail | None = None
    for tx in captures:
        payload = _payload(tx)
        if payload.get("image_hash") != image_hash:
            continue

        signature_valid = _signature_valid(tx)
        registered = _has_valid_registration(payload.get("device_id"), _sender(tx), chain)
        detail = _detail_for_capture(
            tx=tx,
            chain=chain,
            result=VerifyResult.AUTHENTIC if signature_valid and registered else VerifyResult.SUSPICIOUS,
            message=(
                "Exact image hash matched a valid registered capture."
                if signature_valid and registered
                else "Exact image hash matched, but the capture signature or registration is invalid."
            ),
            image_hash=image_hash,
            uploaded_phash=uploaded_phash,
            phash_distance_value=None,
            signature_valid=signature_valid,
        )
        if detail.result == VerifyResult.AUTHENTIC:
            return detail
        suspicious_exact = suspicious_exact or detail

    if suspicious_exact is not None:
        return suspicious_exact

    perceptual_match = _nearest_phash_match(uploaded_phash, captures)
    if perceptual_match is not None:
        tx, distance = perceptual_match
        return _detail_for_capture(
            tx=tx,
            chain=chain,
            result=VerifyResult.SUSPICIOUS,
            message="Image visually matches a registered capture, but the bytes differ.",
            image_hash=image_hash,
            uploaded_phash=uploaded_phash,
            phash_distance_value=distance,
            signature_valid=_signature_valid(tx),
        )

    return VerifyDetail(
        result=VerifyResult.UNKNOWN,
        message="No matching capture was found on chain.",
        image_hash=image_hash,
        phash=uploaded_phash,
        endorsements=[],
    )


def _nearest_phash_match(
    uploaded_phash: str,
    captures: list["Transaction"],
) -> tuple["Transaction", int] | None:
    nearest: tuple["Transaction", int] | None = None
    for tx in captures:
        stored_phash = _payload(tx).get("phash")
        if not isinstance(stored_phash, str):
            continue
        try:
            distance = phash_distance(uploaded_phash, stored_phash)
        except ValueError:
            continue
        if distance <= PHASH_DISTANCE_THRESHOLD and (
            nearest is None or distance < nearest[1]
        ):
            nearest = (tx, distance)
    return nearest


def _detail_for_capture(
    tx: "Transaction",
    chain: "Chain",
    result: VerifyResult,
    message: str,
    image_hash: str,
    uploaded_phash: str,
    phash_distance_value: int | None,
    signature_valid: bool,
) -> VerifyDetail:
    payload = _payload(tx)
    endorsements = [_tx_to_dict(endorsement) for endorsement in get_endorsements(_tx_id(tx) or "", chain)]
    return VerifyDetail(
        result=result,
        message=message,
        image_hash=image_hash,
        phash=uploaded_phash,
        matched_tx_id=_tx_id(tx),
        device_id=_as_optional_str(payload.get("device_id")),
        timestamp=_timestamp(tx),
        location=_as_optional_str(payload.get("location")),
        capture=_tx_to_dict(tx),
        endorsements=endorsements,
        phash_distance=phash_distance_value,
        signature_valid=signature_valid,
    )


def _has_valid_registration(
    device_id: object,
    sender: str | None,
    chain: "Chain",
) -> bool:
    if not isinstance(device_id, str) or sender is None:
        return False
    for tx in chain.get_all_transactions():
        payload = _payload(tx)
        if (
            _tx_type(tx) in REGISTER_TYPES
            and payload.get("device_id") == device_id
            and payload.get("public_key") == sender
            and _sender(tx) == sender
        ):
            return _signature_valid(tx)
    return False


def _signature_valid(tx: object) -> bool:
    sender = _sender(tx)
    signature = _signature(tx)
    signable_bytes = getattr(tx, "signable_bytes", None)
    if sender is None or signature is None or not callable(signable_bytes):
        return False
    return verify(sender, signable_bytes(), signature)


def _tx_to_dict(tx: object) -> dict[str, Any]:
    if isinstance(tx, dict):
        return dict(tx)
    to_dict = getattr(tx, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        return value if isinstance(value, dict) else {}
    return {
        "tx_id": _tx_id(tx),
        "tx_type": _tx_type(tx),
        "sender": _sender(tx),
        "payload": _payload(tx),
        "timestamp": _timestamp(tx),
        "signature": _signature(tx),
    }


def _tx_id(tx: object) -> str | None:
    if isinstance(tx, dict):
        return _as_optional_str(tx.get("tx_id"))
    return _as_optional_str(getattr(tx, "tx_id", None))


def _tx_type(tx: object) -> str | None:
    if isinstance(tx, dict):
        return _as_optional_str(tx.get("tx_type"))
    return _as_optional_str(getattr(tx, "tx_type", None))


def _sender(tx: object) -> str | None:
    if isinstance(tx, dict):
        return _as_optional_str(tx.get("sender"))
    return _as_optional_str(getattr(tx, "sender", None))


def _signature(tx: object) -> str | None:
    if isinstance(tx, dict):
        return _as_optional_str(tx.get("signature"))
    return _as_optional_str(getattr(tx, "signature", None))


def _payload(tx: object) -> dict[str, Any]:
    if isinstance(tx, dict):
        payload = tx.get("payload")
    else:
        payload = getattr(tx, "payload", None)
    return payload if isinstance(payload, dict) else {}


def _timestamp(tx: object) -> float | None:
    value = tx.get("timestamp") if isinstance(tx, dict) else getattr(tx, "timestamp", None)
    return value if isinstance(value, float | int) else None


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
