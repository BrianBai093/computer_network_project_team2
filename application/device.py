"""Device registration workflow.

Builds and signs REGISTER transactions from a Wallet, then submits them to Mempool
without reaching into network or blockchain internals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from application.wallet import Wallet
from application.workflow import sign_transaction, submit_transaction, transaction_class

if TYPE_CHECKING:
    from blockchain.mempool import Mempool
    from blockchain.transaction import Transaction


def register_device(
    wallet: Wallet,
    mempool: "Mempool",
    metadata: dict[str, Any] | None = None,
) -> "Transaction":
    """Register a device identity on the blockchain.

    Args:
        wallet: Device wallet that owns the public/private keypair.
        mempool: Layer 1 mempool to receive the signed transaction.
        metadata: Optional device metadata such as model or serial number.

    Returns:
        The signed REGISTER transaction.

    Raises:
        ValueError: If the mempool rejects the transaction.
        RuntimeError: If the Layer 1 Transaction class is unavailable.
    """
    transaction = transaction_class()
    tx = transaction.make_register(
        wallet.public_key,
        wallet.device_id,
        metadata or {},
    )
    sign_transaction(tx, wallet.private_key)
    return submit_transaction(tx, mempool)
