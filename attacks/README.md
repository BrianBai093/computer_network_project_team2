# TrueShot Blockchain Security Test Report

## Project Background

TrueShot is a blockchain-based photo anti-tampering system. Photos are hashed (SHA-256 + pHash), signed with ECDSA, and recorded on a PoW blockchain. Verification compares uploaded images against on-chain records.

This document presents a security audit of the system, including vulnerability analysis, attack tools, and a real attack demonstration conducted across two PCs on the same LAN.

## Network Topology

```
Attacker PC (10.206.116.8)              Victim PC (10.206.134.178)
┌─────────────────────────┐             ┌──────────────────────────────┐
│                         │    WiFi     │  Tracker (:50000)            │
│  attack_fake_chain.py  ─┼─────────────┤  Peer A  (:60001)           │
│                         │             │  Peer B  (:60002)           │
│  Flask :9997            │◄────────────┤  Peer C  (:60003)           │
│  (serves forged chain)  │  pull chain │                              │
└─────────────────────────┘             └──────────────────────────────┘
```

## Vulnerability Analysis

### V1: Tracker Has No Authentication [CRITICAL]

**File**: `network/tracker.py:37-46`

The `/register` endpoint accepts any URL with zero authentication. A single POST request is enough to inject a malicious node into the peer list, which all legitimate nodes will discover on their next heartbeat cycle.

```python
# Anyone can register as a peer — no token, no signature, no allowlist
requests.post("http://victim:50000/register", json={"url": "http://attacker:9997"})
```

### V2: Chain Sync Trusts the Longest Chain Over HTTP [CRITICAL]

**File**: `blockchain/chain.py:218-225`, `network/sync.py:22-47`

The `replace_chain()` method accepts any chain that is (a) longer and (b) structurally valid. There is no peer authentication, no TLS, and no distinction between "chain built with massive computing power over months" vs "chain forged in 0.008 seconds."

```python
def replace_chain(self, new_chain, difficulty=DIFFICULTY_BITS):
    if len(new_chain) > len(self._chain) and self.is_valid_chain(new_chain, difficulty):
        self._chain = list(new_chain)  # unconditional replacement
```

### V3: PoW Difficulty Is Trivially Low [CRITICAL]

**File**: `config.py:4`, `blockchain/mining.py:20-22`

`DIFFICULTY_BITS = 4` translates to `prefix = 4 // 4 = 1`, meaning a valid block hash only needs **one leading zero hex character** — a 1-in-16 chance per attempt.

| Difficulty | Avg Attempts | Time per Block |
|------------|-------------|----------------|
| This project (prefix=1) | ~16 | **0.02 ms** |
| Moderate (prefix=4) | ~65,000 | ~140 ms |
| Bitcoin (prefix~19) | ~10^23 | ~10 min (global hashrate) |

An attacker can forge 30 blocks in **0.008 seconds**. This makes the longest-chain rule meaningless — attackers can always outpace the network.

### V4: `sender_url` in Gossip Is Attacker-Controlled [MEDIUM]

**File**: `network/peer_server.py:92-140`

When `receive_block()` fails to append a block (fork detected), it pulls the full chain from `sender_url` — a field taken directly from the attacker's POST body. This is the trigger mechanism for chain replacement.

```python
# Attacker controls where the victim pulls the "correct" chain from
sender_url = data.get("sender_url", "")  # from request body!
if sender_url:
    chain_data = fetch_chain(sender_url)  # victim connects to attacker
    state["chain"].replace_chain(...)     # and replaces its own chain
```

### V5: No API Rate Limiting [MEDIUM]

**File**: `network/peer_server.py:46-89`

The `/api/transaction` endpoint accepts unlimited requests. An attacker can generate a valid ECDSA keypair and flood the mempool (max 10,000 entries) with signed garbage transactions, crowding out legitimate ones.

### V6: Hardcoded Flask Secret Key [MEDIUM]

**File**: `web/app.py:25`

```python
app.secret_key = "trueshot-dev-secret"
```

An attacker who knows this value can forge session cookies.

### V7: Capture Endpoint Skips Chain Validation [LOW]

**File**: `web/routes.py:107-123`

The web route for `/capture` calls `record_capture()` without passing the `chain` parameter, so duplicate image hash checks and device registration checks are skipped.

### V8: pHash Threshold Allows Sophisticated Tampering [LOW]

**File**: `config.py:19`

`PHASH_THRESHOLD = 10` can detect simple modifications (resize, compress, blur) but AI-level manipulations (style transfer, face swap, object removal) that preserve overall image structure may remain within threshold.

## Attack Scripts

### 1. `attack_fake_chain.py` — Full Chain Replacement (Primary Attack)

**Combines tracker poisoning + signed forged chain in a single automated script.**

This is the attack that was successfully executed against 3 live nodes.

```bash
python attacks/attack_fake_chain.py \
  --tracker http://<victim-ip>:50000 \
  --attacker-ip <attacker-ip> \
  --serve-port 9997 \
  --blocks 30
```

The script executes 5 steps automatically:

| Step | Action | Vulnerability Exploited |
|------|--------|------------------------|
| 1. Recon | Contact Tracker, discover all peers, probe chain heights | V1 (no auth on Tracker) |
| 2. Poison | Register malicious node in Tracker's peer list, start heartbeat | V1 |
| 3. Forge | Generate ECDSA keypair, build 30+ properly signed blocks | V3 (low PoW difficulty) |
| 4. Trigger | Serve forged chain on Flask, send invalid block to each peer | V4 (sender_url spoofing) |
| 5. Verify | Confirm all peers adopted the forged chain | V2 (longest chain rule) |

### 2. `attack_tracker_poison.py` — Standalone Tracker Poisoning

Registers a malicious node and serves a forged chain, waiting for victims to sync on their own heartbeat cycle. Passive version of the attack.

```bash
python attacks/attack_tracker_poison.py \
  --tracker http://<victim-ip>:50000 \
  --attacker-url http://<attacker-ip>:9999 \
  --serve-port 9999 \
  --chain-length 30
```

### 3. `attack_tamper_photo.py` — Photo Tampering Detection Test

Applies 11 image modifications (JPEG recompress, crop, blur, flip, noise, desaturate, etc.) and submits each to `/verify` to test what the pHash detection catches vs misses.

```bash
python attacks/attack_tamper_photo.py \
  --target http://<victim-ip>:60001 \
  --image photo.jpg
```

### 4. `attack_flood_mempool.py` — Mempool Denial of Service

Generates thousands of validly-signed garbage CAPTURE transactions and floods the mempool via concurrent threads.

```bash
python attacks/attack_flood_mempool.py \
  --target http://<victim-ip>:60001 \
  --count 5000 \
  --threads 20
```

### 5. `attack_gossip_hijack.py` — Gossip Protocol sender_url Spoofing

Sends an invalid block with a spoofed `sender_url` to trigger fork-resolution chain pull. Same core mechanism as `attack_fake_chain.py` but without the tracker poisoning step.

```bash
python attacks/attack_gossip_hijack.py \
  --target http://<victim-ip>:60001 \
  --attacker-url http://<attacker-ip>:9999 \
  --serve-port 9999 \
  --chain-length 25
```

## Live Attack Results

Executed on 2026-04-30 between two PCs on the same WiFi hotspot.

**Command:**
```bash
python attacks/attack_fake_chain.py \
  --tracker http://10.206.134.178:50000 \
  --attacker-ip 10.206.116.8 \
  --serve-port 9997 \
  --blocks 30
```

**Results:**

| Metric | Before | After |
|--------|--------|-------|
| Chain height (all 3 nodes) | 3 | **31** |
| Last block miner | `d37503...` (legitimate) | `bd46f4...` (**attacker**) |
| Nodes compromised | 0 | **3 / 3** |
| Time to forge 30 signed blocks | — | **0.008s** |
| Original photo records | Present | **Erased** |

All three peer nodes (`:60001`, `:60002`, `:60003`) had their entire chain history replaced with attacker-controlled data. Every legitimate photo record was erased and replaced with forged CAPTURE transactions.

## Attack Flow Diagram

```
Attacker                           Tracker                     Peer A / B / C
   │                                  │                             │
   │─── POST /register ──────────────►│                             │
   │    {"url":"http://attacker:9997"} │                             │
   │◄── 200 OK ──────────────────────│                             │
   │                                  │                             │
   │  [Generate ECDSA keypair]        │                             │
   │  [Forge 30 blocks in 0.008s]     │                             │
   │  [Start Flask on :9997]          │                             │
   │                                  │                             │
   │─── POST /api/block (invalid) ────┼────────────────────────────►│
   │    {index:999,                   │    "append failed...        │
   │     sender_url:"http://          │     fork detected!          │
   │       attacker:9997"}            │     let me pull the chain"  │
   │                                  │                             │
   │◄─── GET /api/blocks ────────────┼─────────────────────────────│
   │──── [return 31 forged blocks] ──┼────────────────────────────►│
   │                                  │    "new chain is longer     │
   │                                  │     and valid... replacing!"│
   │                                  │                             │
   │                                  │    *** CHAIN REPLACED ***   │
   │                                  │    All original data lost.  │
```

## Why Real Blockchains Don't Have These Problems

| Defense | Bitcoin / Ethereum | This Project |
|---------|-------------------|--------------|
| PoW difficulty | Requires mass-scale hardware, 10 min/block | 0.02 ms/block, any laptop can outpace the network |
| Node count | Tens of thousands of independent nodes | 3 nodes on one machine |
| Peer discovery | DNS seeds + manual peer exchange, no central authority | Single unauthenticated Tracker |
| Chain pull source | Only from established, long-lived peers | Trusts any URL in a POST body |
| Network layer | Encrypted P2P connections | Plain HTTP, no TLS |

The fundamental issue: this project's security assumes "nobody will attack," rather than building on the cryptographic guarantee of "attacks cannot succeed."
