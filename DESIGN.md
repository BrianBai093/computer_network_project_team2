# TrueShot — Design

> A P2P blockchain that gives every real photograph a **tamper-evident fingerprint**, so anyone can later verify *where it came from* — even in a world full of AI-generated images.

---

## 📌 At a glance

| | |
|---|---|
| **Problem** | AI-generated images are indistinguishable from real photos. Fake images flood every breaking news event. |
| **Approach** | Prove *origin*, not *realism*. Every photo is signed by its capturing device at the moment of capture and registered on a P2P blockchain. |
| **Guarantee** | *This image was signed by this device at this time, and has not been altered since.* |
| **Not a goal** | Judging whether the scene in front of the camera is real. |

---

## 🏛 Three-layer architecture

```
┌──────────────────────────────────────────────────────────┐
│  LAYER 3 — APPLICATION                                   │
│  Four record types + web UI.                             │
│  Meaning lives here.                                     │
├──────────────────────────────────────────────────────────┤
│  LAYER 2 — NETWORK (P2P)                                 │
│  Peers discover each other via a tracker,                │
│  then gossip transactions and blocks directly.           │
├──────────────────────────────────────────────────────────┤
│  LAYER 1 — LEDGER (Blockchain)                           │
│  Append-only chain of blocks, bound by hashes,           │
│  protected by proof-of-work.                             │
└──────────────────────────────────────────────────────────┘
```

**Why three layers?** Each layer defends against a different attack:

| Layer | Defends against |
|-------|----------------|
| 🧱 **Ledger** | Someone quietly changing the past |
| 🌐 **Network** | Someone silencing or overruling the rest of the system |
| 🎯 **Application** | Ambiguity about what the records actually mean |

A forged photo claim would have to defeat **all three** — no single break is enough.

---

## 🧱 Blockchain design

### The four record types

| Record | Who creates it | What it says |
|--------|---------------|--------------|
| **`REGISTER_DEVICE`** | A new camera/owner | *"This device ID belongs to this public key."* |
| **`CAPTURE`** 🎯 | A registered device | *"I captured this image with this hash at this time and place."* |
| **`ENDORSE`** | A trusted endorser (e.g. a newsroom) | *"I vouch for the authenticity of this existing capture."* |
| **`COINBASE`** | The system | *"Reward this peer for mining this block."* |

> **Signatures are mandatory** on every non-coinbase record. Without ECDSA signatures, any peer could impersonate any camera — so this is not an optional add-on, it is the basis of the whole guarantee.

### Block structure

```
┌─────────────────── BLOCK ───────────────────┐
│                                             │
│  HEADER                                     │
│  ├─ index                                   │
│  ├─ timestamp                               │
│  ├─ prev_hash  ──► links to previous block  │
│  ├─ merkle_root ──► fingerprints all txs    │
│  ├─ nonce      ──► proof-of-work puzzle     │
│  └─ difficulty                              │
│                                             │
│  TRANSACTIONS  (a list of records)          │
│  ├─ COINBASE (mining reward)                │
│  ├─ CAPTURE                                 │
│  ├─ ENDORSE                                 │
│  └─ ...                                     │
│                                             │
│  HASH = SHA-256(header)                     │
│       must start with N zeros               │
└─────────────────────────────────────────────┘
```

Each block is linked to the previous one by `prev_hash`, forming an unbroken chain. Any modification to an old block changes its hash, which breaks the link and invalidates every subsequent block.

### Creating a block

A peer creates a block when **either condition** is met:

- 🔴 the mempool has ≥ N pending transactions, **or**
- ⏱ a bounded idle time has elapsed with at least one transaction waiting

Creation flow:

```
take pending txs  →  prepend COINBASE  →  compute Merkle root
     │
     ▼
assemble header  →  search for valid nonce (mining)
     │
     ▼
append to local chain  →  broadcast to peers
```

### Validating a block

Every incoming block passes a strict **6-layer check** before being accepted. Any failure → reject.

| # | Check | Protects against |
|---|-------|-----------------|
| 1 | All fields present | Malformed messages |
| 2 | `prev_hash` matches local tail | Wrong parent |
| 3 | `index` = tail.index + 1 | Out-of-order injection |
| 4 | Hash meets difficulty target | Fake mining |
| 5 | Recomputed hash matches stored hash | Tampered header |
| 6 | Recomputed Merkle root matches stored root | Tampered transactions |

Then **every transaction inside** is validated individually — signature verifies, device is registered, no duplicate captures, and so on.

> A blockchain without strict validation is just a distributed database with extra steps. The rigor *is* the point.

### Difficulty adjustment

Difficulty is recomputed every few blocks based on **on-chain timestamps only** — never wall-clock time. If peers used their local clocks, they would compute different difficulties and permanently fork. Grounding adjustment in the chain itself keeps every peer in sync without any coordination.

---

## 🌐 P2P protocol

### Topology

```
                    ┌─────────────┐
                    │   TRACKER   │   ← discovery only
                    │ (peer list) │     no chain data
                    └──────┬──────┘
                           │
            register / heartbeat / list
                           │
          ┌────────────────┼────────────────┐
          │                │                │
     ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
     │ PEER 1  │◄────►│ PEER 2  │◄────►│ PEER 3  │
     └─────────┘      └─────────┘      └─────────┘
                  ▲                ▲
                  └────────────────┘
                  direct gossip of
                  transactions & blocks
```

**Key point:** the tracker helps peers *find* each other, but never sees transactions or blocks. If the tracker dies, existing peers keep operating — only *new* peers can't join.

> Bitcoin and Ethereum use the same pattern under the names *DNS seeds* and *bootstrap nodes*.

### Gossip propagation

```
   Peer A mines a new block
            │
            ├──► sends to B, C
            │       │
            │       ├─► B validates, applies, forwards to D
            │       └─► C validates, applies, forwards to D
            │               │
            │               └─► D has already seen it, drops silently
```

Three rules keep gossip efficient:

1. ✅ Each peer keeps a cache of **seen message hashes**
2. ✅ A message seen before is **dropped silently** (no broadcast storms)
3. ✅ A new message is **validated first**, then forwarded — never trust, always verify

### Startup and reconnection

When a peer boots (or rejoins after downtime):

```
1. Register with tracker → receive peer list
2. Ask each peer for their chain length
3. Pick the longest chain → download it
4. Validate every block from genesis forward
5. Start mining and listening
```

No manual intervention. No trust. A peer returning from a week-long outage catches up automatically.

### Consensus: the longest chain wins

Peers **do not vote** and **do not negotiate**. Each peer follows one rule:

> **Adopt the longest valid chain I've seen.**

Because producing a block costs proof-of-work, the longest chain is the one backed by the most cumulative computation. Temporary disagreements — two peers mining at nearly the same moment — resolve within one or two further blocks.

---

## 🎯 Demo application

### Four user workflows

```
┌─────────────────┐      ┌─────────────────┐
│  1. REGISTER    │      │  2. CAPTURE     │
│     DEVICE      │      │     PHOTO       │
│                 │      │                 │
│  generate       │      │  upload image   │
│  keypair        │      │  compute hash   │
│  submit pubkey  │      │  sign & submit  │
└─────────────────┘      └─────────────────┘

┌─────────────────┐      ┌─────────────────┐
│  3. VERIFY      │      │  4. ENDORSE     │
│     PHOTO       │      │                 │
│                 │      │  newsroom signs │
│  upload image   │      │  an existing    │
│  look up chain  │      │  capture to     │
│  report result  │      │  vouch for it   │
└─────────────────┘      └─────────────────┘
```

### The three verification outcomes

When a user uploads a photo to verify, the system returns one of:

| Outcome | Condition | Meaning |
|---------|-----------|---------|
| ✅ **Verified** | Exact hash match | Registered by device X at time T. Shows full provenance + endorsements. |
| ⚠️ **Modified** | pHash close, SHA differs | Visually matches a registered photo, but has been altered (recompressed / cropped / edited). |
| ❌ **Unknown** | No match | No on-chain record. Nothing can be said about origin. |

The **modified** outcome is the reason we store *both* a strict content hash and a perceptual hash (pHash) — real photos get recompressed and cropped when they travel through social networks, and a plain SHA-only system would lose them.

### Demonstration scenarios

| # | Scenario | What it shows |
|---|----------|---------------|
| 1 | **Real vs. AI-generated** | Two visually similar images. One verifies ✅. The other returns ❌. |
| 2 | **Tamper detection** | Flip one pixel of a registered photo. Returns ⚠️ *"modified"*. |
| 3 | **Resilience** | Kill a peer mid-demo. Others continue. Killed peer auto-syncs on restart. |
| 4 | **Insurance claim (B2B skin)** | Same protocol, different UI. Shows that TrueShot is infrastructure, not just a consumer app. |

---

## 🚫 What this design does not attempt

TrueShot does **not** prove that the scene in front of a camera is real. A registered device pointed at a screen showing an AI image will produce a cryptographically valid record.

What TrueShot **does** prove is **custody**:

> This specific image data was signed by this specific device at this specific moment, and has not been altered since.

This narrower claim is what cryptography can actually deliver — and it is the foundation any credible broader claim must rest on.
