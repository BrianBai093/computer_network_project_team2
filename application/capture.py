"""Photo capture workflow.

Hashes image data, builds and signs CAPTURE transactions, optionally checks chain
duplicates when a Chain is provided, and submits accepted records to Mempool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from application.image_hash import compute_image_hash, compute_phash
from application.wallet import Wallet
from application.workflow import sign_transaction, submit_transaction, transaction_class

if TYPE_CHECKING:
    from blockchain.chain import Chain
    from blockchain.mempool import Mempool
    from blockchain.transaction import Transaction


def record_capture(
    wallet: Wallet,
    image_data: bytes | str,
    mempool: "Mempool",
    location: str,
    chain: "Chain | None" = None,
) -> "Transaction":
    """Record a captured photo in the mempool.

    Args:
        wallet: Device wallet signing the capture.
        image_data: Image bytes or path to an image file.
        mempool: Layer 1 mempool to receive the signed transaction.
        location: Optional GPS or place string; pass ``""`` if unknown.
        chain: Optional Layer 1 chain used to reject duplicate image hashes.

    Returns:
        The signed CAPTURE transaction.

    Raises:
        ValueError: If the image cannot be decoded, a duplicate exists, or the
            mempool rejects the transaction.
        RuntimeError: If the Layer 1 Transaction class is unavailable.
    """
    image_hash = compute_image_hash(image_data)
    if chain is not None and _image_hash_exists(chain, image_hash):
        raise ValueError("image_hash already exists on chain")

    phash = compute_phash(image_data)
    transaction = transaction_class()
    tx = transaction.make_capture(
        wallet.public_key,
        wallet.device_id,
        image_hash,
        phash,
        location or "",
    )
    sign_transaction(tx, wallet.private_key)
    return submit_transaction(tx, mempool)


def _image_hash_exists(chain: "Chain", image_hash: str) -> bool:
    for tx in chain.get_all_transactions():
        if _tx_type(tx) == "CAPTURE" and _payload(tx).get("image_hash") == image_hash:
            return True
    return False


def _tx_type(tx: object) -> str | None:
    if isinstance(tx, dict):
        return tx.get("tx_type")
    return getattr(tx, "tx_type", None)


def _payload(tx: object) -> dict[str, object]:
    if isinstance(tx, dict):
        payload = tx.get("payload")
    else:
        payload = getattr(tx, "payload", None)
    return payload if isinstance(payload, dict) else {}
