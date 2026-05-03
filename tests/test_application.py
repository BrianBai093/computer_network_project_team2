"""
test_application.py — Unit tests for application layer (Member C)

Run: python -m pytest tests/test_application.py -v
"""

import pytest
from application.crypto_utils import generate_keypair, sign, verify, pubkey_to_device_id
from application.image_utils import sha256_bytes, phash_distance
from application.wallet import Wallet


# ── crypto_utils ───────────────────────────────────────────

class TestCryptoUtils:
    def test_generate_keypair(self):
        priv, pub = generate_keypair()
        assert len(priv) > 0
        assert len(pub) > 0

    def test_sign_verify_roundtrip(self):
        priv, pub = generate_keypair()
        data = b"hello TrueShot"
        sig = sign(priv, data)
        assert verify(pub, data, sig) is True

    def test_verify_wrong_data(self):
        priv, pub = generate_keypair()
        sig = sign(priv, b"original")
        assert verify(pub, b"tampered", sig) is False

    def test_verify_wrong_key(self):
        priv, pub1 = generate_keypair()
        _, pub2 = generate_keypair()
        sig = sign(priv, b"data")
        assert verify(pub2, b"data", sig) is False

    def test_device_id_length(self):
        _, pub = generate_keypair()
        device_id = pubkey_to_device_id(pub)
        assert len(device_id) == 32


# ── image_utils ────────────────────────────────────────────

class TestImageUtils:
    def test_sha256_deterministic(self):
        data = b"test image bytes"
        assert sha256_bytes(data) == sha256_bytes(data)

    def test_sha256_different_data(self):
        assert sha256_bytes(b"aaa") != sha256_bytes(b"bbb")

    def test_sha256_length(self):
        assert len(sha256_bytes(b"test")) == 64

    def test_phash_identical_images(self):
        # TODO: create two identical in-memory images and verify distance == 0
        pass

    def test_phash_similar_images(self):
        # TODO: create slightly modified images and verify distance <= PHASH_THRESHOLD
        pass

    def test_phash_different_images(self):
        # TODO: create very different images and verify distance > PHASH_THRESHOLD
        pass


# ── Wallet ─────────────────────────────────────────────────

class TestWallet:
    def test_generate(self):
        w = Wallet.generate()
        assert w.private_key
        assert w.public_key
        assert len(w.device_id) == 32

    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "test_wallet.json")
        w1 = Wallet.generate()
        w1.save(path)
        w2 = Wallet.from_file(path)
        assert w1.public_key == w2.public_key
        assert w1.private_key == w2.private_key

    def test_from_file_creates_if_missing(self, tmp_path):
        path = str(tmp_path / "new_wallet.json")
        w = Wallet.from_file(path)
        assert w.public_key != ""
        import os; assert os.path.exists(path)


# ── device / capture / endorse / verify workflows ──────────

class TestWorkflows:
    # TODO: wire up Chain + Mempool + Wallet and test end-to-end:
    #   1. register_device  -> tx in mempool
    #   2. mine block       -> tx on chain
    #   3. record_capture   -> tx in mempool
    #   4. mine block       -> tx on chain
    #   5. verify_image     -> AUTHENTIC
    #   6. endorse_capture  -> tx in mempool
    #   7. mine block       -> endorsement_count == 1
    #   8. revoke device    -> verify_image -> SUSPICIOUS

    def test_placeholder(self):
        pass
