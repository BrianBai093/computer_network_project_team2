"""
capture.py — Photo capture record workflow

Functions:
  record_capture(wallet, image_data, mempool, location) -> Transaction
      Compute SHA-256 + pHash of the image, create a CAPTURE transaction,
      sign it, and add it to the mempool.
"""

from application.wallet import Wallet
from application.crypto_utils import sign
from application.image_utils import sha256_bytes, phash_bytes, sha256_file, phash_file
from blockchain.transaction import Transaction
from blockchain.mempool import Mempool


def record_capture(
    wallet:     Wallet,
    image_data: bytes | str,   # bytes = raw image data; str = file path
    mempool:    Mempool,
    location:   str = "",
) -> Transaction:
    """
    Create a CAPTURE transaction for an image, sign it, and add it to the mempool.

    Args:
        wallet:      Wallet instance holding the key pair
        image_data:  Raw image bytes or a file path string
        mempool:     Transaction pool
        location:    Optional GPS / location string

    Returns:
        Signed CAPTURE Transaction
    """
    if isinstance(image_data, bytes):
        img_hash = sha256_bytes(image_data)
        p_hash   = phash_bytes(image_data)
    else:
        img_hash = sha256_file(image_data)
        p_hash   = phash_file(image_data)

    tx = Transaction.make_capture(
        sender_pubkey = wallet.public_key,
        device_id     = wallet.device_id,
        image_hash    = img_hash,
        phash         = p_hash,
        location      = location,
    )
    tx.signature = sign(wallet.private_key, tx.signable_bytes())
    mempool.add(tx)
    return tx
