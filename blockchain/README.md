# Blockchain Layer (Layer 1)

Owner: Member A

This layer implements the core blockchain primitives: transactions, blocks,
mempool, Merkle tree, mining, and the chain itself. It is the foundation
that Layers 2 (Network), 3 (Application), and 4 (Web) build on.

---

## Files

| File | Responsibility |
|------|----------------|
| `transaction.py` | Transaction data class + 4 transaction type factories + coinbase |
| `block.py` | Block data class with auto-computed Merkle root and hash |
| `merkle.py` | Pure Merkle root computation |
| `mempool.py` | Thread-safe pending transaction pool with TTL eviction |
| `mining.py` | PoW mining loop and dynamic difficulty adjustment |
| `chain.py` | Chain validation, append, longest-chain replacement |

All public APIs match the contract defined in `CONTRIBUTING.md` sections 5, 6, and 8.

---

## Quick Start

```python
from blockchain.chain import Chain
from blockchain.mempool import Mempool
from blockchain.transaction import Transaction
from blockchain.mining import mine_block

# 1. Create the core objects (typically done once in run_peer.py)
chain   = Chain()           # genesis block created automatically
mempool = Mempool()         # background TTL evictor starts automatically

# 2. Add a transaction (after signing in Layer 3)
tx = Transaction.make_capture(pubkey, device_id, image_hash, phash, location)
# tx.signature = sign(...)  # done by Layer 3
mempool.add(tx)

# 3. Mine a block (typically in a background mining thread)
pending = mempool.get_pending(limit=100)
block = mine_block(chain.last_block, pending, miner_pubkey)
if block and chain.append_block(block):
    mempool.remove([tx.tx_id for tx in block.transactions])
```

---

## Public API Cheatsheet

### `Chain`

| Method | Returns | Notes |
|--------|---------|-------|
| `chain.height` | `int` | Current chain length |
| `chain.last_block` | `Block` | Tail block |
| `chain.get_block(i)` | `Block \| None` | By index |
| `chain.get_all_blocks()` | `list[Block]` | Snapshot copy |
| `chain.get_all_transactions()` | `list[Transaction]` | Flat list across all blocks |
| `chain.append_block(blk)` | `bool` | Validates internally |
| `chain.replace_chain(new)` | `bool` | Longest-chain rule, must be strictly longer |
| `chain.to_list()` | `list[dict]` | Serialize entire chain |
| `Chain.from_list(data)` | `Chain` | Deserialize |

### `Mempool`

| Method | Returns | Notes |
|--------|---------|-------|
| `mempool.add(tx)` | `bool` | False on duplicate or pool full |
| `mempool.get_pending(limit)` | `list[Transaction]` | Non-destructive read |
| `mempool.remove(tx_ids)` | `None` | After block is committed |
| `mempool.size()` | `int` | |
| `mempool.contains(tx_id)` | `bool` | |
| `mempool.shutdown()` | `None` | Stops background evictor |

### `Transaction`

| Factory | Purpose |
|---------|---------|
| `Transaction.make_register(...)` | Register a device |
| `Transaction.make_capture(...)` | Record a photo |
| `Transaction.make_endorse(...)` | Endorse a capture |
| `Transaction.make_revoke(...)` | Revoke a device |
| `Transaction.make_coinbase(...)` | Mining reward (Layer 1 only) |
| `tx.to_dict()` / `Transaction.from_dict(d)` | Serialization |
| `tx.signable_bytes()` | Bytes to sign/verify (excludes signature field) |

---

## How Each Layer Connects

### Layer 2 — Network

The network layer reads the chain to serve `/api/blocks` and accepts incoming
blocks via `/api/block`. It also mediates transaction gossip into the mempool.

```python
# Receiving a transaction from a peer
tx = Transaction.from_dict(payload["tx"])
if not verify(tx.sender, tx.signable_bytes(), tx.signature):
    return {"status": "invalid signature"}, 400
if mempool.add(tx):
    # New transaction — forward to other peers
    broadcast_transaction(tx, peers, ttl=ttl-1, msg_id=msg_id, exclude_self=self_url)
# else: duplicate, do not re-broadcast

# Receiving a block from a peer
blk = Block.from_dict(payload["block"])
if chain.append_block(blk):
    mempool.remove([tx.tx_id for tx in blk.transactions])
    broadcast_block(blk, peers, ttl=ttl-1, ...)
else:
    # Possible fork — try fetching the sender's chain and replace_chain()
    new_chain_data = fetch_chain(sender_url)
    if new_chain_data:
        new_chain = [Block.from_dict(d) for d in new_chain_data]
        chain.replace_chain(new_chain)
```

**Key points for B:**
- `mempool.add()` returns `False` on duplicate — **use this to stop gossip loops**.
- `chain.append_block()` returning `False` likely means a fork — trigger sync.
- Always verify signatures **before** calling `mempool.add()`.

### Layer 3 — Application

The application layer creates and signs transactions, then submits them to
the mempool. It also queries the chain for verification.

```python
# Creating a CAPTURE transaction
tx = Transaction.make_capture(wallet.public_key, wallet.device_id,
                              image_hash, phash, location)
tx.signature = sign(wallet.private_key, tx.signable_bytes())

# Optional: check duplicates against the chain
for existing in chain.get_all_transactions():
    if existing.tx_type == TX_CAPTURE and existing.payload["image_hash"] == image_hash:
        raise ValueError("Duplicate capture")

mempool.add(tx)
```

**Key points for C:**
- Always set `tx.signature` before calling `mempool.add()` — unsigned transactions
  will be rejected during block validation, leaving them stuck in the pool.
- For verification flows, use `chain.get_all_transactions()` to scan for matches.
- The `Chain` object is read-only from your perspective — use only the methods
  listed in the cheatsheet above. Do not access `_chain`, `_lock`, etc.

### Layer 4 — Web

The web layer reads chain and mempool state for display.

```python
# Explorer page
height       = chain.height
all_blocks   = chain.get_all_blocks()
mempool_size = mempool.size()

# Block detail
block = chain.get_block(index)
if block:
    txs = block.transactions
```

**Key points for D:**
- All read methods return **snapshot copies** — safe to iterate without locking.
- `block.timestamp` is a Unix float; format with `datetime.fromtimestamp()` before display.

---

## Validation Rules (enforced in `chain.is_valid_new_block`)

A block is rejected if any of the following fail:

1. `index` must equal `last_block.index + 1`
2. `previous_hash` must equal `last_block.hash`
3. `block.hash` must equal `block.compute_hash()`
4. `block.hash` must satisfy current difficulty (leading zeros)
5. `merkle_root` must match recomputed Merkle root of transactions
6. The first transaction must be a coinbase, and only one coinbase is allowed
7. Every non-coinbase transaction must have a valid ECDSA signature
8. REVOKE transactions must be signed by the original REGISTER's sender
9. A `device_id` may only be REGISTERed once across the entire chain

The same rules are enforced for full-chain validation in `is_valid_chain`,
which is invoked during `replace_chain`.

---

## Configuration

All tunable values live in `config.py`:

| Constant | Purpose | Suggested |
|----------|---------|-----------|
| `DIFFICULTY_BITS` | PoW difficulty | 16 (demo: ~1s/block) |
| `BLOCK_INTERVAL` | Target block interval (s) | 10 |
| `MAX_BLOCK_TXS` | Max transactions per block | 100 |
| `MAX_MEMPOOL_SIZE` | Max pending transactions | 10000 |
| `MEMPOOL_TX_TTL` | Mempool TTL in seconds | 3600 |
| `MEMPOOL_EVICT_INTERVAL` | Evictor wakeup interval | 60 |
| `MINING_REWARD` | Coinbase reward amount | 1 |
| `GENESIS_HASH` | Genesis previous_hash | `"0" * 64` |
| `TX_REGISTER`, `TX_CAPTURE`, `TX_ENDORSE`, `TX_REVOKE`, `TX_COINBASE` | Tx type strings | — |

**Do not hardcode these values inside the layer.** Always import from `config`.

---

## Threading Model

- `Chain` uses `threading.RLock()` — same thread can re-enter (e.g.
  `append_block` calls `is_valid_new_block`, both acquire the lock).
- `Mempool` uses `threading.Lock()` — flat critical sections, no re-entry needed.
- `Mempool` runs a daemon thread (`MempoolEvictor`) for TTL eviction. Call
  `mempool.shutdown()` for graceful shutdown.
- All public methods on both classes are thread-safe.

---

## Known Constraints (intentional)

- **One REGISTER per device** — duplicates are rejected during block validation.
- **Coinbase has no signature** — verification skips it; only one coinbase per
  block, must be the first transaction.
- **Genesis block is hardcoded** — `timestamp=0.0`, `miner="genesis"`, no
  transactions. All nodes must produce identical genesis blocks.
- **Difficulty is in 4-bit increments** — `_meets_difficulty` uses hex-character
  prefix matching; finer adjustments are not enforced. (See Member A note.)

---

## Contact

Issues, edge cases, or proposed API changes: **post in the team chat first**
before editing this layer or `config.py`.