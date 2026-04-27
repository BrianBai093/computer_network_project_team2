# TrueShot — Contributing Guide

Read this **before writing a single line of code**.
The goal is to keep all four layers compatible so integration is smooth.

---

## Table of Contents

1. [Branch & commit conventions](#1-branch--commit-conventions)
2. [Coding style](#2-coding-style)
3. [File ownership — who touches what](#3-file-ownership--who-touches-what)
4. [The `node_state` dict — central contract](#4-the-node_state-dict--central-contract)
5. [Transaction JSON format — frozen](#5-transaction-json-format--frozen)
6. [Block JSON format — frozen](#6-block-json-format--frozen)
7. [HTTP API contract](#7-http-api-contract)
8. [Public Python API per layer](#8-public-python-api-per-layer)
9. [Testing rules](#9-testing-rules)
10. [Known design notes for each member](#10-known-design-notes-for-each-member)

---

## 1. Branch & Commit Conventions

Create your branch from `start`:

```bash
git checkout start
git pull origin start
git checkout -b feature/layer1-blockchain   # or layer2 / layer3 / layer4
```

| Member | Branch name |
|--------|-------------|
| A — Blockchain | `feature/layer1-blockchain` |
| B — Network    | `feature/layer2-network`    |
| C — Application| `feature/layer3-application`|
| D — Web + Tests| `feature/layer4-web`        |

**Commit message format:**

```
[layer1] Add TX signature verification in chain validation
[layer2] Fix gossip fan-out to use random peer subset
[config] Add TX_COINBASE constant
```

Rules:
- Run `python -m pytest tests/ -v` and make sure all tests pass before opening a PR.
- If you must edit a file owned by another member (e.g. `config.py`), post in the group chat first.

---

## 2. Coding Style

| Rule | Detail |
|------|--------|
| Language | All code and comments in **English** |
| Indentation | 4 spaces — no tabs |
| Naming | `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants |
| Type hints | Required on every **public** function/method signature (args + return) |
| Docstrings | Required on every public function/method; use Google style (`Args:`, `Returns:`, `Raises:`) |
| Imports | stdlib → third-party → project; blank line between each group |
| Constants | All new constants go in `config.py`, never hard-coded inside modules |
| Dependencies | Do **not** add new third-party packages without team agreement + updating `requirements.txt` |

---

## 3. File Ownership — Who Touches What

Only edit files in your own layer unless agreed otherwise.

| Member | Owns | May also edit |
|--------|------|---------------|
| A — Blockchain | `blockchain/` | `config.py` (with notice) |
| B — Network | `network/`, `run_tracker.py` | `config.py` (with notice) |
| C — Application | `application/` | — |
| D — Web + Tests | `web/`, `run_peer.py`, `tests/` | — |

`config.py` is shared. Post in chat before changing it.

---

## 4. The `node_state` Dict — Central Contract

Defined in `run_peer.py : build_node_state()`.
**Do not add or remove keys without a team decision.**

```python
node_state = {
    "chain":       Chain,            # blockchain.chain.Chain
    "mempool":     Mempool,          # blockchain.mempool.Mempool
    "known_peers": set[str],         # set of peer URL strings
    "seen":        SeenMessages,     # network.gossip.SeenMessages
    "wallet":      Wallet,           # application.wallet.Wallet
    "stop_event":  threading.Event,  # graceful shutdown signal
    "self_url":    str,              # this node's own URL
}
```

**Read / write permissions:**

| Key | A (blockchain) | B (network) | C (application) | D (web) |
|-----|:--------------:|:-----------:|:---------------:|:-------:|
| `chain` | owner (R/W) | R/W (sync, append) | R (verify, query) | R (display) |
| `mempool` | owner (R/W) | W (add on gossip) | W (add on workflow) | R (size) |
| `known_peers` | — | W (heartbeat update) | — | R (count) |
| `seen` | — | R/W | — | — |
| `wallet` | — | — | owner (R/W) | R |
| `stop_event` | — | R | — | — |
| `self_url` | — | R | — | — |

---

## 5. Transaction JSON Format — Frozen

The following dict structure is produced by `Transaction.to_dict()` and consumed by
`Transaction.from_dict()`.
**Do not rename, add, or remove fields** — all four layers depend on this.

```python
{
    "tx_id":     str,    # SHA-256 hex, 64 characters
    "tx_type":   str,    # one of: "REGISTER" | "CAPTURE" | "ENDORSE" | "REVOKE"
    "sender":    str,    # sender public key (hex)
    "payload":   dict,   # type-specific content (see schemas below)
    "timestamp": float,  # Unix timestamp — the canonical capture time for all types
    "signature": str,    # ECDSA signature (hex), or "" if unsigned
}
```

### Payload schemas (field names and types are frozen)

**REGISTER**
```python
{
    "device_id":  str,   # derived from SHA-256 of public_key, first 32 hex chars
    "public_key": str,   # sender's public key (hex) — same as outer "sender"
    "metadata":   dict,  # free-form: model, serial, etc.
}
```

**CAPTURE**
```python
{
    "device_id":  str,   # device that took the photo
    "image_hash": str,   # SHA-256 of the raw image bytes (hex, 64 chars)
    "phash":      str,   # perceptual hash (imagehash pHash string)
    "location":   str,   # optional GPS / place string, "" if unknown
}
```
> Note: the capture timestamp is stored in the Transaction-level `timestamp` field — there is no separate `timestamp` inside the payload.

**ENDORSE**
```python
{
    "target_tx_id":       str,   # tx_id of the CAPTURE transaction being endorsed
    "endorser_device_id": str,   # device_id of the endorser
}
```

**REVOKE**
```python
{
    "target_device_id": str,   # device_id being revoked
    "reason":           str,   # human-readable reason string, "" if none
}
```

---

## 6. Block JSON Format — Frozen

Produced by `Block.to_dict()`, consumed by `Block.from_dict()` and the `/api/block` endpoint.

```python
{
    "index":         int,    # block height, 0 = genesis
    "previous_hash": str,    # SHA-256 hex of previous block, 64 chars
    "timestamp":     float,  # Unix timestamp when this block was mined
    "transactions":  list,   # list of Transaction dicts (see above)
    "merkle_root":   str,    # Merkle root of tx_ids, SHA-256 hex, 64 chars
    "nonce":         int,    # PoW nonce
    "miner":         str,    # miner's public key (hex), or "genesis" for block 0
    "hash":          str,    # SHA-256 of block header, 64 chars
}
```

---

## 7. HTTP API Contract

### Peer-to-Peer API  (owner: Member B)

Other members call these via `network/peer_client.py` — do not call them directly.

| Method | Endpoint | Request body | Response body |
|--------|----------|-------------|---------------|
| GET | `/api/health` | — | `{"status": "ok"}` |
| GET | `/api/blocks` | — | `{"chain": [<Block dict>, ...]}` |
| GET | `/api/peers` | — | `{"peers": ["http://...", ...]}` |
| POST | `/api/transaction` | `{"tx": <TX dict>, "ttl": int, "msg_id": str}` | `{"status": "ok"}` or `{"status": "duplicate"}` |
| POST | `/api/block` | `{"block": <Block dict>, "ttl": int, "msg_id": str}` | `{"status": "ok", "appended": bool}` |

Error responses always use HTTP 400 with body `{"error": "<message>"}`.

### Tracker API  (owner: Member B)

| Method | Endpoint | Request body | Response body |
|--------|----------|-------------|---------------|
| POST | `/register` | `{"url": str}` | `{"status": "ok", "registered": str}` |
| GET | `/peers` | — | `{"peers": ["http://...", ...]}` |
| GET | `/health` | — | `{"status": "ok", "peer_count": int}` |

---

## 8. Public Python API Per Layer

These are the **only** methods other layers may call.
Do not access private attributes (those starting with `_`).

### Layer 1 — Blockchain  (owner: Member A)

```python
# Chain  (blockchain/chain.py)
chain.height                                              -> int
chain.last_block                                          -> Block
chain.get_block(index: int)                               -> Block | None
chain.get_all_blocks()                                    -> list[Block]
chain.get_all_transactions()                              -> list[Transaction]
chain.append_block(block: Block, difficulty: int = ...)   -> bool
chain.replace_chain(new_chain: list[Block], difficulty: int = ...) -> bool
chain.to_list()                                           -> list[dict]
Chain.from_list(data: list[dict])                         -> Chain

# Mempool  (blockchain/mempool.py)
mempool.add(tx: Transaction)                              -> bool
mempool.get_pending(limit: int = MAX_BLOCK_TXS)           -> list[Transaction]
mempool.remove(tx_ids: list[str])                         -> None
mempool.size()                                            -> int

# Transaction factories  (blockchain/transaction.py)
Transaction.make_register(sender_pubkey, device_id, metadata)     -> Transaction
Transaction.make_capture(sender_pubkey, device_id, image_hash, phash, location) -> Transaction
Transaction.make_endorse(sender_pubkey, target_tx_id, endorser_device_id) -> Transaction
Transaction.make_revoke(sender_pubkey, target_device_id, reason)   -> Transaction
Transaction.from_dict(d: dict)                                      -> Transaction
tx.to_dict()                                                        -> dict
tx.signable_bytes()                                                 -> bytes
```

### Layer 2 — Network  (owner: Member B)

```python
# peer_client.py
broadcast_transaction(tx: Transaction, peers: list[str], ttl: int, msg_id: str, exclude_self: str) -> None
broadcast_block(block: Block, peers: list[str], ttl: int, msg_id: str, exclude_self: str)          -> None
fetch_chain(peer_url: str)                   -> list[dict] | None
fetch_peers(tracker_url: str)               -> list[str]
register_with_tracker(tracker_url: str, self_url: str) -> bool

# sync.py
initial_sync(state: dict, tracker_url: str) -> None
heartbeat_loop(state: dict, tracker_url: str, self_url: str, interval: int) -> None  # run in thread
```

### Layer 3 — Application  (owner: Member C)

```python
# device.py
register_device(wallet: Wallet, mempool: Mempool, metadata: dict | None) -> Transaction

# capture.py
record_capture(wallet: Wallet, image_data: bytes | str, mempool: Mempool, location: str) -> Transaction

# endorse.py
endorse_capture(wallet: Wallet, target_tx_id: str, mempool: Mempool) -> Transaction
get_endorsements(target_tx_id: str, chain: Chain) -> list[Transaction]

# verify.py
verify_image(image_data: bytes, chain: Chain) -> VerifyDetail
# VerifyDetail.result  -> VerifyResult  ("AUTHENTIC" | "SUSPICIOUS" | "UNKNOWN")
# VerifyDetail.to_dict() -> dict

# wallet.py
Wallet.generate()          -> Wallet
Wallet.from_file(path: str) -> Wallet
wallet.save(path: str)     -> None
wallet.public_key          -> str
wallet.private_key         -> str
wallet.device_id           -> str
```

---

## 9. Testing Rules

- Every new function needs at least one test.
- Test file ownership mirrors code ownership:

| File | Owner |
|------|-------|
| `tests/test_blockchain.py` | Member A |
| `tests/test_network.py` | Member B |
| `tests/test_application.py` | Member C |
| `tests/test_web.py` | Member D |

- `python -m pytest tests/ -v` must be **100% green** before any PR.
- Use `pytest.fixture` for shared setup (node_state, etc.) — do not duplicate setup code.
- Do not mock `Chain` or `Mempool` — use real instances. This prevents the class of bug where mocked tests pass but integration fails.

---

## 10. Known Design Notes for Each Member

### Member A — Blockchain

- **Transaction signature verification is not yet in `chain.py`.**
  `is_valid_new_block()` currently only checks hash, difficulty, and Merkle root. It must also verify the ECDSA `signature` of every transaction against the `sender` public key. Without this, the blockchain provides no authenticity guarantee.
  Call `application.crypto_utils.verify(tx.sender, tx.signable_bytes(), tx.signature)` for each tx.

- **`TX_COINBASE = "COINBASE"` is reserved in `config.py`.**
  DESIGN.md specifies a mining reward transaction prepended to every block.
  Decide with the team whether to implement it; if so, add a `make_coinbase()` factory and handle it in `is_valid_new_block()` (the coinbase tx has no signature requirement).

- **REVOKE authorization is not enforced.**
  Currently any sender can revoke any device. Enforce that `tx.sender` == the `public_key` from the original REGISTER transaction for `target_device_id`.

### Member B — Network

- **Gossip currently broadcasts to *all* known peers.**
  In `broadcast_transaction` and `broadcast_block`, pick a random subset (e.g. 3–5 peers) instead of iterating the full list, to avoid network storms as the peer count grows.

- **Fork/conflict is not handled on gossip block receipt.**
  If `chain.append_block()` returns `False` (the received block is not the immediate next block), the node may be on a fork. Trigger a `fetch_chain` + `replace_chain` attempt from the sender's URL.

- **`/api/transaction` does not verify signatures.**
  Any peer can relay transactions with invalid or missing signatures into the mempool. Add a signature check before `mempool.add()`.

### Member C — Application

- **`verify_image` does not re-verify the on-chain transaction signature.**
  After finding an exact SHA-256 match, call `crypto_utils.verify(tx.sender, tx.signable_bytes(), tx.signature)` to confirm the record itself was not forged.

- **Self-endorsement is not prevented.**
  In `endorse_capture`, reject the case where `wallet.device_id == capture_tx.payload["device_id"]`.

- **Duplicate capture is not detected.**
  In `record_capture`, warn (or raise) if `image_hash` already appears on the chain.

### Member D — Web + Integration

- **Explorer timestamps are raw Unix floats.**
  Format them with `datetime.fromtimestamp(ts).strftime(...)` in the template or in the route before passing to Jinja.

- **`run_peer.py` does not handle SIGINT/SIGTERM.**
  Wire `stop_event.set()` to a signal handler so the mining and heartbeat threads shut down cleanly on Ctrl-C.

- **Demo script is missing.**
  Write `demo.sh` or `demo.py` that spins up 1 Tracker + 3 Peers, registers devices, records a capture, endorses it, then verifies — printing the final result. This is needed for the live demo.
