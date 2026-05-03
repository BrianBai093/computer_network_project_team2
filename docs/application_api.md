# TrueShot Application API

This document records the Layer 3 application API implemented for TrueShot.
Application code creates and verifies semantic photo provenance records while
calling Layer 1 only through the public `Transaction`, `Mempool`, and `Chain`
contracts.

## Dependencies

- `ecdsa`: ECDSA NIST256p key generation, signing, and verification.
- `Pillow` and `ImageHash`: image decoding and perceptual pHash calculation.
- `pytest`: test runner.

## Public Interfaces

### Wallet

```python
Wallet.generate() -> Wallet
Wallet.from_file(path: str) -> Wallet
wallet.save(path: str) -> None
wallet.public_key -> str
wallet.private_key -> str
wallet.device_id -> str
```

Wallet files are JSON objects with `private_key` and `public_key` fields. The
`device_id` is derived as `SHA-256(public_key)[:32]`.

### Device Registration

```python
register_device(wallet: Wallet, mempool: Mempool, metadata: dict | None = None) -> Transaction
```

Creates a `REGISTER` transaction with payload `device_id`, `public_key`, and
`metadata`, signs `tx.signable_bytes()`, writes `tx.signature`, and submits it to
`mempool.add(tx)`.

### Capture

```python
record_capture(
    wallet: Wallet,
    image_data: bytes | str,
    mempool: Mempool,
    location: str,
    chain: Chain | None = None,
) -> Transaction
```

Creates a `CAPTURE` transaction with strict raw-byte SHA-256 and perceptual
pHash. The optional `chain` parameter is a backwards-compatible extension: when
provided, the function rejects duplicate on-chain `image_hash` values.

### Endorsement

```python
endorse_capture(
    wallet: Wallet,
    target_tx_id: str,
    mempool: Mempool,
    chain: Chain | None = None,
) -> Transaction

get_endorsements(target_tx_id: str, chain: Chain) -> list[Transaction]
```

`endorse_capture` creates an `ENDORSE` transaction. The optional `chain`
parameter enables target existence validation and self-endorsement rejection.
`get_endorsements` returns only `ENDORSE` transactions whose
`payload["target_tx_id"]` matches the requested capture id.

### Verification

```python
verify_image(image_data: bytes, chain: Chain) -> VerifyDetail
```

The verification result is:

- `AUTHENTIC`: exact SHA-256 match, valid capture signature, and valid device
  registration.
- `SUSPICIOUS`: exact SHA match with invalid signature/registration, or pHash
  distance at or below `10` while SHA differs.
- `UNKNOWN`: no exact or perceptual match.

`VerifyDetail.to_dict()` returns:

```python
{
    "result": str,
    "message": str,
    "image_hash": str,
    "phash": str,
    "matched_tx_id": str | None,
    "device_id": str | None,
    "timestamp": float | None,
    "location": str | None,
    "capture": dict | None,
    "endorsements": list[dict],
    "phash_distance": int | None,
    "signature_valid": bool | None,
}
```

## Layer Calls

Application workflows call:

- `Transaction.make_register(...)`
- `Transaction.make_capture(...)`
- `Transaction.make_endorse(...)`
- `tx.signable_bytes()`
- `tx.to_dict()`
- `mempool.add(tx)`
- `chain.get_all_transactions()`

They do not call peer HTTP endpoints, tracker APIs, gossip, mining, or private
Layer 1 attributes.

## Error Behavior

- Invalid wallet files raise `ValueError`.
- Undecodable image data raises `ValueError`.
- Duplicate captures raise `ValueError` only when `record_capture(..., chain=...)`
  is used.
- Missing endorsement targets and self-endorsement raise `ValueError` only when
  `endorse_capture(..., chain=...)` is used.
- Mempool rejection raises `ValueError`.

## Example Flow

```python
camera_wallet = Wallet.generate()
newsroom_wallet = Wallet.generate()

register_tx = register_device(camera_wallet, mempool, {"model": "demo"})
capture_tx = record_capture(camera_wallet, image_bytes, mempool, "NYC", chain=chain)
endorse_tx = endorse_capture(newsroom_wallet, capture_tx.tx_id, mempool, chain=chain)
detail = verify_image(image_bytes, chain)
```

The simulation tests use in-process fake Chain, Mempool, and Transaction objects
only because Layer 1 is not present in this branch yet. Those fakes mirror the
frozen public API and should be replaced by the real Layer 1 implementation once
it is merged.
