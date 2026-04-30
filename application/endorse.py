"""Capture endorsement workflow.

Builds and signs ENDORSE transactions, optionally validates target captures and
self-endorsement when a Chain is provided, and queries existing endorsements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from application.wallet import Wallet
from application.workflow import sign_transaction, submit_transaction, transaction_class

if TYPE_CHECKING:
    from blockchain.chain import Chain
    from blockchain.mempool import Mempool
    from blockchain.transaction import Transaction


def endorse_capture(
    wallet: Wallet,
    target_tx_id: str,
    mempool: "Mempool",
    chain: "Chain | None" = None,
) -> "Transaction":
    """Endorse an existing CAPTURE transaction.

    Args:
        wallet: Endorser wallet signing the endorsement.
        target_tx_id: Transaction id of the CAPTURE being endorsed.
        mempool: Layer 1 mempool to receive the signed transaction.
        chain: Optional Layer 1 chain used to validate the target capture.

    Returns:
        The signed ENDORSE transaction.

    Raises:
        ValueError: If the target is missing, self-endorsement is attempted, or
            the mempool rejects the transaction.
        RuntimeError: If the Layer 1 Transaction class is unavailable.
    """
    if chain is not None:
        target = _find_capture(target_tx_id, chain)
        if target is None:
            raise ValueError("target capture transaction was not found")
        if _payload(target).get("device_id") == wallet.device_id:
            raise ValueError("devices cannot endorse their own captures")

    transaction = transaction_class()
    tx = transaction.make_endorse(
        wallet.public_key,
        target_tx_id,
        wallet.device_id,
    )
    sign_transaction(tx, wallet.private_key)
    return submit_transaction(tx, mempool)


def get_endorsements(target_tx_id: str, chain: "Chain") -> list["Transaction"]:
    """Return endorsements for a target CAPTURE transaction.

    Args:
        target_tx_id: Transaction id of the target CAPTURE.
        chain: Layer 1 chain to query.

    Returns:
        ENDORSE transactions that reference ``target_tx_id``.
    """
    return [
        tx
        for tx in chain.get_all_transactions()
        if _tx_type(tx) == "ENDORSE" and _payload(tx).get("target_tx_id") == target_tx_id
    ]


def _find_capture(target_tx_id: str, chain: "Chain") -> "Transaction | None":
    for tx in chain.get_all_transactions():
        if _tx_id(tx) == target_tx_id and _tx_type(tx) == "CAPTURE":
            return tx
    return None


def _tx_id(tx: object) -> str | None:
    if isinstance(tx, dict):
        return tx.get("tx_id")
    return getattr(tx, "tx_id", None)


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
