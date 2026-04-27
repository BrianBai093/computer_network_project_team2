"""Application workflow simulation tests.

Runs in-process user scenarios without starting P2P nodes: register a device,
record a photo, endorse the capture, and verify exact, modified, and unknown images.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import types
from io import BytesIO
from typing import Any

import pytest
from PIL import Image

from application.capture import record_capture
from application.device import register_device
from application.endorse import endorse_capture
from application.models import VerifyResult
from application.verify import verify_image
from application.wallet import Wallet


class SimTransaction:
    """In-process transaction fake with the Layer 1 public factory methods."""

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
    ) -> "SimTransaction":
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
    ) -> "SimTransaction":
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
    ) -> "SimTransaction":
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


class SimMempool:
    """In-process mempool fake used by the simulation."""

    def __init__(self) -> None:
        self.transactions: list[SimTransaction] = []

    def add(self, tx: SimTransaction) -> bool:
        if any(existing.tx_id == tx.tx_id for existing in self.transactions):
            return False
        self.transactions.append(tx)
        return True

    def drain(self) -> list[SimTransaction]:
        transactions = self.transactions
        self.transactions = []
        return transactions


class SimChain:
    """In-process chain fake exposing ``get_all_transactions``."""

    def __init__(self) -> None:
        self.transactions: list[SimTransaction] = []

    def get_all_transactions(self) -> list[SimTransaction]:
        return list(self.transactions)

    def append_transactions(self, transactions: list[SimTransaction]) -> None:
        self.transactions.extend(transactions)


@pytest.fixture(autouse=True)
def sim_blockchain_module(monkeypatch: pytest.MonkeyPatch) -> None:
    blockchain_module = types.ModuleType("blockchain")
    transaction_module = types.ModuleType("blockchain.transaction")
    transaction_module.Transaction = SimTransaction
    monkeypatch.setitem(sys.modules, "blockchain", blockchain_module)
    monkeypatch.setitem(sys.modules, "blockchain.transaction", transaction_module)


def make_demo_png() -> bytes:
    image = Image.new("RGB", (48, 48), (240, 240, 240))
    for x_coord in range(8, 40):
        image.putpixel((x_coord, 16), (20, 20, 20))
        image.putpixel((x_coord, 32), (20, 20, 20))
    for y_coord in range(16, 33):
        image.putpixel((8, y_coord), (20, 20, 20))
        image.putpixel((39, y_coord), (20, 20, 20))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_modified_demo_png(image_bytes: bytes) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG", compress_level=0)
    return buffer.getvalue()


def test_in_process_register_capture_endorse_verify_flow() -> None:
    chain = SimChain()
    mempool = SimMempool()
    camera_wallet = Wallet.generate()
    newsroom_wallet = Wallet.generate()
    image_bytes = make_demo_png()
    modified_bytes = make_modified_demo_png(image_bytes)

    register_device(camera_wallet, mempool, {"model": "demo-camera"})
    register_device(newsroom_wallet, mempool, {"name": "demo-newsroom"})
    chain.append_transactions(mempool.drain())

    capture_tx = record_capture(camera_wallet, image_bytes, mempool, "New York", chain=chain)
    chain.append_transactions(mempool.drain())

    endorse_capture(newsroom_wallet, capture_tx.tx_id, mempool, chain=chain)
    chain.append_transactions(mempool.drain())

    exact = verify_image(image_bytes, chain).to_dict()
    modified = verify_image(modified_bytes, chain).to_dict()
    unknown = verify_image(image_bytes, SimChain()).to_dict()

    assert exact["result"] == VerifyResult.AUTHENTIC.value
    assert exact["device_id"] == camera_wallet.device_id
    assert exact["location"] == "New York"
    assert len(exact["endorsements"]) == 1
    assert modified["result"] == VerifyResult.SUSPICIOUS.value
    assert unknown["result"] == VerifyResult.UNKNOWN.value
