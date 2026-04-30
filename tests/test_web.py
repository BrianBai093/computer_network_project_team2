"""
test_web.py — Integration tests for Web UI + run_peer entry point (Member D)

Run: python -m pytest tests/test_web.py -v
"""

from io import BytesIO

import pytest
from PIL import Image

from blockchain.chain import Chain
from blockchain.mempool import Mempool
from network.gossip import SeenMessages
from application.wallet import Wallet
from web.app import create_app


# ── Fixtures ───────────────────────────────────────────────

@pytest.fixture
def node_state():
    return {
        "chain": Chain(),
        "mempool": Mempool(),
        "known_peers": set(),
        "seen": SeenMessages(),
        "wallet": Wallet.generate(),
        "self_url": "http://localhost:8001",
    }


@pytest.fixture
def client(node_state):
    app = create_app(node_state)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def png_image():
    """Create a small valid PNG image in memory for upload tests."""
    image = Image.new("RGB", (32, 32), color=(255, 0, 0))
    buf = BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ── Home page ──────────────────────────────────────────────

class TestIndex:
    def test_home_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_home_contains_trueshot(self, client):
        resp = client.get("/")
        assert b"TrueShot" in resp.data


# ── Register page ──────────────────────────────────────────

class TestRegister:
    def test_get_register_page(self, client):
        resp = client.get("/register")
        assert resp.status_code == 200

    def test_post_register(self, client):
        resp = client.post("/register", data={"model": "TestCam", "serial": "SN001"},
                           follow_redirects=True)
        assert resp.status_code == 200

    def test_register_adds_to_mempool(self, client, node_state):
        client.post("/register", data={"model": "TestCam"})
        assert node_state["mempool"].size() == 1


# ── Capture page ───────────────────────────────────────────

class TestCapture:
    def test_get_capture_page(self, client):
        resp = client.get("/capture")
        assert resp.status_code == 200

    def test_post_capture_no_file(self, client):
        resp = client.post("/capture", data={}, follow_redirects=True)
        assert resp.status_code == 200   # redirects back with flash warning

    def test_post_capture_with_image(self, client, node_state, png_image):
        before = node_state["mempool"].size()
        resp = client.post(
            "/capture",
            data={
                "location": "Test Lab",
                "image": (png_image, "capture.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert node_state["mempool"].size() == before + 1


# ── Verify page ────────────────────────────────────────────

class TestVerify:
    def test_get_verify_page(self, client):
        resp = client.get("/verify")
        assert resp.status_code == 200

    def test_post_verify_unknown_image(self, client, png_image):
        resp = client.post(
            "/verify",
            data={"image": (png_image, "unknown.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        assert b"UNKNOWN" in resp.data or b"Unknown" in resp.data or b"unknown" in resp.data


# ── Endorse page ───────────────────────────────────────────

class TestEndorse:
    def test_get_endorse_page(self, client):
        resp = client.get("/endorse")
        assert resp.status_code == 200

    def test_post_endorse_missing_tx_id(self, client):
        resp = client.post("/endorse", data={"target_tx_id": ""},
                           follow_redirects=True)
        assert resp.status_code == 200


# ── Explorer page ──────────────────────────────────────────

class TestExplorer:
    def test_explorer_shows_genesis(self, client):
        resp = client.get("/explorer")
        assert resp.status_code == 200
        assert b"Block Explorer" in resp.data

    def test_block_detail(self, client):
        resp = client.get("/explorer/block/0")
        assert resp.status_code == 200
        assert b"Block #0" in resp.data

    def test_block_detail_not_found(self, client):
        resp = client.get("/explorer/block/9999", follow_redirects=True)
        assert resp.status_code == 200

    def test_missing_page_returns_custom_404(self, client):
        resp = client.get("/missing-page")
        assert resp.status_code == 404
        assert b"Page Not Found" in resp.data


# ── Peer API ───────────────────────────────────────────────

class TestPeerAPI:
    def test_api_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_api_blocks_returns_chain(self, client):
        resp = client.get("/api/blocks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "chain" in data
        assert len(data["chain"]) == 1   # genesis only

    def test_api_peers_returns_list(self, client):
        resp = client.get("/api/peers")
        assert resp.status_code == 200
        assert "peers" in resp.get_json()
