"""
merkle.py — Merkle tree

Given a list of transaction IDs (list of strings), builds the Merkle tree and
returns the root hash.  An empty list returns an all-zero hash.
"""

import hashlib


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def merkle_root(tx_ids: list[str]) -> str:
    """
    Compute the Merkle root of a list of transaction IDs.

    Args:
        tx_ids: List of transaction ID strings

    Returns:
        Merkle root hash (hex string); returns 64 '0' characters for an empty list
    """
    if not tx_ids:
        return "0" * 64

    layer = [_sha256(tx_id) for tx_id in tx_ids]

    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])   # Duplicate last node for odd-length layer

        next_layer = []
        for i in range(0, len(layer), 2):
            combined = layer[i] + layer[i + 1]
            next_layer.append(_sha256(combined))
        layer = next_layer

    return layer[0]
