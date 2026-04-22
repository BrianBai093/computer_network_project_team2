"""
test_network.py — Unit tests for network layer (Member B)

Run: python -m pytest tests/test_network.py -v
"""

import pytest
from network.gossip import SeenMessages
from network.tracker import create_tracker_app


# ── SeenMessages ───────────────────────────────────────────

class TestSeenMessages:
    def test_first_time_returns_false(self):
        seen = SeenMessages()
        assert seen.seen("msg_001") is False

    def test_second_time_returns_true(self):
        seen = SeenMessages()
        seen.seen("msg_001")
        assert seen.seen("msg_001") is True

    def test_lru_eviction(self):
        seen = SeenMessages(maxsize=3)
        seen.seen("a")
        seen.seen("b")
        seen.seen("c")
        seen.seen("d")   # evicts "a"
        assert seen.seen("a") is False   # "a" was evicted, treated as new
        assert seen.size() == 3


# ── Tracker Flask app ──────────────────────────────────────

class TestTracker:
    @pytest.fixture
    def client(self):
        app = create_tracker_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_register_missing_url(self, client):
        resp = client.post("/register", json={})
        assert resp.status_code == 400

    def test_register_and_list(self, client):
        client.post("/register", json={"url": "http://peer1:8001"})
        resp = client.get("/peers")
        assert resp.status_code == 200
        assert "http://peer1:8001" in resp.get_json()["peers"]

    def test_peers_empty_initially(self, client):
        resp = client.get("/peers")
        # newly registered peers may or may not be pruned depending on timing
        assert resp.status_code == 200


# ── Peer server (Gossip API) ───────────────────────────────

class TestPeerServer:
    # TODO: set up a full node state fixture and test /api/transaction and /api/block
    # Requires: Chain, Mempool, SeenMessages, Wallet all wired together

    def test_placeholder(self):
        pass


# ── peer_client ────────────────────────────────────────────

class TestPeerClient:
    # TODO: use responses / unittest.mock to mock HTTP calls and verify
    # that broadcast_transaction and broadcast_block hit the right URLs

    def test_placeholder(self):
        pass
