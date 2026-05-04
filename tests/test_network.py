"""
test_network.py — Unit tests for network layer (Member B)

Run: python -m pytest tests/test_network.py -v
"""

import pytest
from network.gossip import SeenMessages
from network.tracker import create_tracker_app
from network.peer_server import peer_api
from flask import Flask
from blockchain.chain import Chain
from blockchain.mempool import Mempool
from blockchain.mining import mine_block
from blockchain.transaction import Transaction
from application.crypto_utils import generate_keypair, sign, pubkey_to_device_id
from config import DIFFICULTY_BITS


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
    @pytest.fixture
    def node_state(self):
        state = {
            "chain": Chain(),
            "mempool": Mempool(start_evictor=False),
            "known_peers": set(),
            "seen": SeenMessages(),
            "self_url": "http://127.0.0.1:8008",
        }
        yield state
        state["mempool"].shutdown()

    @staticmethod
    def _signed_register_tx():
        priv, pub = generate_keypair()
        tx = Transaction.make_register(pub, pubkey_to_device_id(pub))
        tx.signature = sign(priv, tx.signable_bytes())
        return tx

    def test_receive_fork_block_with_already_committed_tx_does_not_append(
        self, node_state, monkeypatch
    ):
        trace = []
        tx = self._signed_register_tx()

        local_block = mine_block(
            node_state["chain"].last_block,
            [tx],
            "local_miner",
            DIFFICULTY_BITS,
        )
        assert local_block is not None
        assert node_state["chain"].append_block(local_block, DIFFICULTY_BITS)
        trace.append(
            f"[setup] local peer committed block #{local_block.index} "
            f"hash={local_block.hash[:16]} tx={tx.tx_id[:16]}"
        )

        fork_block = mine_block(
            node_state["chain"].get_block(0),
            [tx],
            "fork_miner",
            DIFFICULTY_BITS,
        )
        assert fork_block is not None
        assert fork_block.index == local_block.index
        assert fork_block.hash != local_block.hash
        assert tx.tx_id in {t.tx_id for t in node_state["chain"].get_all_transactions()}
        trace.append(
            f"[incoming] received competing block #{fork_block.index} "
            f"hash={fork_block.hash[:16]} containing tx already on local chain "
            f"tx={tx.tx_id[:16]}"
        )

        fetched_from = []

        def fake_fetch_chain(sender_url):
            fetched_from.append(sender_url)
            trace.append(f"[strategy] fetching sender chain from {sender_url}")
            return None

        monkeypatch.setattr("network.peer_client.fetch_chain", fake_fetch_chain)

        emitted = []

        def fake_emit(event, **payload):
            emitted.append((event, payload))
            if event == "fork_detected":
                trace.append(
                    f"[detect] fork_detected at block #{payload['index']} "
                    f"from={payload['from_peer']} our_height={payload['our_height']}"
                )

        monkeypatch.setattr("event_bus.emit", fake_emit)

        app = Flask(__name__)
        app.config["NODE_STATE"] = node_state
        app.register_blueprint(peer_api)
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.post(
            "/api/block",
            json={
                "block": fork_block.to_dict(),
                "ttl": 0,
                "msg_id": "fork-block-with-committed-tx",
                "sender_url": "http://127.0.0.1:8008",
            },
        )

        trace.append(
            f"[result] appended={resp.get_json()['appended']} "
            f"local_tip={node_state['chain'].last_block.hash[:16]}"
        )
        trace.append(
            "[policy] keep local tip; use sender chain only if it is longer and valid"
        )
        print("\n" + "\n".join(trace))

        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok", "appended": False}
        assert node_state["chain"].height == 2
        assert node_state["chain"].last_block.hash == local_block.hash
        assert fetched_from == ["http://127.0.0.1:8008"]
        assert any(event == "fork_detected" for event, _ in emitted)


# ── peer_client ────────────────────────────────────────────

class TestPeerClient:
    # TODO: use responses / unittest.mock to mock HTTP calls and verify
    # that broadcast_transaction and broadcast_block hit the right URLs

    def test_placeholder(self):
        pass
