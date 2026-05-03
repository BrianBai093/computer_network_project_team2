# Testing

This document explains how to run the TrueShot test suite, what the tests cover,
and the current test result.

## How to Run All Tests

Run this command from the project root:

```bash
python3 -m pytest tests -v
```

If the dependencies are not installed yet, install them first:

```bash
python3 -m pip install -r requirements.txt pytest
```

## Overall Test Coverage

The test suite covers four main parts of the project:

- Blockchain layer: transactions, Merkle roots, blocks, chain validation, mining,
  and the mempool.
- Network layer: Gossip duplicate-message tracking and Tracker peer registration
  and discovery APIs.
- Application layer: key generation, signatures, image hashing, wallet
  persistence, and basic workflow placeholders.
- Web layer: page routes, form submissions, image upload, verification pages,
  block explorer views, and Peer API endpoints.

Current full test result:

```text
69 passed in 0.86s
```

All 69 test cases pass.

## Test File Breakdown

### `tests/test_application.py`

Run this file:

```bash
python3 -m pytest tests/test_application.py -v
```

This file tests the application layer. It contains 15 test cases:

- `TestCryptoUtils`: tests ECDSA keypair generation, signing and verification,
  failed verification with modified data, failed verification with the wrong
  public key, and device ID length.
- `TestImageUtils`: tests deterministic SHA-256 image hashing, different hashes
  for different inputs, hash length, and pHash distance checks for identical,
  similar, and different images.
- `TestWallet`: tests wallet generation, saving and loading a wallet file, and
  automatically creating a wallet when the file does not exist.
- `TestWorkflows`: keeps an entry point for end-to-end workflow tests. It
  currently contains one placeholder test.

Result: all 15 tests pass.

### `tests/test_blockchain.py`

Run this file:

```bash
python3 -m pytest tests/test_blockchain.py -v
```

This file tests the blockchain core. It contains 26 test cases:

- `TestTransaction`: tests creation of `REGISTER`, `CAPTURE`, `ENDORSE`, and
  `REVOKE` transactions, transaction serialization/deserialization, and
  deterministic transaction IDs.
- `TestMerkle`: tests empty transaction lists, single transactions, two
  transactions, deterministic Merkle roots, and order sensitivity.
- `TestBlock`: tests block hash generation and block
  serialization/deserialization.
- `TestChain`: tests genesis block creation, valid block appending, invalid
  block rejection, replacing a chain with a longer valid chain, and chain
  serialization/deserialization.
- `TestMempool`: tests transaction insertion, duplicate rejection, limited
  pending transaction retrieval, removal, max-size enforcement, expired
  transaction eviction, internal index cleanup, and idempotent shutdown.

Result: all 26 tests pass.

### `tests/test_network.py`

Run this file:

```bash
python3 -m pytest tests/test_network.py -v
```

This file tests the network layer. It contains 9 test cases:

- `TestSeenMessages`: tests that a message is treated as unseen the first time,
  seen the second time, and that the LRU cache evicts old entries correctly.
- `TestTracker`: tests the Tracker `/health` endpoint, failed registration when
  the peer URL is missing, registering and listing peers, and the availability of
  the initial peer list endpoint.
- `TestPeerServer`: keeps an entry point for Peer Server API tests. It currently
  contains one placeholder test.
- `TestPeerClient`: keeps an entry point for Peer Client broadcast tests. It
  currently contains one placeholder test.

Result: all 9 tests pass.

### `tests/test_web.py`

Run this file:

```bash
python3 -m pytest tests/test_web.py -v
```

This file tests the Web UI and Peer API. It contains 19 test cases:

- `TestIndex`: tests that the home page returns HTTP 200 and contains the
  TrueShot name.
- `TestRegister`: tests the register page, register form submission, and that a
  register transaction is added to the mempool.
- `TestCapture`: tests the capture page, missing-file handling, and adding a
  capture transaction to the mempool after uploading an image.
- `TestVerify`: tests the verify page and that an unknown image returns
  `UNKNOWN`.
- `TestEndorse`: tests the endorse page and form handling when the target
  transaction ID is missing.
- `TestExplorer`: tests the block explorer, genesis block detail page,
  not-found block handling, and the custom 404 page.
- `TestPeerAPI`: tests `/api/health`, `/api/blocks`, and `/api/peers`.

Result: all 19 tests pass.

## Final Test Result

Full test command:

```bash
python3 -m pytest tests -v
```

Full test result:

```text
69 passed in 0.86s
```

All test cases pass.
