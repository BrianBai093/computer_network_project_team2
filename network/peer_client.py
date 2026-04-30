"""
peer_client.py — Peer node broadcast / sync calls

Functions:
  broadcast_transaction(tx, peers, ttl, msg_id, exclude_self)
  broadcast_block(block, peers, ttl, msg_id, exclude_self)
  fetch_chain(peer_url) -> list[dict] | None
  fetch_peers(tracker_url) -> list[str]
  register_with_tracker(tracker_url, self_url) -> bool
"""

import hashlib
import json
import uuid
import logging

import requests

from config import GOSSIP_TTL

log = logging.getLogger(__name__)


def _new_msg_id(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Broadcast ─────────────────────────────────────────────────────────────────

def broadcast_transaction(tx, peers: list[str],
                          ttl: int = GOSSIP_TTL,
                          msg_id: str = "",
                          exclude_self: str = "") -> None:
    """Broadcast a transaction to known peers (fire-and-forget)."""
    if not msg_id:
        msg_id = _new_msg_id(tx.to_dict())
    payload = {"tx": tx.to_dict(), "ttl": ttl, "msg_id": msg_id}
    for peer in peers:
        if peer == exclude_self:
            continue
        try:
            requests.post(f"{peer}/api/transaction", json=payload, timeout=3)
        except Exception as e:
            log.debug("broadcast_transaction to %s failed: %s", peer, e)


def broadcast_block(block, peers: list[str],
                    ttl: int = GOSSIP_TTL,
                    msg_id: str = "",
                    exclude_self: str = "") -> None:
    """Broadcast a block to known peers (fire-and-forget)."""
    if not msg_id:
        msg_id = _new_msg_id(block.to_dict())
    payload = {"block": block.to_dict(), "ttl": ttl, "msg_id": msg_id}
    for peer in peers:
        if peer == exclude_self:
            continue
        try:
            requests.post(f"{peer}/api/block", json=payload, timeout=3)
        except Exception as e:
            log.debug("broadcast_block to %s failed: %s", peer, e)


# ── Sync ──────────────────────────────────────────────────────────────────────

def fetch_chain(peer_url: str) -> list[dict] | None:
    """Fetch the full chain from the specified peer; returns None on failure."""
    try:
        resp = requests.get(f"{peer_url}/api/blocks", timeout=5)
        resp.raise_for_status()
        return resp.json().get("chain")
    except Exception as e:
        log.debug("fetch_chain from %s failed: %s", peer_url, e)
        return None


def fetch_peers(tracker_url: str) -> list[str]:
    """Fetch the list of active peers from the Tracker; returns an empty list on failure."""
    try:
        resp = requests.get(f"{tracker_url}/peers", timeout=5)
        resp.raise_for_status()
        return resp.json().get("peers", [])
    except Exception as e:
        log.debug("fetch_peers from %s failed: %s", tracker_url, e)
        return []


def register_with_tracker(tracker_url: str, self_url: str) -> bool:
    """Register this node with the Tracker; returns True on success."""
    try:
        resp = requests.post(
            f"{tracker_url}/register",
            json={"url": self_url},
            timeout=5,
        )
        return resp.status_code == 200
    except Exception as e:
        log.debug("register_with_tracker failed: %s", e)
        return False
