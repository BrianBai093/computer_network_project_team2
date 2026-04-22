"""
device.py — Device registration workflow

Functions:
  register_device(wallet, mempool, metadata) -> Transaction
      Create a REGISTER transaction, sign it, and add it to the mempool.

  is_device_registered(device_id, chain) -> bool
      Check whether a REGISTER transaction for this device exists on the chain.

  is_device_revoked(device_id, chain) -> bool
      Check whether a REVOKE transaction targeting this device exists on the chain.
"""

from application.wallet import Wallet
from application.crypto_utils import sign
from blockchain.transaction import Transaction
from blockchain.mempool import Mempool
from blockchain.chain import Chain
from config import TX_REGISTER, TX_REVOKE


def register_device(wallet: Wallet, mempool: Mempool,
                    metadata: dict | None = None) -> Transaction:
    """
    Create a device registration transaction, sign it with the private key,
    and add it to the mempool.

    Args:
        wallet:   Wallet instance holding the key pair
        mempool:  Transaction pool
        metadata: Optional device metadata (model, serial number, etc.)

    Returns:
        Signed REGISTER Transaction
    """
    tx = Transaction.make_register(
        sender_pubkey = wallet.public_key,
        device_id     = wallet.device_id,
        metadata      = metadata,
    )
    tx.signature = sign(wallet.private_key, tx.signable_bytes())
    mempool.add(tx)
    return tx


def is_device_registered(device_id: str, chain: Chain) -> bool:
    """Return True if a REGISTER transaction for device_id exists on the chain."""
    for tx in chain.get_all_transactions():
        if tx.tx_type == TX_REGISTER:
            if tx.payload.get("device_id") == device_id:
                return True
    return False


def is_device_revoked(device_id: str, chain: Chain) -> bool:
    """Return True if a REVOKE transaction targeting device_id exists on the chain."""
    for tx in chain.get_all_transactions():
        if tx.tx_type == TX_REVOKE:
            if tx.payload.get("target_device_id") == device_id:
                return True
    return False
