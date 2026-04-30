"""Internal transaction workflow helpers.

Centralizes late Transaction loading, signing, and mempool submission for Layer 3
workflow modules without importing the blockchain package at module import time.
"""

from __future__ import annotations

from typing import Any

from application.crypto_utils import sign


def transaction_class() -> Any:
    """Return the Layer 1 Transaction class.

    Returns:
        The ``blockchain.transaction.Transaction`` class.

    Raises:
        RuntimeError: If the Layer 1 package is unavailable.
    """
    try:
        from blockchain.transaction import Transaction
    except ModuleNotFoundError as exc:
        raise RuntimeError("blockchain.transaction.Transaction is unavailable") from exc
    return Transaction


def sign_transaction(tx: Any, private_key: str) -> Any:
    """Attach a signature to a transaction.

    Args:
        tx: Layer 1 transaction instance.
        private_key: Hex-encoded ECDSA private key.

    Returns:
        The same transaction with ``signature`` set.
    """
    tx.signature = sign(private_key, tx.signable_bytes())
    return tx


def submit_transaction(tx: Any, mempool: Any) -> Any:
    """Submit a transaction to the Layer 1 mempool.

    Args:
        tx: Layer 1 transaction instance.
        mempool: Layer 1 mempool exposing ``add(tx)``.

    Returns:
        The submitted transaction.

    Raises:
        ValueError: If the mempool rejects the transaction.
    """
    if not mempool.add(tx):
        tx_id = getattr(tx, "tx_id", "<unknown>")
        raise ValueError(f"transaction {tx_id} was rejected by mempool")
    return tx
