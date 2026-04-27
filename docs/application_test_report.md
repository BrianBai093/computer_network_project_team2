# Application Layer Test Report

Test run date: 2026-04-27

Command:

```bash
python -m pytest tests/ -v
```

Result:

```text
9 passed in 0.40s
```

## Simulation Setup

The current branch does not include Layer 1 implementation files yet, so the
tests use in-process fake objects that expose the frozen public API expected by
the application layer:

- `FakeTransaction` / `SimTransaction`: `make_register`, `make_capture`,
  `make_endorse`, `signable_bytes`, and `to_dict`.
- `FakeMempool` / `SimMempool`: `add(tx)`.
- `FakeChain` / `SimChain`: `get_all_transactions()`.

No tracker, peer server, HTTP endpoint, gossip, mining, or filesystem blockchain
state is started during these tests.

## Simulated Input / Output Cases

| Test case | Simulated input | Expected output | Result |
|---|---|---|---|
| Wallet save/load | Generated ECDSA wallet, temp JSON wallet path | Reloaded wallet has same private key, public key, and derived `device_id` | PASS |
| Signature validation | Message bytes `b"canonical transaction bytes"`, correct wallet, wrong wallet, changed message, invalid hex signature | Correct signature verifies; changed message, wrong public key, and invalid signature fail | PASS |
| Device registration | Wallet, `FakeMempool`, metadata `{"model": "demo"}` | Signed `REGISTER` transaction in mempool; sender equals wallet public key; payload device id equals wallet device id | PASS |
| Capture recording | Wallet, generated PNG bytes, location `"NYC"`, empty fake chain | Signed `CAPTURE`; payload contains raw-byte SHA-256, pHash, location; duplicate capture with same chain raises `ValueError` | PASS |
| Capture from path | Wallet, temp PNG file path, empty location | Signed `CAPTURE`; image hash equals SHA-256 of file bytes | PASS |
| Endorsement validation | Camera wallet, endorser wallet, fake chain with capture | Signed `ENDORSE`; target id matches capture id; `get_endorsements()` returns it; self-endorsement and missing target raise `ValueError` | PASS |
| Verify exact / modified / unknown | Registered capture chain, original PNG bytes, re-encoded PNG bytes, empty chain | Original image returns `AUTHENTIC`; re-encoded visual match returns `SUSPICIOUS`; empty chain returns `UNKNOWN` | PASS |
| Verify bad signature | Registered capture chain with capture signature overwritten by bad value | Exact SHA match is classified `SUSPICIOUS`, not `AUTHENTIC`; `signature_valid` is false | PASS |
| Full workflow simulation | `SimChain`, `SimMempool`, camera wallet, newsroom wallet, demo PNG bytes | Register camera and newsroom, record capture, endorse capture, verify original as `AUTHENTIC`, modified as `SUSPICIOUS`, empty chain as `UNKNOWN` | PASS |

## Representative Simulated Outputs

Device registration output shape:

```python
{
    "tx_type": "REGISTER",
    "sender": "<wallet.public_key>",
    "payload": {
        "device_id": "<wallet.device_id>",
        "public_key": "<wallet.public_key>",
        "metadata": {"model": "demo"},
    },
    "signature": "<valid ECDSA signature>",
}
```

Capture output shape:

```python
{
    "tx_type": "CAPTURE",
    "sender": "<wallet.public_key>",
    "payload": {
        "device_id": "<wallet.device_id>",
        "image_hash": "<sha256(raw image bytes)>",
        "phash": "<imagehash pHash>",
        "location": "NYC",
    },
    "signature": "<valid ECDSA signature>",
}
```

Verification output shapes:

```python
{
    "result": "AUTHENTIC",
    "matched_tx_id": "<capture tx id>",
    "device_id": "<camera device id>",
    "location": "New York",
    "endorsements": ["<one endorsement dict>"],
    "signature_valid": True,
}
```

```python
{
    "result": "SUSPICIOUS",
    "matched_tx_id": "<capture tx id>",
    "phash_distance": 0,
    "signature_valid": True,
}
```

```python
{
    "result": "UNKNOWN",
    "matched_tx_id": None,
    "endorsements": [],
    "signature_valid": None,
}
```

## Notes

- Re-encoded PNG bytes are used as the modified-image simulation: SHA-256 differs
  because the byte stream changed, while pHash remains close enough to trigger
  `SUSPICIOUS`.
- These tests are application-layer tests only. Once Layer 1 is merged, the same
  cases should be re-run against real `Chain`, `Mempool`, and `Transaction`
  implementations.
