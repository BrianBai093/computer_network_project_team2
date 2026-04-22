"""
test_blockchain.py — Unit tests for blockchain layer (Member A)

Run: python -m pytest tests/test_blockchain.py -v
"""

import pytest
from blockchain.transaction import Transaction
from blockchain.merkle import merkle_root
from blockchain.block import Block
from blockchain.chain import Chain
from blockchain.mempool import Mempool
from config import TX_REGISTER, TX_CAPTURE, TX_ENDORSE, TX_REVOKE


# ── Transaction ────────────────────────────────────────────

class TestTransaction:
    def test_make_register(self):
        tx = Transaction.make_register("pubkey_hex", "device_001")
        assert tx.tx_type == TX_REGISTER
        assert tx.payload["device_id"] == "device_001"
        assert tx.tx_id != ""

    def test_make_capture(self):
        tx = Transaction.make_capture("pubkey_hex", "device_001", "sha256hash", "phash")
        assert tx.tx_type == TX_CAPTURE
        assert tx.payload["image_hash"] == "sha256hash"

    def test_make_endorse(self):
        tx = Transaction.make_endorse("pubkey_hex", "target_tx_id", "device_001")
        assert tx.tx_type == TX_ENDORSE

    def test_make_revoke(self):
        tx = Transaction.make_revoke("pubkey_hex", "device_001", "compromised")
        assert tx.tx_type == TX_REVOKE

    def test_serialization_roundtrip(self):
        tx = Transaction.make_register("pubkey_hex", "device_001")
        restored = Transaction.from_dict(tx.to_dict())
        assert restored.tx_id == tx.tx_id
        assert restored.tx_type == tx.tx_type

    def test_compute_id_deterministic(self):
        tx1 = Transaction.make_register("pubkey", "dev")
        tx2 = Transaction.from_dict(tx1.to_dict())
        assert tx1.tx_id == tx2.tx_id


# ── Merkle ─────────────────────────────────────────────────

class TestMerkle:
    def test_empty(self):
        assert merkle_root([]) == "0" * 64

    def test_single(self):
        result = merkle_root(["abc"])
        assert len(result) == 64

    def test_two(self):
        result = merkle_root(["abc", "def"])
        assert len(result) == 64

    def test_deterministic(self):
        ids = ["a", "b", "c"]
        assert merkle_root(ids) == merkle_root(ids)

    def test_order_sensitive(self):
        assert merkle_root(["a", "b"]) != merkle_root(["b", "a"])


# ── Block ──────────────────────────────────────────────────

class TestBlock:
    def test_compute_hash(self):
        blk = Block(index=0, previous_hash="0" * 64)
        assert len(blk.hash) == 64

    def test_serialization_roundtrip(self):
        blk = Block(index=1, previous_hash="0" * 64)
        restored = Block.from_dict(blk.to_dict())
        assert restored.hash == blk.hash
        assert restored.index == blk.index


# ── Chain ──────────────────────────────────────────────────

class TestChain:
    def test_genesis_created(self):
        chain = Chain()
        assert chain.height == 1
        assert chain.last_block.index == 0

    def test_append_valid_block(self):
        # TODO: mine a valid block and append it
        pass

    def test_reject_invalid_block(self):
        # TODO: verify that a block with wrong previous_hash is rejected
        pass

    def test_replace_with_longer_chain(self):
        # TODO: build two chains and verify the longer one wins
        pass

    def test_serialization_roundtrip(self):
        chain = Chain()
        restored = Chain.from_list(chain.to_list())
        assert restored.height == chain.height


# ── Mempool ────────────────────────────────────────────────

class TestMempool:
    def test_add_and_size(self):
        mp = Mempool()
        tx = Transaction.make_register("pub", "dev")
        assert mp.add(tx) is True
        assert mp.size() == 1

    def test_deduplication(self):
        mp = Mempool()
        tx = Transaction.make_register("pub", "dev")
        mp.add(tx)
        assert mp.add(tx) is False
        assert mp.size() == 1

    def test_get_pending_limit(self):
        mp = Mempool()
        for i in range(5):
            mp.add(Transaction.make_register(f"pub{i}", f"dev{i}"))
        assert len(mp.get_pending(limit=3)) == 3

    def test_remove(self):
        mp = Mempool()
        tx = Transaction.make_register("pub", "dev")
        mp.add(tx)
        mp.remove([tx.tx_id])
        assert mp.size() == 0
