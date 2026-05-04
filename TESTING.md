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
- Network layer: Gossip duplicate-message tracking, Tracker peer registration
  and discovery APIs, and Peer Server block-receive fork handling.
- Application layer: key generation, signatures, image hashing, wallet
  persistence, and basic workflow placeholders.
- Web layer: page routes, form submissions, image upload, verification pages,
  block explorer views, and Peer API endpoints.

## Important Fork Regression Coverage
Policy verified by this test: when a peer receives a competing block, even if that block contains a transaction already present on the peer's local chain, the block must not be appended. The peer treats it as a fork, keeps its current chain tip, and attempts to fetch the sender's chain for the later longest-valid-chain decision.

This is covered by:

```text
tests/test_network.py::TestPeerServer::test_receive_fork_block_with_already_committed_tx_does_not_append
```

The test builds this exact scenario:

- the local peer first commits a block containing a signed transaction;
- the peer then receives a different block at the same height, built from the
  same parent and containing that same transaction;
- `/api/block` rejects the block as not appended;
- the local chain tip remains unchanged;
- the Peer Server emits `fork_detected`;
- the Peer Server attempts to fetch the sender's chain for fork resolution.

This is a high-value regression test because it protects the network behavior
around fork detection, duplicate-on-chain transaction exposure, and the
append-failure path that triggers chain sync.

Run the test with `-s`:

```bash
python3 -m pytest tests/test_network.py::TestPeerServer::test_receive_fork_block_with_already_committed_tx_does_not_append -s -v
```

The output shows the peer's decision flow:

```text
[setup] local peer committed block #1 hash=0de765b3237760c6 tx=dfa5a90425a15ada
[incoming] received competing block #1 hash=048cac0e0edfe7e2 containing tx already on local chain tx=dfa5a90425a15ada
[detect] fork_detected at block #1 from=http://127.0.0.1:8008 our_height=2
[strategy] fetching sender chain from http://127.0.0.1:8008
[result] appended=False local_tip=0de765b3237760c6
[policy] keep local tip; use sender chain only if it is longer and valid
```

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
- `TestPeerServer`: tests the Peer Server `/api/block` fork path when an
  incoming block cannot be appended because it is on a competing branch and
  includes a transaction that is already present on the local chain. The test verifies
  that the block is not appended, the local tip remains unchanged,
  `fork_detected` is emitted, and the sender's chain is fetched for possible
  fork resolution.
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
69 passed in 0.83s
```

All test cases pass.
