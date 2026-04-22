"""
endorse.py — Endorsement workflow

Functions:
  endorse_capture(wallet, target_tx_id, mempool) -> Transaction
      Create an ENDORSE transaction, sign it, and add it to the mempool.

  get_endorsements(target_tx_id, chain) -> list[Transaction]
      Return all on-chain endorsements for the specified CAPTURE transaction.
"""

from application.wallet import Wallet
from application.crypto_utils import sign
from blockchain.transaction import Transaction
from blockchain.mempool import Mempool
from blockchain.chain import Chain
from config import TX_ENDORSE


def endorse_capture(
    wallet:       Wallet,
    target_tx_id: str,
    mempool:      Mempool,
) -> Transaction:
    """
    Create an endorsement transaction for the specified CAPTURE transaction,
    sign it, and add it to the mempool.

    Args:
        wallet:       Endorser's Wallet instance
        target_tx_id: TX ID of the CAPTURE transaction being endorsed
        mempool:      Transaction pool

    Returns:
        Signed ENDORSE Transaction
    """
    tx = Transaction.make_endorse(
        sender_pubkey      = wallet.public_key,
        target_tx_id       = target_tx_id,
        endorser_device_id = wallet.device_id,
    )
    tx.signature = sign(wallet.private_key, tx.signable_bytes())
    mempool.add(tx)
    return tx


def get_endorsements(target_tx_id: str, chain: Chain) -> list[Transaction]:
    """Return all ENDORSE transactions on the chain that endorse the given CAPTURE."""
    result = []
    for tx in chain.get_all_transactions():
        if tx.tx_type == TX_ENDORSE:
            if tx.payload.get("target_tx_id") == target_tx_id:
                result.append(tx)
    return result
