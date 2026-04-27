"""Application layer tests.

Exercises wallet, signatures, registration, capture, endorsement, and verification
against real Chain, Mempool, and Transaction APIs from Layer 1.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import types
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from application.capture import record_capture
from application.crypto_utils import derive_device_id, sign, verify
from application.device import register_device
from application.endorse import endorse_capture, get_endorsements
from application.image_hash import compute_image_hash, compute_phash
from application.models import VerifyResult
from application.verify import verify_image
from application.wallet import Wallet


class FakeTransaction:
    """Minimal test Transaction matching the frozen Layer 1 public API."""

    def __init__(
        self,
        tx_type: str,
        sender: str,
        payload: dict[str, Any],
        timestamp: float | None = None,
        signature: str = "",
    ) -> None:
        self.tx_type = tx_type
        self.sender = sender
        self.payload = payload
        self.timestamp = time.time() if timestamp is None else timestamp
        self.signature = signature
        self.tx_id = hashlib.sha256(self.signable_bytes()).hexdigest()

    @classmethod
    def make_register(
        cls,
        sender_pubkey: str,
        device_id: str,
        metadata: dict[str, Any],
    ) -> "FakeTransaction":
        return cls(
            "REGISTER",
            sender_pubkey,
            {
                "device_id": device_id,
                "public_key": sender_pubkey,
                "metadata": metadata,
            },
        )

    @classmethod
    def make_capture(
        cls,
        sender_pubkey: str,
        device_id: str,
        image_hash: str,
        phash: str,
        location: str,
    ) -> "FakeTransaction":
        return cls(
            "CAPTURE",
            sender_pubkey,
            {
                "device_id": device_id,
                "image_hash": image_hash,
                "phash": phash,
                "location": location,
            },
        )

    @classmethod
    def make_endorse(
        cls,
        sender_pubkey: str,
        target_tx_id: str,
        endorser_device_id: str,
    ) -> "FakeTransaction":
        return cls(
            "ENDORSE",
            sender_pubkey,
            {
                "target_tx_id": target_tx_id,
                "endorser_device_id": endorser_device_id,
            },
        )

    def signable_bytes(self) -> bytes:
        return json.dumps(
            {
                "tx_type": self.tx_type,
                "sender": self.sender,
                "payload": self.payload,
                "timestamp": self.timestamp,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return {
            "tx_id": self.tx_id,
            "tx_type": self.tx_type,
            "sender": self.sender,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "signature": self.signature,
        }


class FakeMempool:
    """Minimal mempool matching ``mempool.add(tx)``."""

    def __init__(self) -> None:
        self.transactions: list[FakeTransaction] = []

    def add(self, tx: FakeTransaction) -> bool:
        if any(existing.tx_id == tx.tx_id for existing in self.transactions):
            return False
        self.transactions.append(tx)
        return True


class FakeChain:
    """Minimal chain matching ``chain.get_all_transactions()``."""

    def __init__(self, transactions: list[FakeTransaction] | None = None) -> None:
        self.transactions = transactions or []

    def get_all_transactions(self) -> list[FakeTransaction]:
        return list(self.transactions)

    def add_transaction(self, tx: FakeTransaction) -> None:
        self.transactions.append(tx)


@pytest.fixture(autouse=True)
def fake_blockchain_module(monkeypatch: pytest.MonkeyPatch) -> None:
    blockchain_module = types.ModuleType("blockchain")
    transaction_module = types.ModuleType("blockchain.transaction")
    transaction_module.Transaction = FakeTransaction
    monkeypatch.setitem(sys.modules, "blockchain", blockchain_module)
    monkeypatch.setitem(sys.modules, "blockchain.transaction", transaction_module)


def make_png(color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    image = Image.new("RGB", (32, 32), color)
    for index in range(32):
        image.putpixel((index, index), (0, 0, 0))
        image.putpixel((31 - index, index), (0, 0, 0))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_modified_png(image_bytes: bytes) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG", compress_level=0)
    return buffer.getvalue()


def test_wallet_generate_save_and_load(tmp_path: Path) -> None:
    wallet = Wallet.generate()
    wallet_path = tmp_path / "wallet.json"

    wallet.save(str(wallet_path))
    loaded = Wallet.from_file(str(wallet_path))

    assert loaded.private_key == wallet.private_key
    assert loaded.public_key == wallet.public_key
    assert loaded.device_id == derive_device_id(wallet.public_key)


def test_signature_round_trip_and_failures() -> None:
    wallet = Wallet.generate()
    other_wallet = Wallet.generate()
    message = b"canonical transaction bytes"

    signature = sign(wallet.private_key, message)

    assert verify(wallet.public_key, message, signature)
    assert not verify(wallet.public_key, b"changed", signature)
    assert not verify(other_wallet.public_key, message, signature)
    assert not verify(wallet.public_key, message, "not-hex")


def test_register_device_signs_and_submits_transaction() -> None:
    wallet = Wallet.generate()
    mempool = FakeMempool()

    tx = register_device(wallet, mempool, {"model": "demo"})

    assert tx in mempool.transactions
    assert tx.tx_type == "REGISTER"
    assert tx.sender == wallet.public_key
    assert tx.payload["device_id"] == wallet.device_id
    assert verify(tx.sender, tx.signable_bytes(), tx.signature)


def test_record_capture_hashes_image_and_rejects_duplicate() -> None:
    wallet = Wallet.generate()
    image_bytes = make_png()
    mempool = FakeMempool()
    chain = FakeChain()

    tx = record_capture(wallet, image_bytes, mempool, "NYC", chain=chain)
    chain.add_transaction(tx)

    assert tx.payload["image_hash"] == compute_image_hash(image_bytes)
    assert tx.payload["phash"] == compute_phash(image_bytes)
    assert tx.payload["location"] == "NYC"
    assert verify(tx.sender, tx.signable_bytes(), tx.signature)

    with pytest.raises(ValueError, match="image_hash already exists"):
        record_capture(wallet, image_bytes, FakeMempool(), "NYC", chain=chain)


def test_record_capture_accepts_file_path(tmp_path: Path) -> None:
    wallet = Wallet.generate()
    image_bytes = make_png()
    image_path = tmp_path / "capture.png"
    image_path.write_bytes(image_bytes)

    tx = record_capture(wallet, str(image_path), FakeMempool(), "")

    assert tx.payload["image_hash"] == compute_image_hash(image_bytes)


def test_endorse_capture_validates_target_and_self_endorsement() -> None:
    camera_wallet = Wallet.generate()
    endorser_wallet = Wallet.generate()
    chain = FakeChain()

    register_tx = register_device(camera_wallet, FakeMempool())
    capture_tx = record_capture(camera_wallet, make_png(), FakeMempool(), "NYC")
    chain.add_transaction(register_tx)
    chain.add_transaction(capture_tx)

    endorse_tx = endorse_capture(endorser_wallet, capture_tx.tx_id, FakeMempool(), chain=chain)
    chain.add_transaction(endorse_tx)

    assert endorse_tx.tx_type == "ENDORSE"
    assert endorse_tx.payload["target_tx_id"] == capture_tx.tx_id
    assert get_endorsements(capture_tx.tx_id, chain) == [endorse_tx]

    with pytest.raises(ValueError, match="cannot endorse|devices cannot endorse"):
        endorse_capture(camera_wallet, capture_tx.tx_id, FakeMempool(), chain=chain)

    with pytest.raises(ValueError, match="not found"):
        endorse_capture(endorser_wallet, "missing", FakeMempool(), chain=chain)


def test_verify_image_outcomes() -> None:
    wallet = Wallet.generate()
    image_bytes = make_png()
    modified = make_modified_png(image_bytes)

    register_tx = register_device(wallet, FakeMempool())
    capture_tx = record_capture(wallet, image_bytes, FakeMempool(), "NYC")
    chain = FakeChain([register_tx, capture_tx])

    authentic = verify_image(image_bytes, chain)
    suspicious = verify_image(modified, chain)
    unknown = verify_image(image_bytes, FakeChain())

    assert authentic.result == VerifyResult.AUTHENTIC
    assert authentic.matched_tx_id == capture_tx.tx_id
    assert authentic.signature_valid is True
    assert suspicious.result == VerifyResult.SUSPICIOUS
    assert unknown.result == VerifyResult.UNKNOWN


def test_verify_bad_signature_is_not_authentic() -> None:
    wallet = Wallet.generate()
    image_bytes = make_png()
    register_tx = register_device(wallet, FakeMempool())
    capture_tx = record_capture(wallet, image_bytes, FakeMempool(), "NYC")
    capture_tx.signature = "bad-signature"

    detail = verify_image(image_bytes, FakeChain([register_tx, capture_tx]))

    assert detail.result == VerifyResult.SUSPICIOUS
    assert detail.signature_valid is False
