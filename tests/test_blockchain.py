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
from blockchain.mining import mine_block
from config import TX_REGISTER, TX_CAPTURE, TX_ENDORSE, TX_REVOKE, DIFFICULTY_BITS


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
        chain = Chain()
        block = mine_block(chain.last_block, [], "miner_pub", DIFFICULTY_BITS)
        assert block is not None
        result = chain.append_block(block, DIFFICULTY_BITS)
        assert result is True
        assert chain.height == 2

    def test_reject_invalid_block(self):
        chain = Chain()
        block = mine_block(chain.last_block, [], "miner_pub", DIFFICULTY_BITS)
        assert block is not None
        block.previous_hash = "f" * 64
        block.hash = block.compute_hash()
        result = chain.append_block(block, DIFFICULTY_BITS)
        assert result is False
        assert chain.height == 1

    def test_replace_with_longer_chain(self):
        chain_a = Chain()
        chain_b = Chain()
        for _ in range(2):
            block = mine_block(chain_b.last_block, [], "miner_b", DIFFICULTY_BITS)
            assert block is not None
            assert chain_b.append_block(block, DIFFICULTY_BITS)
        assert chain_b.height == 3
        result = chain_a.replace_chain(chain_b.get_all_blocks(), DIFFICULTY_BITS)
        assert result is True
        assert chain_a.height == 3

    def test_serialization_roundtrip(self):
        chain = Chain()
        restored = Chain.from_list(chain.to_list())
        assert restored.height == chain.height


# ── Mempool ────────────────────────────────────────────────

class TestMempool:
    def test_add_and_size(self):
        mp = Mempool(start_evictor=False)
        tx = Transaction.make_register("pub", "dev")
        assert mp.add(tx) is True
        assert mp.size() == 1

    def test_deduplication(self):
        mp = Mempool(start_evictor=False)
        tx = Transaction.make_register("pub", "dev")
        mp.add(tx)
        assert mp.add(tx) is False
        assert mp.size() == 1

    def test_get_pending_limit(self):
        mp = Mempool(start_evictor=False)
        for i in range(5):
            mp.add(Transaction.make_register(f"pub{i}", f"dev{i}"))
        assert len(mp.get_pending(limit=3)) == 3

    def test_remove(self):
        mp = Mempool(start_evictor=False)
        tx = Transaction.make_register("pub", "dev")
        mp.add(tx)
        mp.remove([tx.tx_id])
        assert mp.size() == 0
    
    def test_max_size(self, monkeypatch):
        """A full mempool refuses new transactions."""
        import blockchain.mempool as m
        monkeypatch.setattr(m, "MAX_MEMPOOL_SIZE", 3)

        mp = Mempool(start_evictor=False)
        for i in range(3):
            assert mp.add(Transaction.make_register(f"pub{i}", f"dev{i}")) is True
        overflow = Transaction.make_register("pubX", "devX")
        assert mp.add(overflow) is False
        assert mp.size() == 3

    def test_evict_expired(self):
        """Transactions older than TTL are removed by _evict_expired()."""
        import time
        mp = Mempool(start_evictor=False)
        tx = Transaction.make_register("pub", "dev")
        mp.add(tx)
        mp._entered_at[tx.tx_id] = time.time() - 999_999
        assert mp._evict_expired() == 1
        assert mp.size() == 0

    def test_remove_cleans_entered_at(self):
        """remove() must keep _pool and _entered_at in sync."""
        mp = Mempool(start_evictor=False)
        tx = Transaction.make_register("pub", "dev")
        mp.add(tx)
        mp.remove([tx.tx_id])
        assert tx.tx_id not in mp._pool
        assert tx.tx_id not in mp._entered_at

    def test_shutdown_is_idempotent(self):
        """shutdown() can be called multiple times safely."""
        mp = Mempool()
        mp.shutdown()
        mp.shutdown()
